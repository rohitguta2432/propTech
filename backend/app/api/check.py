"""POST /v1/check — submit a property listing URL for trust evaluation.

Day 5–7 wired up:
- URL parser detects portal + listing_id (Day 4).
- Scraper fetches the live listing HTML (Day 5).
- Trust engine runs RERA + price-deviation + listing-age signals (Day 7).
- Persist every check + 24h cache (Day 4 + Day 10 light version).
"""
import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.engine.trust_score import compute_score, compute_stub
from app.middleware.rate_limit import cost_func, limiter
from app.models.db import Check
from app.models.schemas import CheckRequest, CheckResponse
from app.parsers.router import route, supported_portals
from app.scrapers.base import ScrapedListing
from app.scrapers.router import get as get_scraper

# Tight upper bound to fit Vercel's 10s serverless ceiling.
SCRAPER_TIMEOUT_S = 6.0

router = APIRouter()


@router.post("/check", response_model=CheckResponse)
@limiter.limit("10/minute", cost=cost_func)
async def submit_check(
    payload: CheckRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> CheckResponse:
    portal_route = route(payload.url)
    if portal_route is None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_URL",
                "message": "URL does not match any supported portal pattern.",
                "supported": supported_portals(),
            },
        )

    # Cache lookup — same URL within 24h returns the cached row.
    cached = (
        db.query(Check)
        .filter(Check.url == payload.url)
        .order_by(Check.checked_at.desc())
        .first()
    )
    if cached and (datetime.now(UTC) - _ensure_utc(cached.checked_at)).total_seconds() < 86_400:
        return _row_to_response(cached, cache_hit=True)

    # Scrape the listing.
    scraper = get_scraper(portal_route.portal)
    listing: ScrapedListing
    if scraper is not None:
        try:
            listing = await asyncio.wait_for(
                scraper.fetch(payload.url, portal_route.listing_id),
                timeout=SCRAPER_TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            listing = ScrapedListing(
                portal=portal_route.portal,
                listing_id=portal_route.listing_id,
                url=payload.url,
                fetch_error=f"timeout after {SCRAPER_TIMEOUT_S}s",
            )
        except Exception as exc:  # belt-and-braces — scrapers shouldn't raise
            listing = ScrapedListing(
                portal=portal_route.portal,
                listing_id=portal_route.listing_id,
                url=payload.url,
                fetch_error=f"{type(exc).__name__}: {exc}",
            )
    else:
        listing = ScrapedListing(
            portal=portal_route.portal,
            listing_id=portal_route.listing_id,
            url=payload.url,
            fetch_error="no scraper for this portal",
        )

    # If scraping returned nothing useful, fall back to the stub. Otherwise score it.
    if _is_empty(listing):
        report = compute_stub(payload.url)
        report.property.portal = portal_route.portal
        report.property.listing_id = portal_route.listing_id
    else:
        report = await compute_score(listing, url=payload.url, db=db)

    # Persist (best-effort).
    try:
        row = Check(
            id=report.id,
            portal=portal_route.portal,
            listing_id=portal_route.listing_id,
            url=payload.url,
            score=report.score,
            label=report.label,
            summary=report.summary,
            red_flags=[f.model_dump() for f in report.red_flags],
            green_flags=[f.model_dump() for f in report.green_flags],
            checklist=list(report.checklist),
            verifications=report.verifications.model_dump(exclude_none=False),
            property_data=report.property.model_dump(exclude_none=False, mode="json"),
            cache_hit=False,
            source_surface=_detect_surface(request),
            requester_ip=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            checked_at=report.checked_at,
        )
        db.add(row)
        db.commit()
    except OperationalError:
        db.rollback()

    return report


# ------------------ helpers ------------------


def _is_empty(listing: ScrapedListing) -> bool:
    """A scrape that gave us literally nothing useful — fall back to stub."""
    return all(
        getattr(listing, f) in (None, []) for f in (
            "title",
            "price_inr",
            "bhk",
            "area_sqft",
            "rera_id",
            "builder_name",
        )
    )


def _ensure_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _row_to_response(row: Check, cache_hit: bool) -> CheckResponse:
    # parse_confidence lives inside the JSONB `verifications` column so it
    # survives a cache round-trip without a schema migration. Surface it
    # at the top level of the response too for ergonomic frontend access.
    verifications = row.verifications or {}
    parse_confidence = (
        verifications.get("parse_confidence")
        if isinstance(verifications, dict)
        else None
    )
    return CheckResponse.model_validate({
        "id": row.id,
        "score": row.score,
        "label": row.label,
        "summary": row.summary,
        "property": row.property_data,
        "red_flags": row.red_flags,
        "green_flags": row.green_flags,
        "checklist": row.checklist,
        "verifications": verifications,
        "checked_at": row.checked_at,
        "cache_hit": cache_hit,
        "parse_confidence": parse_confidence,
    })


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


def _detect_surface(request: Request) -> str:
    ua = (request.headers.get("user-agent") or "").lower()
    if "extension" in ua or "chrome-extension" in ua:
        return "extension"
    if "twilio" in ua or "whatsapp" in ua:
        return "whatsapp"
    return "web"
