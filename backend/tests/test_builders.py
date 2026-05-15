"""Tests for /v1/builders/{slug} + /v1/builders/recent.

Each saved check becomes a permanent /check/<id>; each *builder* mentioned
across those checks becomes a permanent /builder/<slug>. These tests cover:

  - Slug normalization (suffix stripping, casing, punctuation collapse)
  - The happy path: aggregated stats across multiple checks
  - 404 paths (unknown slug, oversized slug)
  - Cross-spelling collapse — "Prestige Estates" + "PRESTIGE ESTATES LTD"
    resolve to the same builder
  - RERA + complaint roll-up by matched builder names
  - /v1/builders/recent shape + dedupe
"""
from __future__ import annotations

import sys
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.middleware.rate_limit import limiter  # noqa: E402
from app.models.db import BuilderComplaint, Check, RERARecord  # noqa: E402
from app.util.slug import to_slug  # noqa: E402


@pytest.fixture()
def shared_db() -> Generator[Session, None, None]:
    """Single in-memory SQLite shared across the test and the FastAPI app."""
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def _override() -> Generator[Session, None, None]:
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    limiter.reset()
    app.dependency_overrides[get_db] = _override
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        app.dependency_overrides.clear()
        engine.dispose()


def _make_check(
    db: Session,
    *,
    check_id: str,
    builder_name: str | None,
    score: int = 70,
    label: str = "safe",
    city: str | None = "Bangalore",
    locality: str | None = "Whitefield",
    state: str | None = "karnataka",
    checked_at: datetime | None = None,
) -> Check:
    row = Check(
        id=check_id,
        portal="magicbricks",
        listing_id=check_id,
        url=f"https://www.magicbricks.com/{check_id}",
        score=score,
        label=label,
        summary="Test check.",
        red_flags=[],
        green_flags=[],
        checklist=[],
        verifications={"parse_confidence": "high"},
        property_data={
            "portal": "magicbricks",
            "listing_id": check_id,
            "title": f"3 BHK in {locality}",
            "price_inr": 12_000_000,
            "bhk": 3,
            "area_sqft": 1450,
            "locality": locality,
            "city": city,
            "state": state,
            "rera_id": None,
            "builder_name": builder_name,
            "listed_at": None,
        },
        cache_hit=False,
        source_surface="web",
        requester_ip=None,
        user_agent=None,
        checked_at=checked_at or datetime.now(UTC),
    )
    db.add(row)
    db.commit()
    return row


# ---------- slug helper ----------


def test_slug_strips_corporate_suffixes() -> None:
    assert to_slug("Prestige Estates Projects Ltd") == "prestige"
    assert to_slug("Prestige Estates Projects Private Limited") == "prestige"
    assert to_slug("PRESTIGE  ESTATES   PROJECTS") == "prestige"


def test_slug_collapses_casing_and_punctuation() -> None:
    assert to_slug("Sobha Limited") == "sobha"
    assert to_slug("sobha-ltd.") == "sobha"
    assert to_slug("L&T  Realty") == "l-t"


def test_slug_returns_none_for_empty_or_garbage() -> None:
    assert to_slug(None) is None
    assert to_slug("") is None
    assert to_slug("   ") is None
    # All-suffix input has nothing left after stripping.
    assert to_slug("Ltd") is None


# ---------- /v1/builders/{slug} ----------


def test_builder_returns_aggregated_profile(shared_db: Session) -> None:
    _make_check(shared_db, check_id="c1", builder_name="Prestige Estates", score=80, label="safe")
    _make_check(shared_db, check_id="c2", builder_name="Prestige Estates", score=60, label="caution")
    _make_check(shared_db, check_id="c3", builder_name="PRESTIGE ESTATES PROJECTS LTD", score=40, label="risky")

    client = TestClient(app)
    resp = client.get("/v1/builders/prestige")
    assert resp.status_code == 200
    body = resp.json()

    assert body["slug"] == "prestige"
    assert body["total_checks"] == 3
    assert body["avg_score"] == 60  # round((80+60+40)/3) = 60
    assert body["label_breakdown"] == {"safe": 1, "caution": 1, "risky": 1}
    # Display name picks the most-common spelling. Two checks have
    # "Prestige Estates", one has the LTD variant, so the bare form wins.
    assert body["name"] == "Prestige Estates"
    assert "PRESTIGE ESTATES PROJECTS LTD" in body["aliases"]
    # All three checks share city/state.
    assert body["cities"] == ["Bangalore"]
    assert body["states"] == ["karnataka"]
    # recent_checks ordered newest-first, with key fields populated.
    assert len(body["recent_checks"]) == 3
    assert {r["id"] for r in body["recent_checks"]} == {"c1", "c2", "c3"}


def test_builder_rolls_up_rera_and_complaints(shared_db: Session) -> None:
    _make_check(shared_db, check_id="c1", builder_name="Sobha Limited")
    shared_db.add(
        RERARecord(
            state="karnataka",
            rera_id="PRM/KA/RERA/1251/309/PR/180101/001234",
            project_name="Sobha Dream Acres",
            builder_name="Sobha Limited",
            status="active",
        )
    )
    shared_db.add(
        BuilderComplaint(
            builder_name="Sobha Limited",
            state="karnataka",
            open_count=3,
            closed_count=7,
            delays_count=1,
        )
    )
    shared_db.commit()

    client = TestClient(app)
    resp = client.get("/v1/builders/sobha")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["rera_records"]) == 1
    assert body["rera_records"][0]["project_name"] == "Sobha Dream Acres"
    assert body["complaints"]["open"] == 3
    assert body["complaints"]["closed"] == 7
    assert body["complaints"]["delays"] == 1
    assert body["complaints"]["by_state"][0]["state"] == "karnataka"


def test_builder_404_for_unknown_slug(shared_db: Session) -> None:
    _make_check(shared_db, check_id="c1", builder_name="Prestige Estates")
    client = TestClient(app)
    resp = client.get("/v1/builders/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "BUILDER_NOT_FOUND"


def test_builder_404_for_oversized_slug(shared_db: Session) -> None:
    client = TestClient(app)
    resp = client.get("/v1/builders/" + ("x" * 200))
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "BUILDER_NOT_FOUND"


def test_builder_ignores_checks_with_no_builder_name(shared_db: Session) -> None:
    # A check with no builder shouldn't influence anything.
    _make_check(shared_db, check_id="c0", builder_name=None)
    _make_check(shared_db, check_id="c1", builder_name="Sobha")
    client = TestClient(app)
    resp = client.get("/v1/builders/sobha")
    assert resp.status_code == 200
    assert resp.json()["total_checks"] == 1


# ---------- /v1/builders/recent ----------


def test_recent_builders_dedupes_by_slug(shared_db: Session) -> None:
    base = datetime.now(UTC)
    # Three checks across two distinct builders, all dedupe by slug.
    _make_check(shared_db, check_id="c1", builder_name="Prestige Estates", checked_at=base - timedelta(minutes=1))
    _make_check(shared_db, check_id="c2", builder_name="PRESTIGE ESTATES LTD", checked_at=base - timedelta(minutes=2))
    _make_check(shared_db, check_id="c3", builder_name="Sobha", checked_at=base - timedelta(minutes=3))

    client = TestClient(app)
    resp = client.get("/v1/builders/recent")
    assert resp.status_code == 200
    body = resp.json()
    slugs = [item["slug"] for item in body["items"]]
    assert slugs == ["prestige", "sobha"]  # newest-first, deduped
    assert body["count"] == 2


def test_recent_builders_respects_limit(shared_db: Session) -> None:
    _make_check(shared_db, check_id="c1", builder_name="Prestige")
    _make_check(shared_db, check_id="c2", builder_name="Sobha")
    _make_check(shared_db, check_id="c3", builder_name="Brigade")
    client = TestClient(app)
    resp = client.get("/v1/builders/recent?limit=2")
    assert resp.status_code == 200
    assert resp.json()["count"] == 2


def test_recent_builders_skips_null_builder_names(shared_db: Session) -> None:
    _make_check(shared_db, check_id="c0", builder_name=None)
    _make_check(shared_db, check_id="c1", builder_name="Sobha")
    client = TestClient(app)
    resp = client.get("/v1/builders/recent")
    body = resp.json()
    assert [i["slug"] for i in body["items"]] == ["sobha"]
