"""Rate-limit middleware tests — see specs/rate-limiting.md.

Strategy
--------
- Use the FastAPI ``TestClient`` against the real app.
- Override the ``get_db`` dependency so /v1/check doesn't need Postgres.
- Send POSTs with an INVALID URL: under the limit they return 400
  (URL parser short-circuits before any DB write), over the limit they
  return 429. Either way, no DB write happens.
- Reset the in-memory limiter between tests via an autouse fixture so
  test order doesn't matter.
"""
from __future__ import annotations

import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure ``app.*`` resolves when pytest is run from backend/.
_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.middleware.rate_limit import limiter  # noqa: E402


# An invalid URL: matches no portal regex, so the /v1/check handler
# raises HTTPException(400, INVALID_URL) before touching the DB.
_INVALID_URL = "https://example.com/whatever"


def _noop_db() -> Generator[None, None, None]:
    """Dependency override — /v1/check never reaches the DB on an
    invalid URL, but FastAPI still resolves Depends(get_db) before
    calling the route. Yield None so resolution succeeds."""
    yield None


@pytest.fixture(autouse=True)
def _reset_limiter_and_overrides() -> Generator[None, None, None]:
    """Each test starts with a fresh in-memory limiter and the
    ``get_db`` dependency stubbed out."""
    limiter.reset()
    app.dependency_overrides[get_db] = _noop_db
    try:
        yield
    finally:
        limiter.reset()
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    """Fresh TestClient per test — no shared cookies/state across tests."""
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Under / at-limit behaviour
# ---------------------------------------------------------------------------

def test_under_limit_returns_200(client: TestClient) -> None:
    """9 sequential POSTs from the same IP must all be accepted by the
    rate limiter. The URL is invalid so the response is 400, not 200,
    but the limiter does NOT short-circuit them with 429."""
    for i in range(9):
        resp = client.post("/v1/check", json={"url": _INVALID_URL})
        # The limiter let it through — 400 (INVALID_URL) is fine here.
        # The point of this test is that we DON'T see 429 yet.
        assert resp.status_code != 429, f"request {i} unexpectedly 429"
        assert resp.status_code == 400


def test_over_limit_returns_429(client: TestClient) -> None:
    """The 11th POST from the same IP within the window must return
    429 with the spec'd JSON body and headers."""
    last_resp = None
    for _ in range(11):
        last_resp = client.post("/v1/check", json={"url": _INVALID_URL})

    assert last_resp is not None
    assert last_resp.status_code == 429

    body = last_resp.json()
    assert body["code"] == "RATE_LIMITED"
    assert body["status"] == 429

    assert "Retry-After" in last_resp.headers
    assert int(last_resp.headers["Retry-After"]) >= 0
    assert last_resp.headers["X-RateLimit-Remaining"] == "0"


def test_healthz_not_rate_limited(client: TestClient) -> None:
    """/healthz must never be limited — 50 calls all 200."""
    for _ in range(50):
        resp = client.get("/healthz")
        assert resp.status_code == 200


def test_pro_key_bypasses_anon_limit(client: TestClient) -> None:
    """A pk_* API key gets its own bucket — 11+ calls must all pass
    the anon 10/min ceiling because the bucket key is the API key,
    not the IP."""
    headers = {"X-API-Key": "pk_test"}
    for i in range(11):
        resp = client.post("/v1/check", json={"url": _INVALID_URL}, headers=headers)
        assert resp.status_code != 429, f"request {i} unexpectedly 429"
        # Same-as under-limit: invalid URL → 400.
        assert resp.status_code == 400
