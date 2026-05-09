"""Asserts the 429 JSON body shape exactly matches specs/rate-limiting.md."""
from __future__ import annotations

import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.middleware.rate_limit import limiter  # noqa: E402

_INVALID_URL = "https://example.com/whatever"


def _noop_db() -> Generator[None, None, None]:
    yield None


@pytest.fixture(autouse=True)
def _reset_limiter_and_overrides() -> Generator[None, None, None]:
    limiter.reset()
    app.dependency_overrides[get_db] = _noop_db
    try:
        yield
    finally:
        limiter.reset()
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


def test_429_response_shape(client: TestClient) -> None:
    """Trip the limiter and assert the response body has every field
    the spec calls for — type, title, status, detail, code, limit,
    remaining, reset_at — plus the X-RateLimit-* / Retry-After headers.
    """
    resp = None
    for _ in range(12):
        resp = client.post("/v1/check", json={"url": _INVALID_URL})

    assert resp is not None
    assert resp.status_code == 429

    body = resp.json()
    # Required keys per the spec.
    for key in ("type", "title", "status", "detail", "code", "limit", "remaining", "reset_at"):
        assert key in body, f"missing key: {key}"

    assert body["status"] == 429
    assert body["code"] == "RATE_LIMITED"
    assert body["title"] == "Rate limited"
    assert body["type"] == "https://propcheck.in/errors/rate-limited"
    assert body["limit"] == 10
    assert body["remaining"] == 0
    assert isinstance(body["reset_at"], str)
    assert body["reset_at"].endswith("Z")  # ISO-8601 UTC

    # Required headers.
    assert "Retry-After" in resp.headers
    assert resp.headers["X-RateLimit-Limit"] == "10"
    assert resp.headers["X-RateLimit-Remaining"] == "0"
    assert "X-RateLimit-Reset" in resp.headers
