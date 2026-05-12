"""Pydantic request and response schemas. Source of truth: specs/api.md."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, HttpUrl


class CheckRequest(BaseModel):
    url: str = Field(..., description="Property listing URL on a supported portal.")


class PropertyInfo(BaseModel):
    portal: str
    listing_id: str
    title: str | None = None
    price_inr: int | None = None
    bhk: int | None = None
    area_sqft: int | None = None
    locality: str | None = None
    city: str | None = None
    state: str | None = None
    rera_id: str | None = None
    builder_name: str | None = None
    listed_at: datetime | None = None


class Flag(BaseModel):
    code: str
    label: str
    description: str
    severity: Literal["high", "medium", "low", "positive"]
    evidence_urls: list[str] = Field(default_factory=list)
    source: str


class Verifications(BaseModel):
    rera: dict[str, object] | None = None
    image_match_count: int | None = None
    locality_avg_price_per_sqft: int | None = None
    price_delta_pct: int | None = None
    listing_age_days: int | None = None
    builder_open_complaints: int | None = None
    # How much of the underlying listing data we could trust.
    # Duplicated at the top level of `CheckResponse` for ergonomic access,
    # stored here so it survives a JSONB cache round-trip.
    parse_confidence: Literal["high", "medium", "low"] | None = None


class CheckResponse(BaseModel):
    id: str
    score: int = Field(..., ge=0, le=100)
    label: Literal["safe", "caution", "risky"]
    summary: str
    property: PropertyInfo
    red_flags: list[Flag]
    green_flags: list[Flag]
    checklist: list[str]
    verifications: Verifications
    checked_at: datetime
    cache_hit: bool = False
    # When "low", the trust engine has refused to commit to a meaningful
    # numeric score — the surfaces (web, extension, WhatsApp) should
    # render "Not enough data" rather than the `score` value. The numeric
    # score is still set (to 50, neutral) so the existing schema constraint
    # `int 0..100` is preserved without breaking older clients.
    parse_confidence: Literal["high", "medium", "low"] | None = None


# --- Feedback (Sprint 1 Day 12) -----------------------------------------------

FeedbackReason = Literal["false_positive", "false_negative", "data_error", "other"]


class FeedbackRequest(BaseModel):
    """User-flagged wrong score. See specs/api.md `POST /v1/feedback`."""

    check_id: str = Field(..., description="ID of the check being flagged.")
    reason: FeedbackReason = Field(
        ...,
        description="Why the user is flagging this check.",
    )
    note: str | None = Field(
        default=None,
        description="Optional free-text context from the reporter.",
    )
    reporter_email: EmailStr | None = Field(
        default=None,
        description="Optional email so we can follow up.",
    )


class FeedbackResponse(BaseModel):
    id: int
    status: Literal["pending", "reviewed", "accepted", "rejected"]
