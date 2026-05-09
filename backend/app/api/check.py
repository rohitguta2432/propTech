"""POST /v1/check — submit a property listing URL for trust evaluation.

Day 4: real URL parsing and per-call DB persistence.
Day 5+: real scraping replaces compute_stub().
"""
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.engine.trust_score import compute_stub
from app.models.db import Check
from app.models.schemas import CheckRequest, CheckResponse
from app.parsers.router import route, supported_portals

router = APIRouter()


@router.post("/check", response_model=CheckResponse)
def submit_check(
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

    # Cache lookup — same URL within 24h returns the cached report.
    cached = (
        db.query(Check)
        .filter(Check.url == payload.url)
        .order_by(Check.checked_at.desc())
        .first()
    )
    if cached and (datetime.now(UTC) - cached.checked_at).total_seconds() < 86_400:
        return _row_to_response(cached, cache_hit=True)

    # Build a fresh report. Currently a deterministic stub — real scoring lands Day 7.
    report = compute_stub(payload.url)
    # Override portal/listing_id with what the parser detected.
    report.property.portal = portal_route.portal
    report.property.listing_id = portal_route.listing_id

    # Persist.
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
        # If the DB is briefly unreachable, still return the report — don't block the user.
        db.rollback()

    return report


def _row_to_response(row: Check, cache_hit: bool) -> CheckResponse:
    return CheckResponse.model_validate(
        {
            "id": row.id,
            "score": row.score,
            "label": row.label,
            "summary": row.summary,
            "property": row.property_data,
            "red_flags": row.red_flags,
            "green_flags": row.green_flags,
            "checklist": row.checklist,
            "verifications": row.verifications,
            "checked_at": row.checked_at,
            "cache_hit": cache_hit,
        }
    )


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
