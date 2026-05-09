"""Tests for POST /v1/feedback (Sprint 1 Day 12).

Strategy:
- Use FastAPI TestClient against the real app.
- Override `get_db` to bind to the in-memory SQLite session from the
  shared `db_session` fixture (defined in conftest.py).
- Pre-seed a `Check` row so the FK / existence guard has something to
  point at in the success-path tests.
- Reset the in-memory limiter between tests so order doesn't matter.
"""
from __future__ import annotations

import sys
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Make `app.*` importable when pytest runs from backend/.
_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.middleware.rate_limit import limiter  # noqa: E402
from app.models.db import Check, Feedback  # noqa: E402


_SEEDED_CHECK_ID = "chk_test_001"


@pytest.fixture(autouse=True)
def _reset_limiter() -> Generator[None, None, None]:
    """Each test starts with a fresh in-memory limiter."""
    limiter.reset()
    try:
        yield
    finally:
        limiter.reset()


@pytest.fixture()
def seeded_db(db_session: Session) -> Session:
    """A `db_session` with one `Check` row pre-seeded for FK references."""
    db_session.add(
        Check(
            id=_SEEDED_CHECK_ID,
            portal="magicbricks",
            listing_id="12345",
            url="https://www.magicbricks.com/propertyDetails/test",
            score=42,
            label="risky",
            summary="Test check used by feedback tests.",
            red_flags=[],
            green_flags=[],
            checklist=[],
            verifications={},
            property_data={},
            cache_hit=False,
            source_surface="api",
            requester_ip=None,
            user_agent=None,
            checked_at=datetime.now(UTC),
        )
    )
    db_session.commit()
    return db_session


@pytest.fixture()
def client(seeded_db: Session) -> Generator[TestClient, None, None]:
    """A TestClient whose `get_db` dependency is bound to `seeded_db`."""

    def _override() -> Generator[Session, None, None]:
        # Yield the same session across requests in this test so the
        # commits/queries see each other.
        yield seeded_db

    app.dependency_overrides[get_db] = _override
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def empty_client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient with an EMPTY in-memory DB (no seeded check rows)."""

    def _override() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Happy-path
# ---------------------------------------------------------------------------

def test_feedback_creates_row(client: TestClient, seeded_db: Session) -> None:
    """A valid POST against an existing check_id creates a feedback row
    with status='pending' and returns 201 with `{id, status}`."""
    resp = client.post(
        "/v1/feedback",
        json={
            "check_id": _SEEDED_CHECK_ID,
            "reason": "false_positive",
            "note": "I verified the RERA in person, it's correct.",
            "reporter_email": "user@example.com",
        },
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "pending"
    assert isinstance(body["id"], int)
    assert body["id"] > 0

    rows = seeded_db.query(Feedback).all()
    assert len(rows) == 1
    saved = rows[0]
    assert saved.check_id == _SEEDED_CHECK_ID
    assert saved.reason == "false_positive"
    assert saved.note == "I verified the RERA in person, it's correct."
    assert saved.reporter_email == "user@example.com"
    assert saved.status == "pending"


# ---------------------------------------------------------------------------
# Error-paths
# ---------------------------------------------------------------------------

def test_feedback_check_not_found(empty_client: TestClient) -> None:
    """Non-existent check_id returns 404 with code CHECK_NOT_FOUND."""
    resp = empty_client.post(
        "/v1/feedback",
        json={
            "check_id": "chk_does_not_exist",
            "reason": "data_error",
        },
    )

    assert resp.status_code == 404, resp.text
    body = resp.json()
    assert body["detail"]["code"] == "CHECK_NOT_FOUND"


def test_feedback_validates_reason(client: TestClient) -> None:
    """Invalid reason value -> 422."""
    resp = client.post(
        "/v1/feedback",
        json={
            "check_id": _SEEDED_CHECK_ID,
            "reason": "totally-not-a-valid-reason",
        },
    )

    assert resp.status_code == 422, resp.text


def test_feedback_validates_email(client: TestClient) -> None:
    """Malformed reporter_email -> 422."""
    resp = client.post(
        "/v1/feedback",
        json={
            "check_id": _SEEDED_CHECK_ID,
            "reason": "other",
            "reporter_email": "not-an-email",
        },
    )

    assert resp.status_code == 422, resp.text


def test_feedback_email_optional(client: TestClient, seeded_db: Session) -> None:
    """Omitting reporter_email is allowed; row stores reporter_email=None."""
    resp = client.post(
        "/v1/feedback",
        json={
            "check_id": _SEEDED_CHECK_ID,
            "reason": "false_negative",
            "note": "missed a red flag",
        },
    )

    assert resp.status_code == 201, resp.text
    rows = seeded_db.query(Feedback).all()
    assert len(rows) == 1
    assert rows[0].reporter_email is None


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

def test_feedback_rate_limited(client: TestClient) -> None:
    """11 rapid POSTs from the same IP -> 11th returns 429."""
    last_resp = None
    for _ in range(11):
        last_resp = client.post(
            "/v1/feedback",
            json={
                "check_id": _SEEDED_CHECK_ID,
                "reason": "other",
            },
        )

    assert last_resp is not None
    assert last_resp.status_code == 429, last_resp.text
    body = last_resp.json()
    assert body["code"] == "RATE_LIMITED"
