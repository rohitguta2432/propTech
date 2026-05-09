"""Trust scoring engine — v1 with real signals.

Inputs: a `ScrapedListing` (best-effort fields from a portal) + a DB session
(for RERA + locality price lookups).
Output: a `CheckResponse` matching the API contract.

Falls back to a deterministic stub when the scraper couldn't fetch the page —
that way the surface always returns a valid report and the integration is
never gated on scraping success.
"""
from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.integrations import locality_prices
from app.integrations.rera import lookup as rera_lookup
from app.integrations.rera_karnataka import RERAResult
from app.models.schemas import (
    CheckResponse,
    Flag,
    PropertyInfo,
    Verifications,
)
from app.scrapers.base import ScrapedListing

# Score deltas per signal — see specs/trust-engine.md.
DELTA_RERA_MATCH = +10
DELTA_RERA_MISMATCH = -25
DELTA_RERA_MISSING = -10
DELTA_PRICE_BELOW = -10
DELTA_PRICE_ABOVE = -5
DELTA_LISTING_STALE = -5


async def compute_score(
    listing: ScrapedListing,
    *,
    url: str,
    db: Session,
) -> CheckResponse:
    """Run signals against a scraped listing, return a full response."""
    flags: list[Flag] = []
    base = 100

    # ---------------- RERA ----------------
    # Pass listing.state as a hint so Maharashtra listings hit MahaRERA
    # even if the id shape is ambiguous. Inference handles the common
    # case when state isn't set on the scraped listing.
    rera_result: RERAResult = await rera_lookup(
        listing.rera_id, db, state_hint=listing.state
    )
    rera_status = rera_result.status

    if rera_status == "MATCH":
        flags.append(_flag(
            code="RERA_OK",
            label="RERA verified",
            description="The RERA number on this listing matches a registered Karnataka project.",
            severity="positive",
            source="Karnataka RERA portal",
        ))
        base += DELTA_RERA_MATCH
    elif rera_status in ("MISMATCH", "NOT_FOUND"):
        flags.append(_flag(
            code="RERA_MISMATCH",
            label="RERA mismatch",
            description="The RERA number on this listing does not match any Karnataka project record.",
            severity="high",
            source="Karnataka RERA portal",
        ))
        base += DELTA_RERA_MISMATCH
    elif rera_status == "NOT_PROVIDED":
        # Only penalise on flats large enough to need RERA registration
        if listing.area_sqft is not None and listing.area_sqft >= 800:
            flags.append(_flag(
                code="RERA_MISSING",
                label="RERA registration not provided",
                description="No RERA number on the listing. Required for new projects in Karnataka.",
                severity="medium",
                source="PropCheck heuristic",
            ))
            base += DELTA_RERA_MISSING
    # PORTAL_UNREACHABLE → silent, no flag (we don't penalise on our outage)

    # ---------------- Price vs locality ----------------
    avg_pps: int | None = None
    price_delta_pct: int | None = None
    if (
        listing.city
        and listing.locality
        and listing.bhk is not None
        and listing.area_sqft is not None
        and listing.price_inr is not None
        and listing.area_sqft > 0
    ):
        avg_pps = await locality_prices.get_avg_price(
            listing.city, listing.locality, listing.bhk, db
        )
        if avg_pps and avg_pps > 0:
            actual_pps = listing.price_inr / listing.area_sqft
            price_delta_pct = round(((actual_pps - avg_pps) / avg_pps) * 100)
            if price_delta_pct <= -15:
                flags.append(_flag(
                    code="PRICE_BELOW_MARKET",
                    label="Price below locality average",
                    description=(
                        f"This listing is {abs(price_delta_pct)}% below the {listing.locality} "
                        f"{listing.bhk}BHK average of ₹{avg_pps:,}/sqft. Either a deal or bait."
                    ),
                    severity="medium",
                    source="PropCheck locality price index",
                ))
                base += DELTA_PRICE_BELOW
            elif price_delta_pct >= 25:
                flags.append(_flag(
                    code="PRICE_ABOVE_MARKET",
                    label="Price above locality average",
                    description=(
                        f"This listing is {price_delta_pct}% above the {listing.locality} "
                        f"{listing.bhk}BHK average of ₹{avg_pps:,}/sqft."
                    ),
                    severity="low",
                    source="PropCheck locality price index",
                ))
                base += DELTA_PRICE_ABOVE

    # ---------------- Listing age ----------------
    listing_age_days: int | None = None
    if listing.listed_at:
        delta = datetime.now(UTC) - _ensure_utc(listing.listed_at)
        listing_age_days = max(0, delta.days)
        if listing_age_days > 180:
            flags.append(_flag(
                code="LISTING_STALE",
                label="Listing is stale",
                description=f"This listing is {listing_age_days} days old. Either ignored or relisted.",
                severity="low",
                source="PropCheck heuristic",
            ))
            base += DELTA_LISTING_STALE

    # ---------------- Aggregate ----------------
    score = max(0, min(100, base))
    if score >= 70:
        label: str = "safe"
    elif score >= 40:
        label = "caution"
    else:
        label = "risky"

    red_flags = [f for f in flags if f.severity != "positive"]
    green_flags = [f for f in flags if f.severity == "positive"]
    summary = _build_summary(score, red_flags, green_flags)
    checklist = _checklist(rera_status)

    return CheckResponse(
        id=f"chk_{secrets.token_hex(4)}",
        score=score,
        label=label,  # type: ignore[arg-type]
        summary=summary,
        property=PropertyInfo(
            portal=listing.portal,
            listing_id=listing.listing_id,
            title=listing.title,
            price_inr=listing.price_inr,
            bhk=listing.bhk,
            area_sqft=listing.area_sqft,
            locality=listing.locality,
            city=listing.city,
            state=listing.state,
            rera_id=listing.rera_id,
            builder_name=listing.builder_name,
            listed_at=listing.listed_at,
        ),
        red_flags=red_flags,
        green_flags=green_flags,
        checklist=checklist,
        verifications=Verifications(
            rera={"status": rera_status},
            image_match_count=None,
            locality_avg_price_per_sqft=avg_pps,
            price_delta_pct=price_delta_pct,
            listing_age_days=listing_age_days,
            builder_open_complaints=None,
        ),
        checked_at=datetime.now(UTC),
        cache_hit=False,
    )


# ---------------- helpers ----------------


def _flag(*, code: str, label: str, description: str, severity: str, source: str) -> Flag:
    return Flag(
        code=code,
        label=label,
        description=description,
        severity=severity,  # type: ignore[arg-type]
        evidence_urls=[],
        source=source,
    )


def _ensure_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _build_summary(score: int, red_flags: list[Flag], green_flags: list[Flag]) -> str:
    if not red_flags and green_flags:
        return f"This listing looks clean ({len(green_flags)} positive signal{'s' if len(green_flags) > 1 else ''})."
    if not red_flags:
        return "No concerning signals detected."
    high = sum(1 for f in red_flags if f.severity == "high")
    if high:
        return f"This listing has {high} high-risk signal{'s' if high > 1 else ''}."
    return f"This listing has {len(red_flags)} signal{'s' if len(red_flags) > 1 else ''} worth checking."


def _checklist(rera_status: str) -> list[str]:
    items = [
        "Visit the property in person before paying any token",
        "Ask for the sale deed",
        "Verify property tax record at the municipal portal",
        "Never pay token over UPI to a personal account",
        "Verify owner identity with Aadhaar + utility bill",
    ]
    if rera_status in ("MISMATCH", "NOT_FOUND", "NOT_PROVIDED"):
        items.insert(0, "Demand the original RERA registration certificate before any payment")
    return items


# ---------------- legacy stub (still used as fallback) ----------------


def compute_stub(url: str) -> CheckResponse:
    """Deterministic stub for when scraping isn't possible.

    Returns the Whitefield example so the design preview keeps working.
    """
    return CheckResponse.model_validate({
        "id": f"chk_{secrets.token_hex(4)}",
        "score": 42,
        "label": "risky",
        "summary": "Couldn't fetch this listing — showing the design example.",
        "property": {
            "portal": "magicbricks",
            "listing_id": "stub",
            "title": "3 BHK Apartment in Whitefield",
            "price_inr": 12_000_000,
            "bhk": 3,
            "area_sqft": 1450,
            "locality": "Whitefield",
            "city": "Bangalore",
            "state": "karnataka",
            "rera_id": None,
            "builder_name": "ABC Developers",
            "listed_at": "2026-02-10T08:00:00Z",
        },
        "red_flags": [
            {
                "code": "STOLEN_PHOTOS",
                "label": "Photos likely stolen",
                "description": "Listing photos appear on 7 other unrelated listings across India.",
                "severity": "high",
                "evidence_urls": [],
                "source": "Google Vision reverse image search",
            },
            {
                "code": "RERA_MISMATCH",
                "label": "RERA mismatch",
                "description": "The RERA number on this listing does not match any Karnataka RERA project record.",
                "severity": "high",
                "evidence_urls": [],
                "source": "Karnataka RERA portal",
            },
        ],
        "green_flags": [],
        "checklist": [
            "Visit the property in person before paying any token",
            "Ask for the sale deed",
            "Verify property tax record at the municipal portal",
            "Never pay token over UPI to a personal account",
            "Verify owner identity with Aadhaar + utility bill",
        ],
        "verifications": {
            "rera": {"status": "MISMATCH"},
            "image_match_count": 7,
            "locality_avg_price_per_sqft": 10_600,
            "price_delta_pct": -22,
            "listing_age_days": 87,
            "builder_open_complaints": 6,
        },
        "checked_at": datetime.now(UTC).isoformat(),
        "cache_hit": False,
    })
