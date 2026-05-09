"""Tests for the locality_prices integration.

Covers four behaviours:

1. ``get_avg_price`` returns the stored value for a known (city, locality, bhk).
2. ``get_avg_price`` returns ``None`` when the tuple is unknown.
3. ``get_avg_price`` matches city / locality case-insensitively.
4. ``load_seed`` upserts a tiny CSV and the rows show up via the ORM.

The DB fixture uses the project's real Postgres (Supabase) session factory.
Each test cleans up after itself via a transaction-style row delete to keep
the table free of test pollution. If the DATABASE_URL isn't reachable, the
tests skip rather than fail — useful for offline development.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import OperationalError, SQLAlchemyError

# Make `app.*` importable when pytest is run from `backend/`.
_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.db.session import get_session_factory  # noqa: E402
from app.integrations.locality_prices import (  # noqa: E402
    get_avg_price,
    load_seed,
)
from app.models.db import LocalityPrice  # noqa: E402


# Markers used to keep test rows clearly separable from the seeded
# Bangalore data and from each other.
_TEST_CITY = "TestCity"
_TEST_LOCALITY = "TestLocality"
_TEST_LOAD_LOCALITY = "TestLoadLocality"


@pytest.fixture
def db():
    """Yield a SQLAlchemy session bound to the configured DATABASE_URL.

    Skips the test if the database isn't reachable so the suite can still
    pass on machines without Supabase credentials.
    """
    try:
        sf = get_session_factory()
    except RuntimeError as exc:  # DATABASE_URL not configured
        pytest.skip(f"DB not configured: {exc}")
    session = sf()
    try:
        # Probe the connection; bail out cleanly on network failure.
        session.execute(delete(LocalityPrice).where(LocalityPrice.city == _TEST_CITY))
        session.commit()
    except (OperationalError, SQLAlchemyError) as exc:
        session.close()
        pytest.skip(f"DB unreachable: {exc}")
        return  # pragma: no cover
    try:
        yield session
    finally:
        # Clean up any rows we added during the test.
        try:
            session.execute(
                delete(LocalityPrice).where(LocalityPrice.city == _TEST_CITY)
            )
            session.commit()
        except SQLAlchemyError:
            session.rollback()
        session.close()


def _seed_one(db, city: str, locality: str, bhk: int, price: int, sample: int) -> None:
    db.add(
        LocalityPrice(
            city=city,
            locality=locality,
            bhk=bhk,
            avg_price_per_sqft=price,
            sample_size=sample,
        )
    )
    db.commit()


def test_get_avg_price_returns_value(db):
    """A seeded row is found and its avg price is returned."""
    _seed_one(db, _TEST_CITY, _TEST_LOCALITY, 2, 9876, 100)

    result = asyncio.run(get_avg_price(_TEST_CITY, _TEST_LOCALITY, 2, db))

    assert result == 9876


def test_get_avg_price_none_for_unknown(db):
    """Unknown city/locality returns None, not an exception."""
    result = asyncio.run(
        get_avg_price("NoSuchCity", "NoSuchLocality", 3, db)
    )

    assert result is None


def test_get_avg_price_case_insensitive(db):
    """Lookup is case-insensitive on city and locality."""
    _seed_one(db, _TEST_CITY, _TEST_LOCALITY, 2, 11111, 50)

    # Lowercase the city + locality and confirm we still hit the row.
    result = asyncio.run(
        get_avg_price(_TEST_CITY.lower(), _TEST_LOCALITY.lower(), 2, db)
    )
    # And mixed case for good measure.
    result_mixed = asyncio.run(
        get_avg_price(_TEST_CITY.upper(), _TEST_LOCALITY.swapcase(), 2, db)
    )

    assert result == 11111
    assert result_mixed == 11111


def test_load_seed_csv_upserts(tmp_path, db):
    """A small CSV is loaded and the rows show up in the DB."""
    csv_path = tmp_path / "tiny.csv"
    csv_path.write_text(
        "city,locality,bhk,avg_price_per_sqft,sample_size\n"
        f"{_TEST_CITY},{_TEST_LOAD_LOCALITY},1,5000,10\n"
        f"{_TEST_CITY},{_TEST_LOAD_LOCALITY},2,5500,20\n"
        f"{_TEST_CITY},{_TEST_LOAD_LOCALITY},3,6000,30\n",
        encoding="utf-8",
    )

    n = load_seed(str(csv_path), db)
    db.commit()

    assert n == 3

    # Verify the rows are queryable.
    one_bhk = asyncio.run(
        get_avg_price(_TEST_CITY, _TEST_LOAD_LOCALITY, 1, db)
    )
    two_bhk = asyncio.run(
        get_avg_price(_TEST_CITY, _TEST_LOAD_LOCALITY, 2, db)
    )
    three_bhk = asyncio.run(
        get_avg_price(_TEST_CITY, _TEST_LOAD_LOCALITY, 3, db)
    )

    assert one_bhk == 5000
    assert two_bhk == 5500
    assert three_bhk == 6000

    # Re-load with new prices to verify upsert semantics (no duplicate insert).
    csv_path.write_text(
        "city,locality,bhk,avg_price_per_sqft,sample_size\n"
        f"{_TEST_CITY},{_TEST_LOAD_LOCALITY},1,5050,15\n",
        encoding="utf-8",
    )
    n2 = load_seed(str(csv_path), db)
    db.commit()
    assert n2 == 1
    one_bhk_after = asyncio.run(
        get_avg_price(_TEST_CITY, _TEST_LOAD_LOCALITY, 1, db)
    )
    assert one_bhk_after == 5050
