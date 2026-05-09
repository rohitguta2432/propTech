"""Pydantic request and response schemas. Source of truth: specs/api.md."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


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
