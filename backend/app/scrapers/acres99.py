"""99acres.com portal scraper.

Fetches a 99acres listing page over HTTP, parses the HTML with BeautifulSoup,
and returns a `ScrapedListing`. Every extraction is best-effort — every
exception is swallowed and the field stays `None`. Network failures set
`fetch_error` rather than raising.
"""
from __future__ import annotations

import re
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.scrapers.base import (
    DEFAULT_HEADERS,
    DEFAULT_TIMEOUT_S,
    ScrapedListing,
)
from app.scrapers.router import register


# ---------------------------------------------------------------------------
# Regex library — same shapes as Magicbricks per the spec.
# ---------------------------------------------------------------------------

# Matches "1.85 Cr", "₹ 1,85,00,000", "75 Lakh", "1.2 Crore", "85 L", etc.
# Group 1 = the numeric chunk, group 2 = the unit (or empty for plain rupees).
_PRICE_RE = re.compile(
    r"(?:₹|Rs\.?|INR)?\s*"
    r"(\d[\d,]*(?:\.\d+)?)"
    r"\s*"
    r"(Cr|Crore|Crores|Lac|Lacs|Lakh|Lakhs|L|K|Thousand)?",
    re.IGNORECASE,
)

_BHK_RE = re.compile(r"(\d+)\s*BHK", re.IGNORECASE)

_AREA_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:sq\.?\s?ft|sqft|sq ft)",
    re.IGNORECASE,
)

# RERA IDs are alphanumeric with /, -; minimum length 10 to avoid false
# positives. We require at least one digit or slash inside the captured token
# so that English words like "Disclosure" or "Registration" are not matched.
_RERA_RE = re.compile(
    r"(?:RERA(?:\s*(?:ID|Reg(?:istration)?(?:\s*No\.?)?|No\.?))?\s*[:\-]?\s*)"
    r"((?=[A-Z0-9/\-]{10,})[A-Z0-9/\-]*[/0-9][A-Z0-9/\-]*)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_text(node: Any) -> str | None:
    """Strip whitespace from a BS4 node; return None if empty/missing."""
    if node is None:
        return None
    try:
        text = node.get_text(" ", strip=True)
        return text or None
    except Exception:
        return None


def _price_to_inr(text: str) -> int | None:
    """Convert a price string to integer rupees.

    Examples
    --------
    "₹1.85 Cr"          -> 18_500_000
    "₹1,85,00,000"      -> 18_500_000
    "1.85 Crore"        -> 18_500_000
    "75 Lakh"           -> 7_500_000
    "85 L"              -> 8_500_000
    """
    if not text:
        return None
    try:
        m = _PRICE_RE.search(text)
        if not m:
            return None
        raw_num = m.group(1).replace(",", "")
        unit = (m.group(2) or "").lower()
        if not raw_num:
            return None
        value = float(raw_num)
        if unit in ("cr", "crore", "crores"):
            value *= 10_000_000
        elif unit in ("lac", "lacs", "lakh", "lakhs", "l"):
            value *= 100_000
        elif unit in ("k", "thousand"):
            value *= 1_000
        # else: plain rupees (already-formatted Indian-style "1,85,00,000")
        return int(round(value))
    except Exception:
        return None


def _extract_bhk(text: str | None) -> int | None:
    if not text:
        return None
    try:
        m = _BHK_RE.search(text)
        return int(m.group(1)) if m else None
    except Exception:
        return None


def _extract_area_sqft(text: str | None) -> int | None:
    if not text:
        return None
    try:
        m = _AREA_RE.search(text)
        if not m:
            return None
        return int(round(float(m.group(1))))
    except Exception:
        return None


def _extract_rera(text: str | None) -> str | None:
    if not text:
        return None
    try:
        m = _RERA_RE.search(text)
        return m.group(1) if m else None
    except Exception:
        return None


def _meta_content(soup: BeautifulSoup, attr: str, value: str) -> str | None:
    try:
        node = soup.find("meta", attrs={attr: value})
        if node is None:
            return None
        content = node.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

class NinetyNineAcresScraper:
    portal = "99acres"

    async def fetch(self, url: str, listing_id: str) -> ScrapedListing:
        """Fetch HTML and parse. Never raises — sets `fetch_error` on failure."""
        try:
            async with httpx.AsyncClient(
                timeout=DEFAULT_TIMEOUT_S,
                headers=DEFAULT_HEADERS,
                follow_redirects=True,
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                html = response.text
        except httpx.TimeoutException as exc:
            return ScrapedListing(
                portal=self.portal,
                listing_id=listing_id,
                url=url,
                fetch_error=f"timeout: {exc!s}",
            )
        except httpx.HTTPError as exc:
            return ScrapedListing(
                portal=self.portal,
                listing_id=listing_id,
                url=url,
                fetch_error=f"http_error: {exc!s}",
            )
        except Exception as exc:  # pragma: no cover - defensive
            return ScrapedListing(
                portal=self.portal,
                listing_id=listing_id,
                url=url,
                fetch_error=f"error: {exc!s}",
            )

        return self._parse(html, url, listing_id)

    # ---- Sync parser, easy to unit-test --------------------------------

    def _parse(self, html: str, url: str, listing_id: str) -> ScrapedListing:
        listing = ScrapedListing(
            portal=self.portal,
            listing_id=listing_id,
            url=url,
            raw_html_snippet=html[:4096] if html else None,
        )
        if not html:
            return listing

        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            try:
                soup = BeautifulSoup(html, "html.parser")
            except Exception:
                return listing

        # title — prefer h1, then og:title, then <title>
        try:
            h1 = soup.find("h1")
            listing.title = (
                _safe_text(h1)
                or _meta_content(soup, "property", "og:title")
                or _safe_text(soup.find("title"))
            )
        except Exception:
            pass

        # description — prefer og:description, then a .description block
        try:
            listing.description = _meta_content(soup, "property", "og:description")
            if not listing.description:
                desc_node = soup.find(class_=re.compile(r"description", re.I))
                listing.description = _safe_text(desc_node)
            if listing.description:
                listing.description = listing.description[:1500]
        except Exception:
            pass

        # Aggregate text we'll regex-mine for price, bhk, area, rera. We try
        # narrow blocks (factsheet) first, then fall back to the whole body.
        candidate_blocks: list[str] = []
        try:
            for selector in (
                ".factsheet",
                ".pdpFact",
                ".pdp_fact",
                ".pageComponent",
                "[class*='factsheet']",
                "[class*='Factsheet']",
            ):
                for node in soup.select(selector):
                    txt = _safe_text(node)
                    if txt:
                        candidate_blocks.append(txt)
        except Exception:
            pass

        try:
            body = soup.find("body")
            body_text = _safe_text(body) or ""
        except Exception:
            body_text = ""

        full_text = " ".join(candidate_blocks) + " " + body_text

        # price — try a price-tagged block first, then full text
        try:
            price_node = soup.find(class_=re.compile(r"price", re.I))
            price_text = _safe_text(price_node)
            listing.price_inr = _price_to_inr(price_text or "") or _price_to_inr(
                full_text
            )
        except Exception:
            pass

        # bhk
        try:
            listing.bhk = _extract_bhk(full_text) or _extract_bhk(listing.title)
        except Exception:
            pass

        # area
        try:
            listing.area_sqft = _extract_area_sqft(full_text) or _extract_area_sqft(
                listing.title
            )
        except Exception:
            pass

        # rera — look in the full text; many listings put it in a disclosure block
        try:
            rera_node = soup.find(
                class_=re.compile(r"rera|disclosure", re.I)
            )
            rera_text = _safe_text(rera_node)
            listing.rera_id = _extract_rera(rera_text or "") or _extract_rera(
                full_text
            )
        except Exception:
            pass

        # builder — prefer a precise inner class (.builderName / .developerName
        # / .agentName), then fall back to the outer block if needed.
        try:
            inner = soup.find(
                class_=re.compile(
                    r"^(?:builder|developer)Name$", re.I
                )
            )
            builder_text = _safe_text(inner)
            if not builder_text:
                outer = soup.find(
                    class_=re.compile(r"builder|developer|agent", re.I)
                )
                # Prefer the first child <p>/<span> that looks like a name.
                if outer is not None:
                    first_named = outer.find(
                        ["p", "span", "h2", "h3", "h4"],
                        class_=re.compile(r"name", re.I),
                    )
                    builder_text = _safe_text(first_named) or _safe_text(outer)
            if builder_text:
                # strip "By " / "Builder:" prefixes if present
                cleaned = re.sub(
                    r"^(?:By|Builder|Developer|Agent)\s*[:\-]?\s*",
                    "",
                    builder_text,
                    flags=re.IGNORECASE,
                ).strip()
                listing.builder_name = cleaned or builder_text
        except Exception:
            pass

        # locality / city — try og:title (often "<title> in <locality> <city>")
        # and breadcrumbs.
        try:
            og_title = _meta_content(soup, "property", "og:title") or listing.title
            locality, city = _locality_city_from_title(og_title)
            listing.locality = listing.locality or locality
            listing.city = listing.city or city
        except Exception:
            pass

        # image_urls — collect property-photo style imgs, dedup, cap at 12
        try:
            seen: set[str] = set()
            urls: list[str] = []
            for img in soup.find_all("img"):
                src = img.get("src") or img.get("data-src") or ""
                if not isinstance(src, str) or not src:
                    continue
                if src in seen:
                    continue
                seen.add(src)
                urls.append(src)
                if len(urls) >= 12:
                    break
            listing.image_urls = urls
        except Exception:
            pass

        return listing


def _locality_city_from_title(title: str | None) -> tuple[str | None, str | None]:
    """Best-effort: pull (locality, city) out of a title like
    "2 BHK Flat in Indiranagar Bangalore" or
    "2 BHK Flat in Indiranagar, Bangalore".
    """
    if not title:
        return None, None
    try:
        m = re.search(r"\bin\s+([A-Za-z][\w\s]+?)(?:\s*[,\-]\s*|\s+)([A-Z][a-zA-Z]+)\s*$", title)
        if m:
            return m.group(1).strip(), m.group(2).strip()
        # Fallback: "in Indiranagar Bangalore" with no comma — split on the
        # last word.
        m2 = re.search(r"\bin\s+(.+)$", title)
        if m2:
            tail = m2.group(1).strip().rstrip(".")
            parts = tail.replace(",", " ").split()
            if len(parts) >= 2:
                return " ".join(parts[:-1]), parts[-1]
    except Exception:
        return None, None
    return None, None


_instance = NinetyNineAcresScraper()


def parser() -> NinetyNineAcresScraper:
    """Match the convention used by parsers (factory-style accessor)."""
    return _instance


# Register on module import so `app.scrapers.router.get("99acres")` works.
register("99acres", lambda: _instance)
