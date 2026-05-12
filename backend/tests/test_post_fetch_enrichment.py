"""Tests for the post-fetch enrichment pipeline.

`apply_post_fetch_enrichment` runs after a scraper parses the HTML. It:
  1. Calls the LLM on the direct HTML to fill regex gaps.
  2. If gaps remain (or the fetch failed), fans out to free signals.
  3. Stamps `parse_confidence` so the trust engine knows how much to trust
     the resulting fields.

These tests exercise the pipeline end-to-end against mocked HTTP, with no
network access.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest
import respx

from app.integrations import llm_parser
from app.scrapers.base import (
    ScrapedListing,
    apply_post_fetch_enrichment,
)


SAMPLE_URL = (
    "https://www.magicbricks.com/propertydetails/"
    "3-bhk-apartment-for-sale-in-whitefield-bangalore-pdpid-abc123def"
)


def _make_llm_response(**fields) -> dict:
    return {"choices": [{"message": {"content": json.dumps(fields)}}]}


# ---------------------------------------------------------------------------
# Confidence: high — direct HTML was clean.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confidence_high_when_html_yielded_everything():
    """When regex got every key field, no LLM call, no fanout — confidence high."""
    listing = ScrapedListing(
        portal="magicbricks",
        listing_id="abc123def",
        url=SAMPLE_URL,
        title="3 BHK Apartment",
        price_inr=12_000_000,
        bhk=3,
        area_sqft=1450,
        locality="Whitefield",
        city="Bangalore",
    )
    with patch.object(llm_parser.settings, "openrouter_api_key", "fake-key"):
        # No respx mock — any HTTP call would explode. The function must
        # short-circuit because there are no gaps.
        out = await apply_post_fetch_enrichment(listing, "<html>full</html>", SAMPLE_URL)

    assert out.parse_confidence == "high"
    assert out.enrichment_sources == []


# ---------------------------------------------------------------------------
# Confidence: medium — fanout filled the gaps.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confidence_medium_when_fanout_fills_gaps():
    """Empty HTML body + a 4xx response: fanout fills the gaps via slug + OG."""
    listing = ScrapedListing(
        portal="magicbricks", listing_id="abc123def", url=SAMPLE_URL
    )
    og_html = (
        '<meta property="og:title" content="3 BHK Apartment in Whitefield, Bangalore">'
        '<meta property="og:description" content="₹1.2 Cr · 1450 sqft">'
    )

    with respx.mock() as mock, patch.object(
        llm_parser.settings, "openrouter_api_key", "fake-key"
    ):
        # LLM is called twice: once for HTML (empty body returns nothing),
        # once with supplemental.
        mock.post("https://openrouter.ai/api/v1/chat/completions").mock(
            side_effect=[
                # Pass 1 — empty HTML, model returns mostly nulls.
                httpx.Response(
                    200,
                    json=_make_llm_response(
                        title=None,
                        price_inr=None,
                        bhk=None,
                        area_sqft=None,
                        locality=None,
                    ),
                ),
                # Pass 2 — with supplemental, model fills everything.
                httpx.Response(
                    200,
                    json=_make_llm_response(
                        title="3 BHK Apartment in Whitefield",
                        price_inr=12_000_000,
                        bhk=3,
                        area_sqft=1450,
                        locality="Whitefield",
                        city="Bangalore",
                    ),
                ),
            ]
        )
        mock.get(SAMPLE_URL).mock(return_value=httpx.Response(200, text=og_html))
        # SERP returns nothing useful.
        mock.post("https://html.duckduckgo.com/html/").mock(
            return_value=httpx.Response(200, text="<html><body>no results</body></html>")
        )
        # Wayback returns nothing.
        mock.get("https://archive.org/wayback/available").mock(
            return_value=httpx.Response(200, json={"archived_snapshots": {}})
        )

        out = await apply_post_fetch_enrichment(listing, "<html></html>", SAMPLE_URL)

    assert out.parse_confidence == "medium"
    assert "url_slug" in out.enrichment_sources
    assert "og_meta" in out.enrichment_sources
    assert out.locality == "Whitefield"
    assert out.bhk == 3
    assert out.price_inr == 12_000_000


# ---------------------------------------------------------------------------
# Confidence: low — total failure, nothing filled.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confidence_low_when_everything_fails():
    """HTTP error + fanout all 4xx → still in the dark → low confidence."""
    listing = ScrapedListing(
        portal="magicbricks",
        listing_id="x",
        url="https://www.magicbricks.com/blocked",
        fetch_error="http_status: 403",
    )
    with respx.mock() as mock, patch.object(
        llm_parser.settings, "openrouter_api_key", "fake-key"
    ):
        # Every fanout source fails.
        mock.get("https://www.magicbricks.com/blocked").mock(
            return_value=httpx.Response(403)
        )
        mock.post("https://html.duckduckgo.com/html/").mock(
            return_value=httpx.Response(500)
        )
        mock.get("https://archive.org/wayback/available").mock(
            return_value=httpx.Response(200, json={"archived_snapshots": {}})
        )
        # LLM pass 1 — no HTML, no supplemental yet — short-circuits, no call.
        # LLM pass 2 — supplemental is empty, so should also not be called.

        out = await apply_post_fetch_enrichment(
            listing, "", "https://www.magicbricks.com/blocked"
        )

    assert out.parse_confidence == "low"
    # fetch_error is preserved untouched.
    assert out.fetch_error == "http_status: 403"


# ---------------------------------------------------------------------------
# No LLM key — network fanout is skipped, slug-only still applies.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_llm_key_skips_network_fanout_but_applies_slug():
    """Without OPENROUTER_API_KEY, OG/SERP/Wayback are skipped — slug still fills."""
    listing = ScrapedListing(
        portal="magicbricks", listing_id="abc123def", url=SAMPLE_URL
    )
    with patch.object(llm_parser.settings, "openrouter_api_key", None):
        # Critically: no respx mock. If the code tried any network fanout,
        # it would hit the real internet during tests.
        out = await apply_post_fetch_enrichment(listing, "", SAMPLE_URL)

    # Slug-derived fields were applied directly.
    assert out.locality == "Whitefield"
    assert out.city == "Bangalore"
    assert out.bhk == 3
    # Two of four key fields still missing (price, area), so confidence stays low.
    assert out.parse_confidence == "low"


# ---------------------------------------------------------------------------
# Regex-wins is preserved through the pipeline.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_earlier_fields_win_through_full_pipeline():
    """Earlier wins: fields set by an earlier stage (regex, slug, pass 1) must
    NOT be overwritten by later stages (slug, LLM pass 2)."""
    # Start with NO fields. Slug will fill bhk + locality + city deterministically
    # from the URL. That leaves price_inr and area_sqft as the only gaps for
    # pass 2 to act on — and we let pass 2's LLM try to overwrite the slug
    # fields too. The merge must hold the line.
    listing = ScrapedListing(
        portal="magicbricks",
        listing_id="abc123def",
        url=SAMPLE_URL,
    )

    with respx.mock() as mock, patch.object(
        llm_parser.settings, "openrouter_api_key", "fake-key"
    ):
        mock.post("https://openrouter.ai/api/v1/chat/completions").mock(
            side_effect=[
                # Pass 1 — empty HTML, returns nothing usable.
                httpx.Response(200, json=_make_llm_response()),
                # Pass 2 — fills the real gaps AND tries to clobber slug fields.
                httpx.Response(
                    200,
                    json=_make_llm_response(
                        price_inr=99_000_000,
                        area_sqft=9999,
                        bhk=99,            # tries to overwrite slug bhk=3
                        locality="Wrong",  # tries to overwrite slug locality
                    ),
                ),
            ]
        )
        mock.get(SAMPLE_URL).mock(
            return_value=httpx.Response(
                200,
                text='<meta property="og:title" content="signal">',
            )
        )
        mock.post("https://html.duckduckgo.com/html/").mock(
            return_value=httpx.Response(200, text="<html></html>")
        )
        mock.get("https://archive.org/wayback/available").mock(
            return_value=httpx.Response(200, json={"archived_snapshots": {}})
        )

        out = await apply_post_fetch_enrichment(listing, "<html></html>", SAMPLE_URL)

    # Slug-set fields are untouched by pass 2.
    assert out.bhk == 3
    assert out.locality == "Whitefield"
    # Genuine gaps (price, area) filled by pass 2.
    assert out.price_inr == 99_000_000
    assert out.area_sqft == 9999
