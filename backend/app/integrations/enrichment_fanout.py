"""Any-source enrichment for blocked / SPA-shelled listing pages.

When the per-portal scraper comes back with a body that's a JavaScript shell,
a rate-limit interstitial, or a 4xx, we fall back to a fan-out of public,
free signals that survive even when the portal blocks us:

  1. URL slug parse              — locality, BHK, city, listing id are usually
                                   baked into the URL itself
                                   (`/3-bhk-flat-in-whitefield-bangalore-pid-...`)
  2. Open Graph meta fetch       — portals serve real OG tags on otherwise
                                   empty SPA shells so WhatsApp/Twitter can
                                   build link previews; we ask with a
                                   social-bot User-Agent which is normally
                                   exempt from anti-bot challenges
  3. DuckDuckGo SERP snippet     — search the exact URL, grab the snippet
                                   ("₹1.2 Cr · 3 BHK · 1450 sqft · Whitefield")
                                   from cached search results
  4. Wayback Machine snapshot    — `archive.org/wayback/available` returns the
                                   last cached version; if recent, fetch and
                                   re-use its HTML (which DID render at the
                                   time of capture)

The four fetchers run concurrently via `asyncio.gather` so even when most
fail the slow-path is bounded by the slowest single fetch. Every fetcher
returns `(label, text_blob, success)` and NEVER raises — failures become
empty contributions.

The result is a single `EnrichmentBundle` containing:
  - a stitched plain-text blob suitable for an LLM prompt, with section
    headers identifying which source contributed what
  - the list of sources that actually produced anything (used to set
    `ScrapedListing.parse_confidence`)
  - the URL-slug-derived fields, exposed separately so the caller can
    fill them deterministically without waiting on the LLM

The scoring engine is unaffected: the LLM-parser's regex-wins merge rule
still applies, so fanout output only fills holes, never overwrites.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterable
from urllib.parse import quote_plus, urlparse

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public dataclass
# ---------------------------------------------------------------------------


@dataclass
class EnrichmentBundle:
    """Everything the fanout produced for one URL."""

    # Stitched, LLM-ready text blob with `<!-- SOURCE: ... -->` separators.
    # Empty string means no source contributed.
    supplemental_text: str = ""

    # Names of the sources that produced any content (e.g. ["url_slug", "og_meta"]).
    sources: list[str] = field(default_factory=list)

    # Fields extracted deterministically from the URL slug. Safe to apply
    # to a ScrapedListing without an LLM round-trip.
    slug_locality: str | None = None
    slug_city: str | None = None
    slug_bhk: int | None = None
    slug_listing_id: str | None = None
    slug_property_type: str | None = None

    def is_empty(self) -> bool:
        return not self.supplemental_text and not self.sources


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


# Bounded so even a misbehaving SERP / Wayback can't hang the request path.
_FANOUT_TIMEOUT_S = 4.0

# WhatsApp/Twitter-style preview bot UA. Portals deliberately serve OG meta
# to these UAs even when they 403 a real browser request, because broken
# previews on social media hurt them.
_SOCIAL_BOT_UA = (
    "Mozilla/5.0 (compatible; facebookexternalhit/1.1; "
    "+http://www.facebook.com/externalhit_uatext.php)"
)

# A separate UA for SERP / Wayback so we don't look like the same blocked bot.
_GENERIC_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Wayback snapshots older than this are likely stale price data; we still use
# them for non-price fields but flag the source.
_WAYBACK_FRESH_DAYS = 180


# ---------------------------------------------------------------------------
# 1. URL slug parser — no network, runs synchronously inside the gather
# ---------------------------------------------------------------------------

# Locality is the chunk after "...in-" or "for-(sale|rent)-in-".
_SLUG_LOCALITY_RE = re.compile(
    r"(?:for-(?:sale|rent)-)?in-([a-z0-9\-]+?)(?:-(?:bangalore|mumbai|delhi|pune|hyderabad|chennai|kolkata|ahmedabad|gurgaon|noida))",
    re.IGNORECASE,
)

_SLUG_CITY_RE = re.compile(
    r"-(bangalore|mumbai|delhi|pune|hyderabad|chennai|kolkata|ahmedabad|gurgaon|noida)\b",
    re.IGNORECASE,
)

_SLUG_BHK_RE = re.compile(r"(\d+)-?bhk", re.IGNORECASE)

# Magicbricks: pdpid-4d4235363330373333. 99acres: -spid-X12345 or -PID-X12345.
# Housing/NoBroker: various trailing IDs.
_SLUG_LISTING_ID_RE = re.compile(
    r"(?:pdpid|spid|pid|listing|id)[\-_]([A-Za-z0-9]{6,})",
    re.IGNORECASE,
)

_SLUG_PROPERTY_TYPE_RE = re.compile(
    r"\b(flat|apartment|villa|plot|house|builder-floor|studio|penthouse)\b",
    re.IGNORECASE,
)


def parse_slug(url: str) -> dict[str, str | int | None]:
    """Extract whatever the URL itself encodes. Pure, no network."""
    out: dict[str, str | int | None] = {
        "locality": None,
        "city": None,
        "bhk": None,
        "listing_id": None,
        "property_type": None,
    }
    try:
        parsed = urlparse(url)
        path = parsed.path or ""
        # Lowercased path for case-insensitive matching of locality / city /
        # BHK / property type. Listing IDs preserve case (`X88991122`).
        slug_lower = path.lower()
        slug_orig = path
    except Exception:
        return out

    try:
        m = _SLUG_LOCALITY_RE.search(slug_lower)
        if m:
            out["locality"] = m.group(1).replace("-", " ").strip().title() or None
    except Exception:
        pass

    try:
        m = _SLUG_CITY_RE.search(slug_lower)
        if m:
            out["city"] = m.group(1).title()
    except Exception:
        pass

    try:
        m = _SLUG_BHK_RE.search(slug_lower)
        if m:
            out["bhk"] = int(m.group(1))
    except Exception:
        pass

    # Listing ID — case-preserving. Portals often use mixed-case IDs.
    try:
        m = _SLUG_LISTING_ID_RE.search(slug_orig)
        if m:
            out["listing_id"] = m.group(1)
    except Exception:
        pass

    try:
        m = _SLUG_PROPERTY_TYPE_RE.search(slug_lower)
        if m:
            out["property_type"] = m.group(1).lower()
    except Exception:
        pass

    return out


def _slug_to_blob(slug: dict[str, str | int | None], url: str) -> str:
    """Format slug parse into LLM-readable lines."""
    lines = [f"Source URL: {url}"]
    if slug.get("locality"):
        lines.append(f"Locality (from URL): {slug['locality']}")
    if slug.get("city"):
        lines.append(f"City (from URL): {slug['city']}")
    if slug.get("bhk"):
        lines.append(f"BHK (from URL): {slug['bhk']}")
    if slug.get("property_type"):
        lines.append(f"Property type (from URL): {slug['property_type']}")
    if slug.get("listing_id"):
        lines.append(f"Portal listing id (from URL): {slug['listing_id']}")
    return "\n".join(lines) if len(lines) > 1 else ""


# ---------------------------------------------------------------------------
# 2. OG meta fetch — same URL, social-bot UA
# ---------------------------------------------------------------------------

# Tolerant regex matchers — we are NOT going to spin up BeautifulSoup again
# for what is usually a handful of <meta> tags.
_OG_TAG_RE = re.compile(
    r"""<meta\s+(?:property|name)\s*=\s*["'](og:[a-z:]+|twitter:[a-z:]+|description)["']\s+content\s*=\s*["']([^"']{1,800})["']""",
    re.IGNORECASE,
)

_TITLE_TAG_RE = re.compile(r"<title[^>]*>([^<]{1,400})</title>", re.IGNORECASE)


async def fetch_og_meta(url: str, client: httpx.AsyncClient) -> tuple[str, bool]:
    """Try to grab OG / Twitter meta tags via a social-bot UA request.

    Returns `(blob, success)`. Never raises.
    """
    try:
        resp = await client.get(
            url,
            headers={
                "User-Agent": _SOCIAL_BOT_UA,
                "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                "Accept-Language": "en-IN,en;q=0.9",
            },
            timeout=_FANOUT_TIMEOUT_S,
            follow_redirects=True,
        )
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        logger.debug("fanout.og.http_error", extra={"err": str(exc)})
        return "", False

    if resp.status_code >= 400:
        return "", False

    html = resp.text or ""
    if not html:
        return "", False

    pairs: list[tuple[str, str]] = []
    try:
        for m in _OG_TAG_RE.finditer(html):
            pairs.append((m.group(1).strip().lower(), m.group(2).strip()))
    except Exception:
        return "", False

    if not pairs:
        # Sometimes the only useful thing is the <title>.
        try:
            tm = _TITLE_TAG_RE.search(html)
            if tm:
                pairs.append(("title", tm.group(1).strip()))
        except Exception:
            pass

    if not pairs:
        return "", False

    seen: set[str] = set()
    lines: list[str] = []
    for key, value in pairs:
        if not value or key in seen:
            continue
        seen.add(key)
        lines.append(f"{key}: {value}")

    if not lines:
        return "", False
    return "\n".join(lines), True


# ---------------------------------------------------------------------------
# 3. DuckDuckGo SERP snippet — works without an API key
# ---------------------------------------------------------------------------

# DuckDuckGo HTML endpoint. Bing has a similar shape but is more aggressive
# about blocking; DDG is the gentler default.
_DDG_HTML_ENDPOINT = "https://html.duckduckgo.com/html/"

# We only need the snippet bodies, not the full SERP — these regexes are
# narrow on purpose so they don't pick up nav chrome.
_DDG_RESULT_BLOCK_RE = re.compile(
    r"""<a[^>]*class=["'][^"']*result__snippet[^"']*["'][^>]*>(.*?)</a>""",
    re.IGNORECASE | re.DOTALL,
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def _strip_html(s: str) -> str:
    return _WHITESPACE_RE.sub(" ", _HTML_TAG_RE.sub(" ", s)).strip()


async def fetch_serp_snippet(url: str, client: httpx.AsyncClient) -> tuple[str, bool]:
    """Ask DuckDuckGo what it cached for this exact URL."""
    try:
        query = f'"{url}"'
        resp = await client.post(
            _DDG_HTML_ENDPOINT,
            data={"q": query},
            headers={
                "User-Agent": _GENERIC_UA,
                "Accept": "text/html",
                "Accept-Language": "en-IN,en;q=0.9",
            },
            timeout=_FANOUT_TIMEOUT_S,
        )
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        logger.debug("fanout.serp.http_error", extra={"err": str(exc)})
        return "", False

    if resp.status_code >= 400:
        return "", False

    html = resp.text or ""
    if not html:
        return "", False

    snippets: list[str] = []
    try:
        for m in _DDG_RESULT_BLOCK_RE.finditer(html):
            text = _strip_html(m.group(1))
            if text and len(text) >= 20:
                snippets.append(text)
            if len(snippets) >= 5:
                break
    except Exception:
        return "", False

    if not snippets:
        return "", False
    return "\n---\n".join(snippets), True


# ---------------------------------------------------------------------------
# 4. Wayback Machine snapshot
# ---------------------------------------------------------------------------

_WAYBACK_AVAILABLE_ENDPOINT = "https://archive.org/wayback/available"

# Cap on the Wayback HTML chunk we forward to the LLM — same budget as the
# regular HTML truncation in `llm_parser`.
_WAYBACK_MAX_CHARS = 20_000


async def fetch_wayback(url: str, client: httpx.AsyncClient) -> tuple[str, bool]:
    """Pull the most recent snapshot of `url`, if one exists, and excerpt it."""
    try:
        resp = await client.get(
            _WAYBACK_AVAILABLE_ENDPOINT,
            params={"url": url},
            headers={"User-Agent": _GENERIC_UA, "Accept": "application/json"},
            timeout=_FANOUT_TIMEOUT_S,
        )
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        logger.debug("fanout.wayback.lookup_error", extra={"err": str(exc)})
        return "", False

    if resp.status_code >= 400:
        return "", False

    try:
        data = resp.json()
    except ValueError:
        return "", False

    try:
        snapshot = (data or {}).get("archived_snapshots", {}).get("closest", {})
        if not snapshot or not snapshot.get("available"):
            return "", False
        snap_url = snapshot.get("url") or ""
        snap_ts = snapshot.get("timestamp") or ""
        if not snap_url:
            return "", False
    except Exception:
        return "", False

    # Best-effort freshness flag — we still use stale snapshots, but mark them.
    fresh = True
    try:
        if snap_ts and len(snap_ts) >= 8:
            snap_dt = datetime.strptime(snap_ts[:14], "%Y%m%d%H%M%S").replace(
                tzinfo=timezone.utc
            )
            fresh = (datetime.now(timezone.utc) - snap_dt) <= timedelta(
                days=_WAYBACK_FRESH_DAYS
            )
    except Exception:
        fresh = False

    # Pull the raw snapshot — wayback serves the original HTML with a banner.
    try:
        snap_resp = await client.get(
            snap_url,
            headers={"User-Agent": _GENERIC_UA},
            timeout=_FANOUT_TIMEOUT_S,
            follow_redirects=True,
        )
    except (httpx.HTTPError, httpx.TimeoutException):
        return "", False

    if snap_resp.status_code >= 400:
        return "", False

    snap_html = snap_resp.text or ""
    if not snap_html:
        return "", False

    excerpt = snap_html[:_WAYBACK_MAX_CHARS]
    freshness_note = "fresh" if fresh else "stale (>180 days)"
    header = f"Wayback snapshot ({snap_ts}, {freshness_note}): {snap_url}\n"
    return header + excerpt, True


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------


async def fanout(
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
    sources: Iterable[str] = ("url_slug", "og_meta", "serp", "wayback"),
    overall_timeout_s: float = _FANOUT_TIMEOUT_S * 1.5,
) -> EnrichmentBundle:
    """Run the four fetchers concurrently and stitch their outputs.

    Never raises. Returns an empty bundle if everything failed or timed out.
    """
    bundle = EnrichmentBundle()

    # 1. URL slug — always run, no network cost.
    slug = parse_slug(url)
    bundle.slug_locality = slug.get("locality") if isinstance(slug.get("locality"), str) else None  # type: ignore[assignment]
    bundle.slug_city = slug.get("city") if isinstance(slug.get("city"), str) else None  # type: ignore[assignment]
    bundle.slug_bhk = slug.get("bhk") if isinstance(slug.get("bhk"), int) else None  # type: ignore[assignment]
    bundle.slug_listing_id = (
        slug.get("listing_id") if isinstance(slug.get("listing_id"), str) else None
    )  # type: ignore[assignment]
    bundle.slug_property_type = (
        slug.get("property_type")
        if isinstance(slug.get("property_type"), str)
        else None
    )  # type: ignore[assignment]
    slug_blob = _slug_to_blob(slug, url) if "url_slug" in sources else ""

    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=_FANOUT_TIMEOUT_S)

    try:
        # 2-4: network sources, fired in parallel.
        tasks: dict[str, asyncio.Task] = {}
        if "og_meta" in sources:
            tasks["og_meta"] = asyncio.create_task(fetch_og_meta(url, client))
        if "serp" in sources:
            tasks["serp"] = asyncio.create_task(fetch_serp_snippet(url, client))
        if "wayback" in sources:
            tasks["wayback"] = asyncio.create_task(fetch_wayback(url, client))

        results: dict[str, tuple[str, bool]] = {}
        if tasks:
            try:
                done = await asyncio.wait_for(
                    asyncio.gather(*tasks.values(), return_exceptions=True),
                    timeout=overall_timeout_s,
                )
                for (name, _task), result in zip(tasks.items(), done):
                    if isinstance(result, Exception):
                        logger.debug(
                            "fanout.source_exception",
                            extra={"src": name, "err": str(result)},
                        )
                        continue
                    results[name] = result  # type: ignore[assignment]
            except asyncio.TimeoutError:
                logger.info("fanout.overall_timeout", extra={"url": url})
                for name, task in tasks.items():
                    if task.done() and not task.cancelled():
                        try:
                            results[name] = task.result()
                        except Exception:
                            pass
                    else:
                        task.cancel()
    finally:
        if own_client and client is not None:
            try:
                await client.aclose()
            except Exception:
                pass

    blocks: list[str] = []
    if slug_blob:
        blocks.append(f"<!-- SOURCE: url_slug -->\n{slug_blob}")
        bundle.sources.append("url_slug")

    for src in ("og_meta", "serp", "wayback"):
        blob, ok = results.get(src, ("", False))
        if ok and blob:
            blocks.append(f"<!-- SOURCE: {src} -->\n{blob}")
            bundle.sources.append(src)

    bundle.supplemental_text = "\n\n".join(blocks)
    return bundle
