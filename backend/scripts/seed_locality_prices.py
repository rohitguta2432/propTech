#!/usr/bin/env python
"""Run once after migrations: python -m scripts.seed_locality_prices"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import get_session_factory
from app.integrations.locality_prices import load_seed

csv_path = Path(__file__).parent.parent / "seeds" / "locality_prices_bangalore.csv"
sf = get_session_factory()
with sf() as db:
    n = load_seed(str(csv_path), db)
    db.commit()
    print(f"Upserted {n} rows.")
