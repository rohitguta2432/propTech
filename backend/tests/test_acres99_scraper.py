"""Tests for the 99acres scraper.

We exercise three scenarios:

1. _parse() against the fixture HTML matches the expected JSON.
2. fetch() returns a ScrapedListing with `fetch_error` set on a transport
   error (no raise).
3. fetch() returns a ScrapedListing with `fetch_error` set on timeout
   (no raise).

The scraper must NEVER raise — every code path returns a ScrapedListing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

# Make `app.*` importable when pytest is run from `backend/`.
_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.scrapers import acres99 as acres99_scraper  # noqa: E402
from app.scrapers.base import ScrapedListing  # noqa: E402
from app.scrapers.router import get as get_scraper  # noqa: E402


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "99acres"
SAMPLE_HTML = FIXTURES_DIR / "sample-1.html"
EXPECTED_JSON = FIXTURES_DIR / "expected-1.json"


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def test_parse_fixture_matches_expected() -> None:
    html = SAMPLE_HTML.read_text(encoding="utf-8")
    expected = json.loads(EXPECTED_JSON.read_text(encoding="utf-8"))

    scraper = acres99_scraper.parser()
    url = "https://www.99acres.com/2-bhk-flat-indiranagar-bangalore-spid-P12345"
    listing = scraper._parse(html, url, expected["listing_id"])

    assert isinstance(listing, ScrapedListing)
    assert listing.portal == expected["portal"]
    assert listing.listing_id == expected["listing_id"]
    assert listing.url == url
    assert listing.title == expected["title"]
    assert listing.price_inr == expected["price_inr"]
    assert listing.bhk == expected["bhk"]
    assert listing.area_sqft == expected["area_sqft"]
    assert listing.locality == expected["locality"]
    assert listing.city == expected["city"]
    assert listing.rera_id == expected["rera_id"]
    assert listing.builder_name == expected["builder_name"]
    assert len(listing.image_urls) == expected["image_url_count"]
    assert listing.image_urls[0] == expected["first_image_url"]
    # description should be picked up from og:description
    assert listing.description is not None
    assert "Prestige Group" in listing.description
    # raw_html_snippet captured for debugging
    assert listing.raw_html_snippet is not None
    assert listing.fetch_error is None


def test_parse_empty_html_returns_blank_listing() -> None:
    scraper = acres99_scraper.parser()
    listing = scraper._parse("", "https://www.99acres.com/x-spid-X1", "X1")
    assert isinstance(listing, ScrapedListing)
    assert listing.portal == "99acres"
    assert listing.listing_id == "X1"
    assert listing.title is None
    assert listing.price_inr is None
    assert listing.fetch_error is None


def test_parse_garbage_html_does_not_raise() -> None:
    scraper = acres99_scraper.parser()
    listing = scraper._parse("<html>!!! broken < tags >>>", "u://x", "G1")
    assert isinstance(listing, ScrapedListing)
    assert listing.portal == "99acres"


def test_price_parser_variants() -> None:
    assert acres99_scraper._price_to_inr("₹1.85 Cr") == 18_500_000
    assert acres99_scraper._price_to_inr("1.85 Crore") == 18_500_000
    assert acres99_scraper._price_to_inr("₹1,85,00,000") == 18_500_000
    assert acres99_scraper._price_to_inr("75 Lakh") == 7_500_000
    assert acres99_scraper._price_to_inr("85 L") == 8_500_000
    assert acres99_scraper._price_to_inr("") is None
    assert acres99_scraper._price_to_inr("nothing here") is None


# ---------------------------------------------------------------------------
# Fetch — network failures
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_network_error_sets_fetch_error(monkeypatch) -> None:
    """A connection failure must NOT raise — it sets fetch_error."""

    def _transport_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    transport = httpx.MockTransport(_transport_handler)

    class _PatchedClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(acres99_scraper.httpx, "AsyncClient", _PatchedClient)

    scraper = acres99_scraper.parser()
    listing = await scraper.fetch(
        "https://www.99acres.com/property-spid-NET1", "NET1"
    )
    assert isinstance(listing, ScrapedListing)
    assert listing.portal == "99acres"
    assert listing.listing_id == "NET1"
    assert listing.fetch_error is not None
    assert "connection" in listing.fetch_error.lower() or "http_error" in listing.fetch_error.lower()
    # Fields should be untouched
    assert listing.title is None
    assert listing.price_inr is None


@pytest.mark.asyncio
async def test_fetch_timeout_sets_fetch_error(monkeypatch) -> None:
    """A timeout must NOT raise — it sets fetch_error."""

    def _transport_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("read timeout", request=request)

    transport = httpx.MockTransport(_transport_handler)

    class _PatchedClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(acres99_scraper.httpx, "AsyncClient", _PatchedClient)

    scraper = acres99_scraper.parser()
    listing = await scraper.fetch(
        "https://www.99acres.com/property-spid-TO1", "TO1"
    )
    assert isinstance(listing, ScrapedListing)
    assert listing.portal == "99acres"
    assert listing.fetch_error is not None
    assert "timeout" in listing.fetch_error.lower()


@pytest.mark.asyncio
async def test_fetch_http_500_sets_fetch_error(monkeypatch) -> None:
    """An HTTP 500 must NOT raise — it sets fetch_error via raise_for_status."""

    def _transport_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="server boom")

    transport = httpx.MockTransport(_transport_handler)

    class _PatchedClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(acres99_scraper.httpx, "AsyncClient", _PatchedClient)

    scraper = acres99_scraper.parser()
    listing = await scraper.fetch(
        "https://www.99acres.com/property-spid-S1", "S1"
    )
    assert isinstance(listing, ScrapedListing)
    assert listing.fetch_error is not None


@pytest.mark.asyncio
async def test_fetch_success_parses_html(monkeypatch) -> None:
    """A 200 OK with valid HTML must parse successfully (no fetch_error)."""

    html = SAMPLE_HTML.read_text(encoding="utf-8")

    def _transport_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html, headers={"content-type": "text/html"})

    transport = httpx.MockTransport(_transport_handler)

    class _PatchedClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(acres99_scraper.httpx, "AsyncClient", _PatchedClient)

    scraper = acres99_scraper.parser()
    listing = await scraper.fetch(
        "https://www.99acres.com/property-spid-OK1", "OK1"
    )
    assert listing.fetch_error is None
    assert listing.title == "2 BHK Flat in Indiranagar Bangalore"
    assert listing.price_inr == 18_500_000
    assert listing.bhk == 2


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def test_scraper_registered_with_router() -> None:
    """Importing app.scrapers.acres99 must register the portal."""
    scraper = get_scraper("99acres")
    assert scraper is not None
    assert scraper.portal == "99acres"
