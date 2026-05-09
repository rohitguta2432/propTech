"""POST /v1/feedback — user flags a wrong score for review.

Sprint 1 Day 12. See specs/api.md `POST /v1/feedback` and
specs/database.md `feedback` table.

Behaviour:
- Validate that `check_id` references an existing row in `checks`.
- Insert a new `feedback` row with status='pending'.
- Return 201 with `{id, status}`.
- Same rate-limit decorator as /v1/check (10/min/IP, keyed callers exempt).
- Database errors never propagate to the caller — surfaced as 503.
- On successful insert, log a structured warning so the founder can see new
  flags in production logs without an external service.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.middleware.rate_limit import cost_func, limiter
from app.models.db import Check, Feedback
from app.models.schemas import FeedbackRequest, FeedbackResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/feedback", response_model=FeedbackResponse, status_code=201)
@limiter.limit("10/minute", cost=cost_func)
def submit_feedback(
    payload: FeedbackRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> FeedbackResponse:
    # 1) Validate check_id references an existing check.
    try:
        exists = db.query(Check.id).filter(Check.id == payload.check_id).first()
    except SQLAlchemyError as exc:
        # DB unreachable / schema mismatch — surface as 503, never raw.
        logger.exception("feedback: db lookup failed")
        raise HTTPException(
            status_code=503,
            detail={
                "code": "ENGINE_ERROR",
                "message": "Database is temporarily unavailable. Please retry shortly.",
            },
        ) from exc

    if exists is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "CHECK_NOT_FOUND",
                "message": f"No check found with id '{payload.check_id}'.",
            },
        )

    # 2) Insert the feedback row (status defaults to 'pending').
    try:
        row = Feedback(
            check_id=payload.check_id,
            reason=payload.reason,
            note=payload.note,
            reporter_email=str(payload.reporter_email) if payload.reporter_email else None,
            status="pending",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("feedback: db insert failed")
        raise HTTPException(
            status_code=503,
            detail={
                "code": "ENGINE_ERROR",
                "message": "Could not record feedback right now. Please retry shortly.",
            },
        ) from exc

    # 3) Founder-facing structured log line (cheap stand-in for email/Sentry
    # which arrive in a later sprint). Stays out of stdout in tests because
    # the default log level is WARNING.
    logger.warning(
        "new_feedback",
        extra={
            "feedback_id": row.id,
            "check_id": row.check_id,
            "reason": row.reason,
            "has_email": bool(row.reporter_email),
        },
    )

    return FeedbackResponse(id=row.id, status=row.status)
