"""Locality price index integration.

Stores avg ₹/sqft per (city, locality, bhk) tuple. Backed by the
``locality_prices`` Postgres table (see specs/database.md).

This is the data source for the trust engine's price-deviation signal.
The MVP seed is Bangalore-only (20 localities × 4 BHK types). New cities
can be added by appending rows to ``seeds/locality_prices_<city>.csv`` and
re-running the loader.
"""
from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.db import LocalityPrice


async def get_avg_price(
    city: str, locality: str, bhk: int, db: Session
) -> int | None:
    """Return avg ₹/sqft for ``(city, locality, bhk)`` or ``None`` if unknown.

    City and locality are matched case-insensitively. ``bhk`` must match exactly.

    The function is async to fit the integrations contract (see
    specs/integrations.md), but the underlying SQLAlchemy session is
    synchronous; the query itself runs in-process and returns quickly.
    """
    stmt = (
        select(LocalityPrice.avg_price_per_sqft)
        .where(func.lower(LocalityPrice.city) == city.lower())
        .where(func.lower(LocalityPrice.locality) == locality.lower())
        .where(LocalityPrice.bhk == bhk)
        .limit(1)
    )
    result = db.execute(stmt).scalar_one_or_none()
    return int(result) if result is not None else None


def load_seed(csv_path: str, db: Session) -> int:
    """Read a locality-price CSV and upsert each row into ``locality_prices``.

    The CSV must have header ``city,locality,bhk,avg_price_per_sqft,sample_size``.
    Rows conflicting on the unique ``(city, locality, bhk)`` key are updated
    in place; their ``refreshed_at`` is bumped to ``NOW()``.

    Returns the number of rows processed (inserted + updated).

    Caller is responsible for committing the session.
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Seed CSV not found: {csv_path}")

    rows: list[dict[str, int | str]] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        required_cols = {
            "city",
            "locality",
            "bhk",
            "avg_price_per_sqft",
            "sample_size",
        }
        if reader.fieldnames is None or not required_cols.issubset(
            set(reader.fieldnames)
        ):
            raise ValueError(
                f"CSV missing required columns. Got: {reader.fieldnames}, "
                f"need: {sorted(required_cols)}"
            )
        for raw in reader:
            rows.append(
                {
                    "city": raw["city"].strip(),
                    "locality": raw["locality"].strip(),
                    "bhk": int(raw["bhk"]),
                    "avg_price_per_sqft": int(raw["avg_price_per_sqft"]),
                    "sample_size": int(raw["sample_size"]),
                }
            )

    if not rows:
        return 0

    # Postgres-native upsert keyed by the unique (city, locality, bhk)
    # constraint named ``locality_prices_unique``.
    stmt = pg_insert(LocalityPrice).values(rows)
    stmt = stmt.on_conflict_do_update(
        constraint="locality_prices_unique",
        set_={
            "avg_price_per_sqft": stmt.excluded.avg_price_per_sqft,
            "sample_size": stmt.excluded.sample_size,
            "refreshed_at": func.now(),
        },
    )
    db.execute(stmt)
    return len(rows)
