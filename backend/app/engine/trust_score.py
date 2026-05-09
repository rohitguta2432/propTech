"""Trust scoring engine.

v1 stub — returns a fixed example report. Real signals land Sprint 1 Day 7+.
See specs/trust-engine.md for the rules being implemented.
"""
import secrets
from datetime import UTC, datetime

from app.models.schemas import (
    CheckResponse,
    Flag,
    PropertyInfo,
    Verifications,
)


def compute_stub(url: str) -> CheckResponse:
    """Return a deterministic example report for the given URL.

    This is the fixed Whitefield example used in design mockups so the
    frontend can be built against a stable shape.
    """
    return CheckResponse(
        id=f"chk_{secrets.token_hex(4)}",
        score=42,
        label="risky",
        summary="This listing has 4 high-risk signals.",
        property=PropertyInfo(
            portal="magicbricks",
            listing_id="12345",
            title="3 BHK Apartment in Whitefield",
            price_inr=12_000_000,
            bhk=3,
            area_sqft=1450,
            locality="Whitefield",
            city="Bangalore",
            state="karnataka",
            rera_id=None,
            builder_name="ABC Developers",
            listed_at=datetime(2026, 2, 10, 8, 0, tzinfo=UTC),
        ),
        red_flags=[
            Flag(
                code="DUPLICATE_LISTING",
                label="Duplicate listings detected",
                description=(
                    "Listed 4 times across 3 portals at 3 different prices: "
                    "₹1.2 Cr, ₹1.35 Cr, ₹1.1 Cr."
                ),
                severity="high",
                evidence_urls=[
                    "https://www.magicbricks.com/...",
                    "https://www.99acres.com/...",
                    "https://housing.com/...",
                ],
                source="PropCheck dedup engine",
            ),
            Flag(
                code="STOLEN_PHOTOS",
                label="Photos likely stolen",
                description="Listing photos appear on 7 other unrelated listings across India.",
                severity="high",
                evidence_urls=[],
                source="Google Vision reverse image search",
            ),
            Flag(
                code="RERA_MISMATCH",
                label="RERA mismatch",
                description=(
                    "The RERA number on this listing does not match any "
                    "Karnataka RERA project record."
                ),
                severity="high",
                evidence_urls=[],
                source="Karnataka RERA portal",
            ),
            Flag(
                code="BUILDER_COMPLAINTS",
                label="Builder has 6 complaints",
                description=(
                    "ABC Developers has 6 open complaints + 2 reported "
                    "delays in the past 3 years."
                ),
                severity="medium",
                evidence_urls=[],
                source="Karnataka RERA complaint registry",
            ),
        ],
        green_flags=[],
        checklist=[
            "Visit the property in person before paying any token",
            "Ask for the sale deed",
            "Verify property tax record at the municipal portal",
            "Never pay token over UPI to a personal account",
            "Verify owner identity with Aadhaar + utility bill",
        ],
        verifications=Verifications(
            rera={"status": "MISMATCH", "expected": "any-karnataka-record", "found": None},
            image_match_count=7,
            locality_avg_price_per_sqft=10_600,
            price_delta_pct=-22,
            listing_age_days=87,
            builder_open_complaints=6,
        ),
        checked_at=datetime.now(UTC),
        cache_hit=False,
    )
