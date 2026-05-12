"""Tests for GET /v1/checks/{id}.

The endpoint exists so each saved check becomes a permanent, indexable
URL on the website (`/check/<id>`) and a deep link target for the Chrome
extension's "See full report" CTA. These tests cover the happy path
(round-trip the persisted shape), the 404 path, and the rate-limit gate.
"""
from __future__ import annotations

import sys
from collections.abc import Generator
from datetime import UTC, datetime
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
from app.models.db import Check  # noqa: E402


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


def _make_check(db: Session, *, check_id: str = "chk_abc123") -> Check:
    row = Check(
        id=check_id,
        portal="magicbricks",
        listing_id="x999",
        url="https://www.magicbricks.com/x",
        score=42,
        label="caution",
        summary="2 red flags worth checking.",
        red_flags=[
            {
                "code": "PRICE_BELOW_MARKET",
                "label": "Price below locality average",
                "description": "22% below Whitefield 3BHK average.",
                "severity": "medium",
                "evidence_urls": [],
                "source": "PropCheck locality price index",
            }
        ],
        green_flags=[],
        checklist=["Visit in person", "Verify RERA"],
        verifications={
            "rera": {"status": "NOT_PROVIDED"},
            "image_match_count": None,
            "locality_avg_price_per_sqft": 10_600,
            "price_delta_pct": -22,
            "listing_age_days": 87,
            "builder_open_complaints": None,
            "parse_confidence": "high",
        },
        property_data={
            "portal": "magicbricks",
            "listing_id": "x999",
            "title": "3 BHK Apartment in Whitefield",
            "price_inr": 12_000_000,
            "bhk": 3,
            "area_sqft": 1450,
            "locality": "Whitefield",
            "city": "Bangalore",
            "state": "karnataka",
            "rera_id": None,
            "builder_name": None,
            "listed_at": None,
        },
        cache_hit=False,
        source_surface="web",
        requester_ip=None,
        user_agent=None,
        checked_at=datetime.now(UTC),
    )
    db.add(row)
    db.commit()
    return row


def test_get_check_returns_persisted_report(shared_db: Session) -> None:
    _make_check(shared_db, check_id="chk_abc123")
    client = TestClient(app)
    resp = client.get("/v1/checks/chk_abc123")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "chk_abc123"
    assert body["score"] == 42
    assert body["label"] == "caution"
    assert body["property"]["title"] == "3 BHK Apartment in Whitefield"
    assert body["red_flags"][0]["code"] == "PRICE_BELOW_MARKET"
    # parse_confidence survives the JSONB round-trip via verifications.
    assert body["verifications"]["parse_confidence"] == "high"
    assert body["parse_confidence"] == "high"
    # cache_hit is False on a GET — the field is only meaningful for POST.
    assert body["cache_hit"] is False


def test_get_check_404_for_unknown_id(shared_db: Session) -> None:
    client = TestClient(app)
    resp = client.get("/v1/checks/chk_does_not_exist")
    assert resp.status_code == 404
    body = resp.json()
    # FastAPI nests our error dict inside "detail".
    assert body["detail"]["code"] == "CHECK_NOT_FOUND"


def test_get_check_rejects_oversized_id(shared_db: Session) -> None:
    """A 100-character id is bounded out before hitting the DB."""
    client = TestClient(app)
    resp = client.get("/v1/checks/" + ("x" * 100))
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "CHECK_NOT_FOUND"


def test_get_check_carries_low_confidence_through(shared_db: Session) -> None:
    """A low-confidence persisted check must surface parse_confidence so the
    page renders 'Not enough data' instead of the placeholder score."""
    row = _make_check(shared_db, check_id="chk_low1")
    row.verifications = {
        **row.verifications,
        "parse_confidence": "low",
    }
    row.score = 50
    row.label = "caution"
    shared_db.add(row)
    shared_db.commit()

    client = TestClient(app)
    resp = client.get("/v1/checks/chk_low1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["parse_confidence"] == "low"
    assert body["verifications"]["parse_confidence"] == "low"
