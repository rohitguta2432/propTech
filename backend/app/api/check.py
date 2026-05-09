"""POST /v1/check — submit a property listing URL for trust evaluation.

At Sprint 1 Day 3 this returns a stubbed report. Real parsing + scoring
land in Days 4–9.
"""
from fastapi import APIRouter, HTTPException

from app.engine.trust_score import compute_stub
from app.models.schemas import CheckRequest, CheckResponse

router = APIRouter()


@router.post("/check", response_model=CheckResponse)
def submit_check(payload: CheckRequest) -> CheckResponse:
    if not _is_supported_portal(payload.url):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_URL",
                "message": "URL does not match any supported portal pattern.",
            },
        )

    return compute_stub(payload.url)


def _is_supported_portal(url: str) -> bool:
    """Sprint 1 Day 4 will replace this with real parser routing."""
    supported = ("magicbricks.com", "99acres.com", "housing.com", "nobroker.in")
    return any(d in url for d in supported)
