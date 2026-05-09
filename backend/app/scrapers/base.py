"""Shared interface and shape for portal scrapers.

Every scraper returns a `ScrapedListing` with as many fields populated as it
can manage. Missing fields are `None`; the trust engine handles partial data.
Scrapers must never raise — set `fetch_error` instead.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


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
