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


# Real URLs to calibrate against (post-Railway-migration when we can scrape).
# Add 5 known-clean and 5 known-suspicious URLs here when you have them.
REAL_URLS: list[str] = []


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
    print(f"{'LABEL':45s}  {'SCORE':>5s}  {'BAND':8s}  {'FLAGS':40s}")
    print("-" * 110)
    for r in rows:
        flags = ", ".join(f"{c}:{s}" for c, s in r["red_flags"]) or "-"
        print(f"{r['label']:45s}  {r['score']:5d}  {r['band']:8s}  {flags[:40]}")
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
