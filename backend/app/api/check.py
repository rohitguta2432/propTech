"""POST /v1/check — submit a property listing URL for trust evaluation.
GET /v1/checks/{id} — fetch a previously-run report by id (public, indexable).

Day 5–7 wired up:
- URL parser detects portal + listing_id (Day 4).
- Scraper fetches the live listing HTML (Day 5).
- Trust engine runs RERA + price-deviation + listing-age signals (Day 7).
- Persist every check + 24h cache (Day 4 + Day 10 light version).

The GET endpoint exists so the website can render permanent
`/check/<id>` pages that are crawlable by Google + shareable on
WhatsApp — every check becomes an SEO landing page for its own
listing without us writing one. Public read, rate-limited the same
way as anonymous POST.
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


@router.get("/checks/recent")
@limiter.limit("30/minute", cost=cost_func)
async def list_recent_checks(
    request: Request,
    limit: int = 200,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """List recent check ids for sitemap generation.

    Read-only, public. Returns at most 500 ids. The frontend's
    `sitemap.ts` calls this at build / revalidate time so every
    indexable `/check/<id>` page makes it into sitemap.xml without
    a database connection from the Next.js side.
    """
    limit = max(1, min(500, limit))
    rows = (
        db.query(Check.id, Check.checked_at)
        .order_by(Check.checked_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "items": [
            {"id": r.id, "checked_at": r.checked_at.isoformat() if r.checked_at else None}
            for r in rows
        ],
        "count": len(rows),
    }


@router.get("/checks/{check_id}", response_model=CheckResponse)
@limiter.limit("60/minute", cost=cost_func)
async def get_check(
    check_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> CheckResponse:
    """Fetch a stored report by id.

    Public — no auth. Used by the website's permanent `/check/<id>` route
    and by the Chrome extension's "See full report" CTA. The response is
    the same `CheckResponse` produced by POST /v1/check; clients render
    it identically. Returns 404 if the id doesn't exist.
    """
    # check_id is a short token; bound the lookup so a 100-character path
    # can never become an expensive scan.
    if not check_id or len(check_id) > 64:
        raise HTTPException(
            status_code=404,
            detail={"code": "CHECK_NOT_FOUND", "message": "Report not found."},
        )

    row = db.query(Check).filter(Check.id == check_id).first()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "CHECK_NOT_FOUND", "message": "Report not found."},
        )

    # cache_hit is meaningful only for the POST flow (was this an
    # under-24h re-check?). On a GET we're always reading from the row,
    # so it's always "cached" by definition — but we expose it as False
    # to avoid confusing the same field's POST semantics. The frontend
    # uses `checked_at` for the freshness line, which is what actually
    # matters to the reader.
    return _row_to_response(row, cache_hit=False)


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
