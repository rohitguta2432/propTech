"""Tests for trust-engine behavior across parse_confidence levels.

The engine refuses to commit to a real numeric score when the underlying
parse is low-confidence — every signal below that line is unreliable
(a "price 22% below market" claim is meaningless when we don't know the
real price). High/medium parses run the normal signals and pass the
confidence value through to the response.
"""
from __future__ import annotations

import pytest

from app.engine.trust_score import compute_score
from app.scrapers.base import ScrapedListing


def _listing(confidence: str | None, **overrides) -> ScrapedListing:
    """Build a plausible ScrapedListing with the given parse_confidence."""
    base = dict(
        portal="magicbricks",
        listing_id="abc123",
        url="https://www.magicbricks.com/x",
        title="3 BHK Apartment in Whitefield",
        price_inr=12_000_000,
        bhk=3,
        area_sqft=1450,
        locality="Whitefield",
        city="Bangalore",
        state="karnataka",
    )
    base.update(overrides)
    listing = ScrapedListing(**base)
    listing.parse_confidence = confidence
    return listing


# ---------------------------------------------------------------------------
# Low confidence: short-circuit, no signals, DATA_INCOMPLETE flag.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_low_confidence_returns_data_incomplete(db_session):
    listing = _listing("low")
    response = await compute_score(listing, url=listing.url, db=db_session)

    assert response.parse_confidence == "low"
    assert response.verifications.parse_confidence == "low"
    # Score is the neutral midpoint — the engine refuses to commit. Surfaces
    # render "Not enough data" using `parse_confidence`, not by inspecting score.
    assert response.score == 50
    assert response.label == "caution"
    # Exactly one DATA_INCOMPLETE red flag, no green flags, no signal-derived
    # red flags (price/RERA/etc).
    assert len(response.red_flags) == 1
    assert response.red_flags[0].code == "DATA_INCOMPLETE"
    assert response.green_flags == []
    # The checklist nudges the user to verify basics manually.
    assert any("Not enough data" in line or "verify" in line.lower() for line in response.checklist)
    # Verifications are wiped — no fake locality price etc.
    assert response.verifications.locality_avg_price_per_sqft is None
    assert response.verifications.price_delta_pct is None


@pytest.mark.asyncio
async def test_low_confidence_does_not_run_rera_lookup(db_session, monkeypatch):
    """When confidence is low we MUST NOT consume RERA/price-index calls.

    Patches RERA + locality lookups with sentinels that would fail loudly
    if invoked, then asserts the engine short-circuits without touching them.
    """
    from app.engine import trust_score as engine

    async def _boom_rera(*args, **kwargs):
        raise AssertionError("RERA lookup should not run on low-confidence parse")

    async def _boom_price(*args, **kwargs):
        raise AssertionError("Price index lookup should not run on low-confidence parse")

    monkeypatch.setattr(engine, "rera_lookup", _boom_rera)
    monkeypatch.setattr(engine.locality_prices, "get_avg_price", _boom_price)

    listing = _listing("low")
    response = await compute_score(listing, url=listing.url, db=db_session)
    assert response.parse_confidence == "low"


# ---------------------------------------------------------------------------
# High / medium / None: signals run normally, confidence passes through.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_high_confidence_passes_through(db_session):
    listing = _listing("high")
    response = await compute_score(listing, url=listing.url, db=db_session)

    assert response.parse_confidence == "high"
    assert response.verifications.parse_confidence == "high"
    # The DATA_INCOMPLETE flag must NOT appear on high-confidence runs.
    assert all(f.code != "DATA_INCOMPLETE" for f in response.red_flags)


@pytest.mark.asyncio
async def test_medium_confidence_passes_through(db_session):
    listing = _listing("medium")
    response = await compute_score(listing, url=listing.url, db=db_session)

    assert response.parse_confidence == "medium"
    assert response.verifications.parse_confidence == "medium"
    assert all(f.code != "DATA_INCOMPLETE" for f in response.red_flags)


@pytest.mark.asyncio
async def test_none_confidence_treated_as_high_for_back_compat(db_session):
    """Listings predating parse_confidence (None) must still score normally."""
    listing = _listing(None)
    response = await compute_score(listing, url=listing.url, db=db_session)

    # None passes through as None — surfaces fall back to legacy behavior.
    assert response.parse_confidence is None
    assert all(f.code != "DATA_INCOMPLETE" for f in response.red_flags)
