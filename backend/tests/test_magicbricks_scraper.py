"""Tests for the Magicbricks scraper.

Covers:
- Pure parsing of a fixture HTML against an expected JSON shape.
- httpx network errors are caught and surfaced via `fetch_error`.
- httpx timeouts are caught and surfaced via `fetch_error`.

The parse function `_parse` is sync, so tests are sync.
The fetch function is async, so we use `pytest.mark.asyncio`.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from app.scrapers.magicbricks import MagicbricksScraper, _parse


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "magicbricks"
SAMPLE_URL = (
    "https://www.magicbricks.com/propertydetails/"
    "3-bhk-apartment-whitefield-bangalore-pdpid-4d4234567"
)
SAMPLE_LISTING_ID = "4d4234567"


# ---------------------------------------------------------------------------
# Parse-only tests (no network).
# ---------------------------------------------------------------------------


def test_parse_fixture_1():
    """The pure parser must extract every documented field from sample-1."""
    html = (FIXTURE_DIR / "sample-1.html").read_text(encoding="utf-8")
    expected = json.loads((FIXTURE_DIR / "expected-1.json").read_text(encoding="utf-8"))

    listing = _parse(html, SAMPLE_URL, SAMPLE_LISTING_ID)
    actual = asdict(listing)

    # Sanity: inputs preserved.
    assert actual["portal"] == "magicbricks"
    assert actual["url"] == SAMPLE_URL
    assert actual["listing_id"] == SAMPLE_LISTING_ID

    # Snippet should always be set on a successful parse — but its exact
    # contents are an implementation detail, so we don't assert equality.
    assert actual["raw_html_snippet"] is not None
    assert len(actual["raw_html_snippet"]) > 0

    # Every field documented in expected-1.json must match.
    for key, expected_value in expected.items():
        assert actual[key] == expected_value, (
            f"field {key!r}: expected {expected_value!r}, got {actual[key]!r}"
        )


def test_parse_handles_empty_html():
    """A blank body must return a ScrapedListing with no extractions, no error."""
    listing = _parse("", SAMPLE_URL, SAMPLE_LISTING_ID)
    assert listing.portal == "magicbricks"
    assert listing.listing_id == SAMPLE_LISTING_ID
    assert listing.title is None
    assert listing.price_inr is None
    assert listing.fetch_error is None


# ---------------------------------------------------------------------------
# Network-failure tests — fetch must never raise.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_handles_network_error():
    """A connection error must be captured into `fetch_error`, not raised."""

    async def _raise_connect_error(self, url, *args, **kwargs):
        raise httpx.ConnectError("simulated DNS failure")

    scraper = MagicbricksScraper()
    with patch.object(httpx.AsyncClient, "get", _raise_connect_error):
        listing = await scraper.fetch(SAMPLE_URL, SAMPLE_LISTING_ID)

    assert listing.portal == "magicbricks"
    assert listing.listing_id == SAMPLE_LISTING_ID
    assert listing.url == SAMPLE_URL
    assert listing.fetch_error is not None
    assert "ConnectError" in listing.fetch_error or "simulated" in listing.fetch_error
    # No data should have been parsed.
    assert listing.title is None
    assert listing.price_inr is None


@pytest.mark.asyncio
async def test_fetch_handles_timeout():
    """A read/connect timeout must be captured into `fetch_error`."""

    async def _raise_timeout(self, url, *args, **kwargs):
        raise httpx.ReadTimeout("simulated read timeout")

    scraper = MagicbricksScraper()
    with patch.object(httpx.AsyncClient, "get", _raise_timeout):
        listing = await scraper.fetch(SAMPLE_URL, SAMPLE_LISTING_ID)

    assert listing.portal == "magicbricks"
    assert listing.fetch_error is not None
    assert "timeout" in listing.fetch_error.lower()
    assert listing.title is None


@pytest.mark.asyncio
async def test_fetch_handles_unexpected_exception():
    """Even an unrelated exception inside the client must not escape."""

    async def _raise_runtime(self, url, *args, **kwargs):
        raise RuntimeError("something blew up deep inside httpx")

    scraper = MagicbricksScraper()
    with patch.object(httpx.AsyncClient, "get", _raise_runtime):
        listing = await scraper.fetch(SAMPLE_URL, SAMPLE_LISTING_ID)

    assert listing.fetch_error is not None
    assert "RuntimeError" in listing.fetch_error or "blew up" in listing.fetch_error


# ---------------------------------------------------------------------------
# Registry — module import side-effect.
# ---------------------------------------------------------------------------


def test_registered_in_router():
    """The scraper module registers itself with the router on import."""
    from app.scrapers import router

    instance = router.get("magicbricks")
    assert instance is not None
    assert instance.portal == "magicbricks"
