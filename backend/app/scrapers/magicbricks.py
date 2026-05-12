"""Magicbricks portal scraper.

Implements the `PortalScraper` protocol — fetches a Magicbricks listing URL
with httpx and extracts a normalized `ScrapedListing`. Every extraction is
defensive: a parser failure on one field never prevents others from being
populated, and a network failure sets `fetch_error` instead of raising.
"""
from __future__ import annotations

import re
from typing import Iterable

import httpx
from bs4 import BeautifulSoup

from app.scrapers.base import (
    DEFAULT_HEADERS,
    DEFAULT_TIMEOUT_S,
    PortalScraper,
    ScrapedListing,
    apply_post_fetch_enrichment,
)
from app.scrapers.router import register


# ---------------------------------------------------------------------------
# Regexes — kept module-level so they compile once.
# ---------------------------------------------------------------------------

_BHK_RE = re.compile(r"(\d+)\s*BHK", re.IGNORECASE)
_AREA_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:sq\.?\s?ft|sqft|sq ft)",
    re.IGNORECASE,
)
# Karnataka RERAs start with `PRM/KA/RERA/`. Generic prefix handles `P` + path.
_RERA_RE = re.compile(
    r"(?:RERA(?:\s*ID)?\s*[:\-]?\s*)?(P[A-Z0-9/\-]{10,})",
)

# Price tokens we recognise. Order matters — match longer suffixes first.
_PRICE_NUMBER_RE = re.compile(
    r"(?:₹|Rs\.?|INR)?\s*"
    r"(\d+(?:[.,]\d+)*)\s*"
    r"(Crore|Cr|Lakh|Lac|L|K)?",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Field-level helpers — every one returns None on failure, never raises.
# ---------------------------------------------------------------------------


def _safe_text(node) -> str | None:
    """Get stripped text from a BS4 node, tolerating None."""
    if node is None:
        return None
    try:
        text = node.get_text(" ", strip=True)
        return text or None
    except Exception:
        return None


def _meta(soup: BeautifulSoup, prop: str) -> str | None:
    """Read a meta tag's content by `property` or `name`."""
    try:
        tag = soup.find("meta", attrs={"property": prop})
        if tag is None:
            tag = soup.find("meta", attrs={"name": prop})
        if tag is None:
            return None
        content = tag.get("content")
        if not content:
            return None
        return content.strip() or None
    except Exception:
        return None


def _extract_title(soup: BeautifulSoup) -> str | None:
    try:
        h1 = soup.find("h1")
        text = _safe_text(h1)
        if text:
            return text
    except Exception:
        pass
    og = _meta(soup, "og:title")
    if og:
        return og
    try:
        title = soup.find("title")
        return _safe_text(title)
    except Exception:
        return None


def _price_to_rupees(num_str: str, unit: str | None) -> int | None:
    """Convert a (number, unit) pair into integer rupees."""
    try:
        clean = num_str.replace(",", "").strip()
        value = float(clean)
    except Exception:
        return None
    multiplier = 1
    if unit:
        u = unit.lower()
        if u in {"cr", "crore"}:
            multiplier = 10_000_000
        elif u in {"lakh", "lac", "l"}:
            multiplier = 100_000
        elif u == "k":
            multiplier = 1_000
    try:
        return int(round(value * multiplier))
    except Exception:
        return None


def _extract_price(soup: BeautifulSoup, full_text: str) -> int | None:
    # Prefer an explicit price block if present.
    candidates: list[str] = []
    try:
        for sel in (
            {"class_": re.compile(r"price", re.IGNORECASE)},
            {"id": re.compile(r"price", re.IGNORECASE)},
        ):
            for node in soup.find_all(attrs=sel):
                t = _safe_text(node)
                if t:
                    candidates.append(t)
    except Exception:
        pass
    candidates.append(full_text)

    for text in candidates:
        # First try suffix-bearing forms — "₹1.20 Cr", "85 Lakh".
        for m in _PRICE_NUMBER_RE.finditer(text):
            num, unit = m.group(1), m.group(2)
            if unit:
                rupees = _price_to_rupees(num, unit)
                if rupees and rupees >= 1000:
                    return rupees
        # Then a plain comma-separated rupee number, e.g. "₹1,20,00,000".
        for m in re.finditer(r"₹\s*([\d,]{6,})", text):
            rupees = _price_to_rupees(m.group(1), None)
            if rupees and rupees >= 100_000:
                return rupees
    return None


def _extract_bhk(text: str) -> int | None:
    try:
        m = _BHK_RE.search(text)
        if not m:
            return None
        return int(m.group(1))
    except Exception:
        return None


def _extract_area(text: str) -> int | None:
    try:
        # Strip thousands separators inside numbers but keep tokens spaced.
        cleaned = re.sub(r"(\d),(\d)", r"\1\2", text)
        m = _AREA_RE.search(cleaned)
        if not m:
            return None
        return int(round(float(m.group(1))))
    except Exception:
        return None


def _extract_rera(text: str) -> str | None:
    try:
        # First scan for an explicit RERA-prefixed disclosure.
        labelled = re.search(
            r"RERA(?:\s*ID|\s*No\.?|\s*Number)?\s*[:\-]?\s*(P[A-Z0-9/\-]{10,})",
            text,
            re.IGNORECASE,
        )
        if labelled:
            return labelled.group(1).strip().rstrip("./,")
        # Fall back to an unlabelled `P...` token (e.g. PRM/KA/RERA/...).
        m = _RERA_RE.search(text)
        if m:
            return m.group(1).strip().rstrip("./,")
    except Exception:
        return None
    return None


def _find_by_exact_class(soup: BeautifulSoup, name: str):
    """Find the first element whose class list contains `name` exactly."""
    try:
        return soup.find(attrs={"class": lambda c: bool(c) and name in (c if isinstance(c, list) else c.split())})
    except Exception:
        return None


def _extract_locality_city(soup: BeautifulSoup, og_title: str | None) -> tuple[str | None, str | None]:
    """Pick locality and city out of breadcrumbs / og:title / explicit blocks."""
    locality: str | None = None
    city: str | None = None

    # 1. Exact-class spans/divs win over partial matches like `.locality-info`.
    locality = _safe_text(_find_by_exact_class(soup, "locality"))
    city = _safe_text(_find_by_exact_class(soup, "city"))

    # 2. Breadcrumbs — common pattern: Home > City > Locality > Project.
    if not locality or not city:
        try:
            crumbs = soup.find(attrs={"class": re.compile(r"breadcrumb", re.IGNORECASE)})
            if crumbs is not None:
                items = [
                    _safe_text(li)
                    for li in crumbs.find_all(["li", "a", "span"])
                    if _safe_text(li)
                ]
                # Drop generic anchors.
                items = [i for i in items if i and i.lower() not in {"home", "magicbricks"}]
                if items:
                    if not city and len(items) >= 1:
                        city = items[0]
                    if not locality and len(items) >= 2:
                        locality = items[1]
        except Exception:
            pass

    # 3. og:title fallback — "3 BHK Apartment in Whitefield, Bangalore".
    if (not locality or not city) and og_title:
        try:
            after_in = re.search(r"\sin\s+(.+)$", og_title, re.IGNORECASE)
            if after_in:
                tail = after_in.group(1)
                parts = [p.strip() for p in tail.split(",") if p.strip()]
                if parts:
                    if not locality:
                        locality = parts[0]
                    if not city and len(parts) >= 2:
                        city = parts[1]
        except Exception:
            pass

    return locality, city


def _extract_builder(soup: BeautifulSoup, full_text: str) -> str | None:
    # 1. Exact-class match (e.g. `<span class="builder-name">ABC</span>`).
    for cls in ("builder-name", "developer-name", "by-builder", "builder"):
        node = _find_by_exact_class(soup, cls)
        t = _safe_text(node)
        if not t:
            continue
        cleaned = re.sub(r"^(?:By|Builder|Developer)\s*[:\-]\s*", "", t, flags=re.IGNORECASE).strip()
        # Reject obviously over-broad captures (e.g. whole sections of text).
        if cleaned and 2 <= len(cleaned) <= 120 and "\n" not in cleaned:
            return cleaned
    # 2. Regex fallback on the flattened page text.
    try:
        m = re.search(r"(?:Builder|By)\s*[:\-]\s*([A-Z][A-Za-z0-9 .&'\-]{2,80})", full_text)
        if m:
            return m.group(1).strip().rstrip(".,")
    except Exception:
        pass
    return None


def _extract_images(soup: BeautifulSoup) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    try:
        candidates: Iterable = soup.find_all("img")
        for img in candidates:
            src = img.get("src") or img.get("data-src")
            if not src:
                continue
            cls = " ".join(img.get("class") or []).lower()
            # Heuristic: only photos plausibly tied to the property.
            if not (
                "photo" in cls
                or "property" in cls
                or "gallery" in cls
                or "img-property" in cls
                or src.endswith((".jpg", ".jpeg", ".png", ".webp"))
            ):
                continue
            if src in seen:
                continue
            seen.add(src)
            urls.append(src)
            if len(urls) >= 12:
                break
    except Exception:
        pass
    return urls


def _extract_description(soup: BeautifulSoup) -> str | None:
    try:
        node = soup.find("div", attrs={"class": re.compile(r"description", re.IGNORECASE)})
        text = _safe_text(node)
        if text:
            return text[:1500]
    except Exception:
        pass
    og = _meta(soup, "og:description")
    if og:
        return og[:1500]
    return None


# ---------------------------------------------------------------------------
# Top-level parser — synchronous so tests can call without an event loop.
# ---------------------------------------------------------------------------


def _parse(html: str, url: str, listing_id: str) -> ScrapedListing:
    listing = ScrapedListing(portal="magicbricks", listing_id=listing_id, url=url)
    if not html:
        return listing
    listing.raw_html_snippet = html[:4096]

    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception as e:
        listing.fetch_error = f"parse_failed: {type(e).__name__}: {e}"
        return listing

    full_text = ""
    try:
        full_text = soup.get_text(" ", strip=True)
    except Exception:
        full_text = ""

    listing.title = _extract_title(soup)
    listing.price_inr = _extract_price(soup, full_text)
    listing.bhk = _extract_bhk(full_text)
    listing.area_sqft = _extract_area(full_text)
    listing.rera_id = _extract_rera(full_text)
    listing.builder_name = _extract_builder(soup, full_text)
    listing.image_urls = _extract_images(soup)
    listing.description = _extract_description(soup)

    og_title = _meta(soup, "og:title")
    locality, city = _extract_locality_city(soup, og_title)
    listing.locality = locality
    listing.city = city

    return listing


# ---------------------------------------------------------------------------
# Scraper class — the async fetch wraps httpx and delegates to _parse.
# ---------------------------------------------------------------------------


class MagicbricksScraper:
    portal = "magicbricks"

    async def fetch(self, url: str, listing_id: str) -> ScrapedListing:
        try:
            async with httpx.AsyncClient(
                timeout=DEFAULT_TIMEOUT_S,
                headers=DEFAULT_HEADERS,
                follow_redirects=True,
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                html = response.text
        except httpx.TimeoutException as e:
            listing = ScrapedListing(
                portal=self.portal,
                listing_id=listing_id,
                url=url,
                fetch_error=f"timeout: {type(e).__name__}: {e}",
            )
            return await apply_post_fetch_enrichment(listing, "", url)
        except httpx.HTTPStatusError as e:
            listing = ScrapedListing(
                portal=self.portal,
                listing_id=listing_id,
                url=url,
                fetch_error=f"http_status: {e.response.status_code}",
            )
            return await apply_post_fetch_enrichment(listing, "", url)
        except httpx.HTTPError as e:
            listing = ScrapedListing(
                portal=self.portal,
                listing_id=listing_id,
                url=url,
                fetch_error=f"http_error: {type(e).__name__}: {e}",
            )
            return await apply_post_fetch_enrichment(listing, "", url)
        except Exception as e:
            # Belt-and-braces — scraper must never raise.
            listing = ScrapedListing(
                portal=self.portal,
                listing_id=listing_id,
                url=url,
                fetch_error=f"fetch_failed: {type(e).__name__}: {e}",
            )
            return await apply_post_fetch_enrichment(listing, "", url)

        try:
            listing = _parse(html, url, listing_id)
        except Exception as e:
            listing = ScrapedListing(
                portal=self.portal,
                listing_id=listing_id,
                url=url,
                fetch_error=f"parse_crashed: {type(e).__name__}: {e}",
                raw_html_snippet=html[:4096] if html else None,
            )
            return await apply_post_fetch_enrichment(listing, "", url)

        # Run the full enrichment pipeline: LLM on HTML → fanout if gaps
        # remain → second LLM pass with stitched signals → confidence stamp.
        try:
            listing = await apply_post_fetch_enrichment(listing, html, url)
        except Exception as e:
            listing.fetch_error = (
                listing.fetch_error or f"enrichment_failed: {type(e).__name__}"
            )

        return listing


_instance: PortalScraper = MagicbricksScraper()


def parser() -> PortalScraper:
    return _instance


# Register on module import — the router stays the source of truth.
register("magicbricks", lambda: _instance)
