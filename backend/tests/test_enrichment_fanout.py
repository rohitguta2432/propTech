"""Tests for the any-source enrichment fanout.

The fanout exists to keep PropCheck working when a portal returns a JS shell,
a 4xx, or a rate-limit interstitial. It pulls supplemental signals from
URL-slug parsing (sync), OG meta tags (social-bot UA), DuckDuckGo SERP
snippets, and the Wayback Machine, then stitches them into one blob the LLM
parser can read.

Every test here uses respx to mock HTTP so nothing hits the live internet.
"""
from __future__ import annotations

import httpx
import pytest
import respx

from app.integrations import enrichment_fanout


# ---------------------------------------------------------------------------
# URL slug parser — pure, no network.
# ---------------------------------------------------------------------------


class TestSlugParser:
    def test_magicbricks_style_url(self):
        url = (
            "https://www.magicbricks.com/propertydetails/"
            "3-bhk-apartment-flat-for-sale-in-whitefield-bangalore-pdpid-4d4234567"
        )
        slug = enrichment_fanout.parse_slug(url)
        assert slug["bhk"] == 3
        assert slug["locality"] == "Whitefield"
        assert slug["city"] == "Bangalore"
        assert slug["listing_id"] == "4d4234567"
        assert slug["property_type"] in {"apartment", "flat"}

    def test_99acres_style_url(self):
        url = (
            "https://www.99acres.com/2-bhk-flat-in-indiranagar-bangalore-"
            "for-rent-spid-X88991122"
        )
        slug = enrichment_fanout.parse_slug(url)
        assert slug["bhk"] == 2
        assert slug["locality"] == "Indiranagar"
        assert slug["city"] == "Bangalore"
        assert slug["listing_id"] == "X88991122"

    def test_url_with_hyphenated_locality(self):
        url = (
            "https://www.magicbricks.com/propertydetails/"
            "4-bhk-villa-for-sale-in-hsr-layout-bangalore-pdpid-abc123def"
        )
        slug = enrichment_fanout.parse_slug(url)
        assert slug["locality"] == "Hsr Layout"
        assert slug["city"] == "Bangalore"

    def test_url_without_recognizable_fields(self):
        slug = enrichment_fanout.parse_slug("https://example.com/random-page")
        assert slug["bhk"] is None
        assert slug["locality"] is None
        assert slug["city"] is None
        assert slug["listing_id"] is None

    def test_malformed_url_returns_empty(self):
        slug = enrichment_fanout.parse_slug("not a url at all")
        # Must not raise; all fields fall back to None.
        assert all(v is None for v in slug.values())


# ---------------------------------------------------------------------------
# Open Graph fetch — uses a social-bot UA on the original URL.
# ---------------------------------------------------------------------------


class TestOgFetch:
    @pytest.mark.asyncio
    async def test_extracts_og_tags(self):
        url = "https://www.magicbricks.com/propertydetails/x"
        html = """
        <html><head>
            <meta property="og:title" content="3 BHK Apartment in Whitefield, Bangalore">
            <meta property="og:description" content="₹1.2 Cr · 1450 sqft · East Facing">
            <meta property="og:image" content="https://cdn.example.com/p.jpg">
            <meta name="twitter:title" content="3 BHK Apartment">
        </head></html>
        """
        async with httpx.AsyncClient() as client, respx.mock() as mock:
            mock.get(url).mock(return_value=httpx.Response(200, text=html))
            blob, ok = await enrichment_fanout.fetch_og_meta(url, client)

        assert ok is True
        assert "og:title" in blob
        assert "Whitefield" in blob
        assert "1.2 Cr" in blob
        # The dedup keeps the first occurrence of each key; we just check the
        # presence of the keys we care about.
        assert "og:description" in blob
        assert "og:image" in blob

    @pytest.mark.asyncio
    async def test_falls_back_to_title_tag(self):
        url = "https://www.magicbricks.com/x"
        html = "<html><head><title>2 BHK Flat in Indiranagar Bangalore</title></head></html>"
        async with httpx.AsyncClient() as client, respx.mock() as mock:
            mock.get(url).mock(return_value=httpx.Response(200, text=html))
            blob, ok = await enrichment_fanout.fetch_og_meta(url, client)
        assert ok is True
        assert "Indiranagar" in blob

    @pytest.mark.asyncio
    async def test_returns_failure_on_4xx(self):
        url = "https://www.magicbricks.com/x"
        async with httpx.AsyncClient() as client, respx.mock() as mock:
            mock.get(url).mock(return_value=httpx.Response(403))
            blob, ok = await enrichment_fanout.fetch_og_meta(url, client)
        assert ok is False
        assert blob == ""

    @pytest.mark.asyncio
    async def test_returns_failure_on_timeout(self):
        url = "https://www.magicbricks.com/x"
        async with httpx.AsyncClient() as client, respx.mock() as mock:
            mock.get(url).mock(side_effect=httpx.TimeoutException("slow"))
            blob, ok = await enrichment_fanout.fetch_og_meta(url, client)
        assert ok is False

    @pytest.mark.asyncio
    async def test_returns_failure_on_empty_body(self):
        url = "https://www.magicbricks.com/x"
        async with httpx.AsyncClient() as client, respx.mock() as mock:
            mock.get(url).mock(return_value=httpx.Response(200, text=""))
            blob, ok = await enrichment_fanout.fetch_og_meta(url, client)
        assert ok is False


# ---------------------------------------------------------------------------
# DuckDuckGo SERP snippet.
# ---------------------------------------------------------------------------


class TestSerpFetch:
    @pytest.mark.asyncio
    async def test_extracts_snippet_text(self):
        url = "https://www.magicbricks.com/x"
        ddg_html = """
        <html><body>
            <a class="result__snippet">3 BHK Apartment <b>in Whitefield, Bangalore</b>.
               ₹1.20 Crore · 1450 sqft · 12 photos.</a>
            <a class="result__snippet">Buy 3 BHK Flats in Bangalore - Magicbricks</a>
        </body></html>
        """
        async with httpx.AsyncClient() as client, respx.mock() as mock:
            mock.post("https://html.duckduckgo.com/html/").mock(
                return_value=httpx.Response(200, text=ddg_html)
            )
            blob, ok = await enrichment_fanout.fetch_serp_snippet(url, client)

        assert ok is True
        assert "Whitefield" in blob
        assert "1.20 Crore" in blob
        # HTML tags must be stripped.
        assert "<b>" not in blob
        assert "</a>" not in blob

    @pytest.mark.asyncio
    async def test_returns_failure_when_no_snippets(self):
        url = "https://www.magicbricks.com/x"
        async with httpx.AsyncClient() as client, respx.mock() as mock:
            mock.post("https://html.duckduckgo.com/html/").mock(
                return_value=httpx.Response(200, text="<html><body>nothing</body></html>")
            )
            blob, ok = await enrichment_fanout.fetch_serp_snippet(url, client)
        assert ok is False


# ---------------------------------------------------------------------------
# Wayback Machine.
# ---------------------------------------------------------------------------


class TestWaybackFetch:
    @pytest.mark.asyncio
    async def test_pulls_recent_snapshot(self):
        url = "https://www.magicbricks.com/x"
        snap_url = "https://web.archive.org/web/20260201000000/https://www.magicbricks.com/x"
        availability = {
            "archived_snapshots": {
                "closest": {
                    "available": True,
                    "url": snap_url,
                    "timestamp": "20260201000000",
                }
            }
        }
        snap_html = "<html><body>3 BHK in Whitefield for ₹1.2 Cr</body></html>"

        async with httpx.AsyncClient() as client, respx.mock() as mock:
            mock.get("https://archive.org/wayback/available").mock(
                return_value=httpx.Response(200, json=availability)
            )
            mock.get(snap_url).mock(return_value=httpx.Response(200, text=snap_html))
            blob, ok = await enrichment_fanout.fetch_wayback(url, client)

        assert ok is True
        assert "20260201000000" in blob
        assert "fresh" in blob
        assert "Whitefield" in blob

    @pytest.mark.asyncio
    async def test_no_snapshot_available(self):
        url = "https://www.magicbricks.com/x"
        async with httpx.AsyncClient() as client, respx.mock() as mock:
            mock.get("https://archive.org/wayback/available").mock(
                return_value=httpx.Response(200, json={"archived_snapshots": {}})
            )
            blob, ok = await enrichment_fanout.fetch_wayback(url, client)
        assert ok is False

    @pytest.mark.asyncio
    async def test_handles_invalid_json(self):
        url = "https://www.magicbricks.com/x"
        async with httpx.AsyncClient() as client, respx.mock() as mock:
            mock.get("https://archive.org/wayback/available").mock(
                return_value=httpx.Response(200, text="not json")
            )
            blob, ok = await enrichment_fanout.fetch_wayback(url, client)
        assert ok is False


# ---------------------------------------------------------------------------
# Top-level orchestration.
# ---------------------------------------------------------------------------


class TestFanout:
    @pytest.mark.asyncio
    async def test_slug_only_mode(self):
        """When asked for url_slug only, no network calls happen."""
        url = (
            "https://www.magicbricks.com/propertydetails/"
            "3-bhk-apartment-in-whitefield-bangalore-pdpid-xyz123abc"
        )
        # No respx mock — so any HTTP call would fail loudly.
        bundle = await enrichment_fanout.fanout(url, sources=("url_slug",))
        assert "url_slug" in bundle.sources
        assert "og_meta" not in bundle.sources
        assert bundle.slug_locality == "Whitefield"
        assert bundle.slug_city == "Bangalore"
        assert bundle.slug_bhk == 3
        assert bundle.slug_listing_id == "xyz123abc"
        assert "Whitefield" in bundle.supplemental_text

    @pytest.mark.asyncio
    async def test_all_sources_succeed(self):
        url = (
            "https://www.magicbricks.com/propertydetails/"
            "3-bhk-apartment-in-whitefield-bangalore-pdpid-zzz999"
        )
        og_html = (
            '<meta property="og:title" content="3 BHK in Whitefield">'
            '<meta property="og:description" content="₹1.2 Cr · 1450 sqft">'
        )
        ddg_html = (
            '<a class="result__snippet">3 BHK Apartment in Whitefield, Bangalore. '
            "₹1.20 Crore · 1450 sqft.</a>"
        )
        snap_url = "https://web.archive.org/web/20260201000000/" + url
        avail = {
            "archived_snapshots": {
                "closest": {
                    "available": True,
                    "url": snap_url,
                    "timestamp": "20260201000000",
                }
            }
        }

        async with respx.mock() as mock:
            mock.get(url).mock(return_value=httpx.Response(200, text=og_html))
            mock.post("https://html.duckduckgo.com/html/").mock(
                return_value=httpx.Response(200, text=ddg_html)
            )
            mock.get("https://archive.org/wayback/available").mock(
                return_value=httpx.Response(200, json=avail)
            )
            mock.get(snap_url).mock(
                return_value=httpx.Response(200, text="<html>archived</html>")
            )
            bundle = await enrichment_fanout.fanout(url)

        assert "url_slug" in bundle.sources
        assert "og_meta" in bundle.sources
        assert "serp" in bundle.sources
        assert "wayback" in bundle.sources
        # Each source has its own section header.
        assert bundle.supplemental_text.count("<!-- SOURCE:") == 4

    @pytest.mark.asyncio
    async def test_partial_failure_returns_partial_bundle(self):
        """If SERP and Wayback fail, we still get the slug + OG signals."""
        url = (
            "https://www.magicbricks.com/propertydetails/"
            "2-bhk-flat-in-koramangala-bangalore-pdpid-aaa111bbb"
        )
        og_html = '<meta property="og:title" content="2 BHK in Koramangala">'

        async with respx.mock() as mock:
            mock.get(url).mock(return_value=httpx.Response(200, text=og_html))
            mock.post("https://html.duckduckgo.com/html/").mock(
                return_value=httpx.Response(500)
            )
            mock.get("https://archive.org/wayback/available").mock(
                side_effect=httpx.TimeoutException("slow")
            )
            bundle = await enrichment_fanout.fanout(url)

        assert "url_slug" in bundle.sources
        assert "og_meta" in bundle.sources
        assert "serp" not in bundle.sources
        assert "wayback" not in bundle.sources

    @pytest.mark.asyncio
    async def test_empty_bundle_when_everything_fails(self):
        url = "https://generic.example.com/random"
        async with respx.mock() as mock:
            mock.get(url).mock(return_value=httpx.Response(403))
            mock.post("https://html.duckduckgo.com/html/").mock(
                return_value=httpx.Response(500)
            )
            mock.get("https://archive.org/wayback/available").mock(
                return_value=httpx.Response(200, json={"archived_snapshots": {}})
            )
            bundle = await enrichment_fanout.fanout(url)

        # generic.example.com has no slug fields the parser recognises,
        # so the bundle should be effectively empty.
        assert bundle.is_empty() or bundle.sources == []
