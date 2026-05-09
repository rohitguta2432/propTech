#!/usr/bin/env python
"""Local calibration runner — Sprint 1 Day 14.

Runs the full trust pipeline against:
  1. Each per-portal fixture (real-shaped HTML in tests/fixtures/)
  2. A handful of synthetic listings (clean / suspicious / scammy) crafted to
     exercise specific signal combinations.

Prints a comparison table so we can eyeball whether the deltas in
specs/trust-engine.md produce sensible scores. Once you have real listing
URLs, drop them into REAL_URLS below — the script will fetch + parse + score.

Run from backend/:
  PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -X utf8 -m scripts.calibrate
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Make `app` importable when run as `python -m scripts.calibrate` from backend/
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import get_session_factory
from app.engine.trust_score import compute_score
from app.integrations import llm_parser
from app.scrapers import acres99, magicbricks
from app.scrapers.base import ScrapedListing


# Real URLs to calibrate against. When the local IP can fetch the page, we
# run the full pipeline. When it returns 403/404/406, we record the failure
# (typical for magicbricks/99acres anti-bot). NoBroker is the most permissive
# of the four portals as of 2026-05-09.
REAL_URLS: list[str] = [
    "https://www.nobroker.in/property/buy/2-bhk-apartment-for-sale-in-hebbal-kempapura-bangalore/8a9ff2828774022f01877418b77f0d88/detail",
    "https://www.nobroker.in/property/2-bhk-apartment-for-rent-in-mathikere-bangalore-for-rs-16000/8a9f9a827cb6434f017cb6b617bb4f17/detail",
    "https://www.nobroker.in/property/2-bhk-apartment-for-rent-in-electronic-city-bangalore-for-rs-35000/ff8081816dcac7d5016dcbb2fad8554e/detail",
    "https://www.nobroker.in/property/2-bhk-apartment-for-rent-in-maragondanahalli--bangalore-for-rs-28000/8a9f8e438f848203018f84c09c68104e/detail",
    "https://www.99acres.com/3-bhk-bedroom-independent-house-villa-for-sale-in-whitefield-bangalore-east-1372-sq-ft-spid-G90542764",
    "https://www.99acres.com/3-bhk-bedroom-apartment-flat-for-sale-in-koramangala-bangalore-south-1815-sq-ft-spid-B70651770",
    "https://www.99acres.com/2-bhk-bedroom-apartment-flat-for-rent-in-indiranagar-bangalore-south-1200-sq-ft-spid-R89140775",
]


# Realistic browser headers — boost our chances against anti-bot.
_REAL_FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}


# ---------------- helpers ----------------


def parse_with(scraper_module, html: str, url: str, listing_id: str) -> ScrapedListing:
    fn = getattr(scraper_module, "_parse", None)
    if callable(fn):
        return fn(html, url, listing_id)
    return scraper_module.parser()._parse(html, url, listing_id)


def synthetic_clean() -> ScrapedListing:
    """A safe-looking 3 BHK in Whitefield at fair price."""
    return ScrapedListing(
        portal="magicbricks",
        listing_id="SYN-CLEAN-1",
        url="https://example.com/syn-clean-1",
        title="3 BHK Apartment in Whitefield, Bangalore",
        price_inr=15_500_000,   # ~Rs 10.7K/sqft, close to Whitefield 3BHK avg of 11.2K
        bhk=3,
        area_sqft=1450,
        locality="Whitefield",
        city="Bangalore",
        state="karnataka",
        rera_id="PRM/KA/RERA/1251/446/PR/170820/000123",
        builder_name="Prestige Group",
        listed_at=datetime.now(timezone.utc) - timedelta(days=14),
    )


def synthetic_below_market() -> ScrapedListing:
    """Same flat but priced 30% below market — should trigger PRICE_BELOW_MARKET."""
    listing = synthetic_clean()
    listing.listing_id = "SYN-CHEAP-2"
    listing.price_inr = 11_000_000   # 30% below 1450 * 11200 = ~16.2M
    return listing


def synthetic_no_rera_big_flat() -> ScrapedListing:
    """Big flat with no RERA — should trigger RERA_MISSING."""
    listing = synthetic_clean()
    listing.listing_id = "SYN-NORERA-3"
    listing.rera_id = None
    return listing


def synthetic_stale() -> ScrapedListing:
    """Same clean flat, listed 8 months ago — should trigger LISTING_STALE."""
    listing = synthetic_clean()
    listing.listing_id = "SYN-STALE-4"
    listing.listed_at = datetime.now(timezone.utc) - timedelta(days=240)
    return listing


def synthetic_scammy() -> ScrapedListing:
    """Multiple red flags stacked — should land deeply in 'risky'."""
    listing = synthetic_clean()
    listing.listing_id = "SYN-SCAM-5"
    listing.price_inr = 8_500_000   # ~50% below market
    listing.rera_id = None
    listing.listed_at = datetime.now(timezone.utc) - timedelta(days=300)
    return listing


# ---------------- runner ----------------


async def run_one(label: str, listing: ScrapedListing, html: str | None = None) -> dict:
    """Run trust engine + optional LLM enrich, return summary dict."""
    if html:
        listing = await llm_parser.enrich(html, listing)
    sf = get_session_factory()
    with sf() as db:
        report = await compute_score(listing, url=listing.url, db=db)
    return {
        "label": label,
        "score": report.score,
        "band": report.label,
        "summary": report.summary,
        "red_flags": [(f.code, f.severity) for f in report.red_flags],
        "green_flags": [f.code for f in report.green_flags],
        "rera": report.verifications.rera,
        "price_delta_pct": report.verifications.price_delta_pct,
        "locality_avg": report.verifications.locality_avg_price_per_sqft,
    }


async def fetch_real(url: str) -> tuple[str | None, str | None]:
    """Fetch a real listing URL with realistic headers. Return (html, error)."""
    import httpx

    try:
        async with httpx.AsyncClient(
            headers=_REAL_FETCH_HEADERS, timeout=10.0, follow_redirects=True
        ) as client:
            r = await client.get(url)
            if r.status_code != 200 or len(r.text) < 2_000:
                return None, f"HTTP {r.status_code}, {len(r.text)} bytes"
            return r.text, None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


async def run_real_url(url: str) -> dict:
    """Fetch + LLM-parse + score a real listing URL."""
    from app.parsers.router import route

    portal_route = route(url)
    portal = portal_route.portal if portal_route else "unknown"
    listing_id = portal_route.listing_id if portal_route else url[-12:]

    html, err = await fetch_real(url)
    if err or not html:
        return {
            "label": f"REAL {portal}/{listing_id}",
            "score": None,
            "band": "FETCH_ERROR",
            "summary": err,
            "red_flags": [],
            "green_flags": [],
            "rera": None,
            "price_delta_pct": None,
            "locality_avg": None,
            "url": url,
        }

    # Empty regex listing — let the LLM do the work.
    listing = ScrapedListing(portal=portal, listing_id=listing_id, url=url)
    listing = await llm_parser.enrich(html, listing)

    sf = get_session_factory()
    with sf() as db:
        report = await compute_score(listing, url=url, db=db)
    return {
        "label": f"REAL {portal}/{listing_id}",
        "score": report.score,
        "band": report.label,
        "summary": report.summary,
        "red_flags": [(f.code, f.severity) for f in report.red_flags],
        "green_flags": [f.code for f in report.green_flags],
        "rera": report.verifications.rera,
        "price_delta_pct": report.verifications.price_delta_pct,
        "locality_avg": report.verifications.locality_avg_price_per_sqft,
        "url": url,
        "extracted": {
            "title": listing.title,
            "price_inr": listing.price_inr,
            "bhk": listing.bhk,
            "area_sqft": listing.area_sqft,
            "locality": listing.locality,
            "rera_id": listing.rera_id,
        },
    }


async def main() -> int:
    rows: list[dict] = []
    fixtures = Path(__file__).parent.parent / "tests" / "fixtures"

    # --- fixture-based runs (real-shaped HTML) ---
    if (fp := fixtures / "magicbricks" / "sample-1.html").exists():
        html = fp.read_text(encoding="utf-8")
        listing = parse_with(magicbricks, html, "https://example.com/mb-fix-1", "MB-FIX-1")
        rows.append(await run_one("magicbricks-fixture", listing, html))

    if (fp := fixtures / "99acres" / "sample-1.html").exists():
        html = fp.read_text(encoding="utf-8")
        listing = parse_with(acres99, html, "https://example.com/99-fix-1", "99-FIX-1")
        rows.append(await run_one("99acres-fixture", listing, html))

    # --- real URLs (live fetch + LLM parse) ---
    # Pace so we don't trip OpenRouter free-tier per-minute caps.
    for i, url in enumerate(REAL_URLS):
        if i > 0:
            await asyncio.sleep(4)
        rows.append(await run_real_url(url))

    # --- synthetic runs (no HTML, so no LLM call) ---
    for label, factory in [
        ("syn-clean (priced fairly, RERA, fresh)", synthetic_clean),
        ("syn-below-market (30% under)", synthetic_below_market),
        ("syn-no-rera (big flat, no RERA)", synthetic_no_rera_big_flat),
        ("syn-stale (240 days old)", synthetic_stale),
        ("syn-scammy (cheap + no RERA + 300d old)", synthetic_scammy),
    ]:
        rows.append(await run_one(label, factory()))

    # --- pretty-print ---
    print()
    print("=" * 110)
    print(f"{'LABEL':45s}  {'SCORE':>5s}  {'BAND':14s}  {'FLAGS':40s}")
    print("-" * 110)
    for r in rows:
        flags = ", ".join(f"{c}:{s}" for c, s in r["red_flags"]) or "-"
        score = "-" if r["score"] is None else f"{r['score']:5d}"
        print(f"{r['label']:45s}  {score:>5s}  {r['band']:14s}  {flags[:40]}")
    print("=" * 110)
    print()
    print("Per-row detail:")
    for r in rows:
        print(f"\n[{r['label']}]")
        print(f"  score:   {r['score']} ({r['band']})")
        print(f"  summary: {r['summary']}")
        print(f"  red:     {r['red_flags'] or '[]'}")
        print(f"  green:   {r['green_flags'] or '[]'}")
        print(
            f"  signals: rera={r['rera']}, locality_avg={r['locality_avg']}, price_delta_pct={r['price_delta_pct']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
