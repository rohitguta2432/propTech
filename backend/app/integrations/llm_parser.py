"""LLM-based parsing fallback for portal scrapers.

Uses **Gemma 4 31B via OpenRouter** (free tier, $0/M tokens) to extract
structured listing fields from raw HTML when the per-portal regex parser
left key fields blank. Keeps the system rules-first, LLM-second:

- regex parser runs first (deterministic, free, no network)
- LLM only fires if more than half of {price_inr, area_sqft, bhk, locality}
  are still None after regex
- LLM result is *merged* into the partial — regex wins on any field both
  produced; LLM only fills gaps

If `OPENROUTER_API_KEY` is unset, this module is a no-op (returns the
partial unchanged).
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.config import settings
from app.scrapers.base import ScrapedListing

logger = logging.getLogger(__name__)

# Truncate HTML before sending — keep cost predictable + within model context.
_MAX_HTML_CHARS = 12_000

# Strip script/style/nav before sending — they're noise.
_STRIP_TAGS_RE = re.compile(
    r"<(script|style|noscript|svg|iframe)\b[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)

_PROMPT = """You are extracting structured property listing data from raw HTML.

Return ONLY a single JSON object. No prose, no markdown fences, no commentary.

Required fields (use null if not derivable from the HTML):
- title: string | null         (e.g. "3 BHK Apartment in Whitefield, Bangalore")
- price_inr: integer | null    (full rupees; convert "₹1.2 Cr" → 12000000, "85 Lakh" → 8500000)
- bhk: integer | null          (number of bedrooms)
- area_sqft: integer | null    (carpet area or built-up; pick the larger if both shown)
- locality: string | null      (e.g. "Whitefield")
- city: string | null          (e.g. "Bangalore")
- state: string | null         (e.g. "karnataka", lowercased)
- rera_id: string | null       (e.g. "PRM/KA/RERA/1251/446/PR/170820/001234")
- builder_name: string | null  (e.g. "Prestige Group")

If the HTML is not a property listing, return all nulls. Do not invent values.

HTML:
"""


def _needs_llm_help(listing: ScrapedListing) -> bool:
    """We only spend an LLM call if regex left big gaps."""
    key_fields = (listing.price_inr, listing.area_sqft, listing.bhk, listing.locality)
    missing = sum(1 for v in key_fields if v in (None, 0))
    return missing >= 2


def _trim_html(html: str) -> str:
    cleaned = _STRIP_TAGS_RE.sub("", html or "")
    if len(cleaned) > _MAX_HTML_CHARS:
        # Keep the first chunk — listings put the meta block early.
        cleaned = cleaned[:_MAX_HTML_CHARS]
    return cleaned


def _merge(listing: ScrapedListing, parsed: dict[str, Any]) -> ScrapedListing:
    """Fill regex-blank fields from the LLM result. Regex always wins."""

    def _take(key: str, current: Any) -> Any:
        if current not in (None, 0, ""):
            return current
        v = parsed.get(key)
        if v in (None, "", "null"):
            return current
        return v

    listing.title = _take("title", listing.title)
    listing.price_inr = _take("price_inr", listing.price_inr)
    listing.bhk = _take("bhk", listing.bhk)
    listing.area_sqft = _take("area_sqft", listing.area_sqft)
    listing.locality = _take("locality", listing.locality)
    listing.city = _take("city", listing.city)
    listing.state = _take("state", listing.state)
    listing.rera_id = _take("rera_id", listing.rera_id)
    listing.builder_name = _take("builder_name", listing.builder_name)
    return listing


async def enrich(
    html: str,
    listing: ScrapedListing,
    *,
    client: httpx.AsyncClient | None = None,
    timeout_s: float = 6.0,
) -> ScrapedListing:
    """Try to fill in fields the regex parser missed, using an LLM.

    Always returns a ScrapedListing — never raises. Set `OPENROUTER_API_KEY`
    in env to enable; otherwise this is a no-op.
    """
    if not settings.openrouter_api_key:
        return listing
    if not _needs_llm_help(listing):
        return listing
    if not html:
        return listing

    prompt = _PROMPT + _trim_html(html)
    payload = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": "You return strict JSON. No commentary."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": 600,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        # OpenRouter uses these for analytics + free-tier prioritisation.
        "HTTP-Referer": "https://propcheck.rohitraj.tech",
        "X-Title": "PropCheck",
    }

    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=timeout_s)

    try:
        try:
            resp = await client.post(
                f"{settings.openrouter_base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=timeout_s,
            )
            resp.raise_for_status()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            logger.warning("llm_parser.http_error", extra={"err": str(exc)})
            return listing

        try:
            content = resp.json()["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, ValueError) as exc:
            logger.warning("llm_parser.bad_response", extra={"err": str(exc)})
            return listing

        # Strip code-fences if the model added them despite our prompt.
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.warning(
                "llm_parser.json_decode_error",
                extra={"err": str(exc), "content_snippet": content[:200]},
            )
            return listing

        if not isinstance(parsed, dict):
            return listing

        return _merge(listing, parsed)
    finally:
        if own_client and client is not None:
            await client.aclose()
