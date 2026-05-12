"""Shared interface and shape for portal scrapers.

Every scraper returns a `ScrapedListing` with as many fields populated as it
can manage. Missing fields are `None`; the trust engine handles partial data.
Scrapers must never raise — set `fetch_error` instead.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ScrapedListing:
    portal: str
    listing_id: str
    url: str

    # Best-effort fields. None = "couldn't extract".
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
    image_urls: list[str] = field(default_factory=list)
    description: str | None = None
    raw_html_snippet: str | None = None
    fetch_error: str | None = None

    # How much we trust the populated fields:
    #   "high"   = direct HTML parsed cleanly (regex + LLM on real page body)
    #   "medium" = portal page was a shell/blocked, but OG meta + SERP snippet
    #              + Wayback stitched enough for the LLM to fill key fields
    #   "low"    = only the URL slug yielded anything; score must be clamped
    # None = parser did not record it (treat as "unknown", behave like high
    # for back-compat with code paths that pre-date the field).
    parse_confidence: str | None = None
    enrichment_sources: list[str] = field(default_factory=list)


class PortalScraper(Protocol):
    portal: str

    async def fetch(self, url: str, listing_id: str) -> ScrapedListing: ...


# Common HTTP defaults — every scraper should reuse these.
DEFAULT_TIMEOUT_S = 5.0
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}


# ---------------------------------------------------------------------------
# Post-fetch enrichment pipeline.
#
# This runs after a scraper has produced its best regex-based `ScrapedListing`
# from whatever HTML it could fetch. It orchestrates:
#
#   1. First LLM pass on the direct HTML.                  (fills regex gaps)
#   2. If gaps remain (or the page was blocked entirely),
#      fan out to free public signals (URL slug, OG meta,
#      DuckDuckGo SERP snippet, Wayback snapshot) and run
#      a second LLM pass with both blobs.
#   3. Stamp `parse_confidence` so the trust engine can
#      clamp scores when data quality is poor.
#
# Confidence policy (kept deliberately simple, easy to tweak after calibration):
#   - "high"   : direct HTML was reachable AND every key field is populated.
#   - "medium" : enrichment from non-HTML sources contributed to the fill, OR
#                key fields are still partially missing after the HTML pass.
#   - "low"    : after both passes, half or more key fields are still blank.
#                The trust engine should refuse to assign a numeric score and
#                show "Not enough data" instead.
# ---------------------------------------------------------------------------


_KEY_FIELDS = ("price_inr", "area_sqft", "bhk", "locality")


def _key_field_gaps(listing: "ScrapedListing") -> int:
    return sum(
        1
        for f in _KEY_FIELDS
        if getattr(listing, f, None) in (None, 0, "")
    )


async def apply_post_fetch_enrichment(
    listing: "ScrapedListing",
    html: str,
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> "ScrapedListing":
    """Run LLM + (optionally) fanout enrichment on a freshly-scraped listing.

    Always returns a ScrapedListing. Never raises — every failure path leaves
    the listing in whatever state it was already in, with `parse_confidence`
    set so downstream code knows how much to trust it.
    """
    # Imports here, not at module top, so test patches of
    # `app.integrations.llm_parser.settings` keep working without import-cycle
    # complications between scrapers.base and the integrations package.
    from app.config import settings
    from app.integrations import enrichment_fanout, llm_parser

    started_with_http_error = bool(listing.fetch_error)
    # Network fanout sources (OG, SERP, Wayback) are only useful as LLM input;
    # gate them on the LLM key. The URL-slug parse is sync and always runs,
    # since slug fields are deterministic and we apply them directly.
    network_fanout_enabled = bool(settings.openrouter_api_key)

    # ---- Pass 1: LLM on direct HTML ---------------------------------------
    try:
        listing = await llm_parser.enrich(html, listing, client=client)
    except Exception as exc:  # never let the LLM break the scrape path
        logger.warning("enrichment.llm_pass1_failed", extra={"err": str(exc)})

    gaps_after_pass_1 = _key_field_gaps(listing)

    # ---- Decide whether to fan out ----------------------------------------
    # Fan out if: the HTML fetch failed entirely, OR we still have 2+ key
    # gaps after the first LLM pass. The threshold matches `_needs_llm_help`.
    must_fanout = started_with_http_error or gaps_after_pass_1 >= 2

    fanout_sources: list[str] = []
    if must_fanout:
        sources = (
            ("url_slug", "og_meta", "serp", "wayback")
            if network_fanout_enabled
            else ("url_slug",)
        )
        try:
            bundle = await enrichment_fanout.fanout(
                url, client=client, sources=sources
            )
        except Exception as exc:
            logger.warning("enrichment.fanout_failed", extra={"err": str(exc)})
            bundle = None

        if bundle is not None and not bundle.is_empty():
            fanout_sources = list(bundle.sources)

            # Apply slug-derived fields directly. These come from the URL
            # itself, so they're as deterministic as a regex parse — no
            # reason to wait on the LLM to surface them.
            if listing.locality in (None, "") and bundle.slug_locality:
                listing.locality = bundle.slug_locality
            if listing.city in (None, "") and bundle.slug_city:
                listing.city = bundle.slug_city
            if listing.bhk in (None, 0) and bundle.slug_bhk:
                listing.bhk = bundle.slug_bhk
            if not listing.listing_id and bundle.slug_listing_id:
                listing.listing_id = bundle.slug_listing_id

            # ---- Pass 2: LLM with HTML + supplemental blob ----------------
            try:
                listing = await llm_parser.enrich(
                    html,
                    listing,
                    client=client,
                    supplemental=bundle.supplemental_text,
                )
            except Exception as exc:
                logger.warning(
                    "enrichment.llm_pass2_failed", extra={"err": str(exc)}
                )

    # ---- Stamp confidence -------------------------------------------------
    listing.enrichment_sources = fanout_sources
    final_gaps = _key_field_gaps(listing)

    if final_gaps >= 2:
        listing.parse_confidence = "low"
    elif fanout_sources and final_gaps >= 1:
        listing.parse_confidence = "medium"
    elif fanout_sources:
        # Fanout was used and got us to fully-populated key fields, but the
        # direct page didn't render — treat that as medium, not high.
        listing.parse_confidence = "medium"
    elif started_with_http_error:
        # No HTML, no fanout signals — we're operating blind.
        listing.parse_confidence = "low"
    else:
        listing.parse_confidence = "high"

    return listing
