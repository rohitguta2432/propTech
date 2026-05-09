#!/usr/bin/env python
"""Run once after migrations: python -m scripts.seed_locality_prices

Loads the curated locality-price seeds for all supported cities. Each CSV
is upserted independently into the ``locality_prices`` table; conflicts on
``(city, locality, bhk)`` update the existing row in place.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import get_session_factory
from app.integrations.locality_prices import load_seed

CITIES = ["bangalore", "mumbai", "delhi", "pune", "hyderabad"]

seeds_dir = Path(__file__).parent.parent / "seeds"
sf = get_session_factory()
with sf() as db:
    total = 0
    for city in CITIES:
        csv_path = seeds_dir / f"locality_prices_{city}.csv"
        n = load_seed(str(csv_path), db)
        total += n
        print(f"  {city}: {n} rows")
    db.commit()
    print(f"Upserted {total} rows across {len(CITIES)} cities.")
