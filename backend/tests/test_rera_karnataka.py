"""Tests for `app.integrations.rera_karnataka`.

Covers the five behaviours required by specs/integrations.md §1:
  - rera_id is None        -> NOT_PROVIDED
  - cache hit (fresh row)  -> MATCH from cache, no HTTP
  - cache miss + transport error -> PORTAL_UNREACHABLE, nothing cached
  - cache miss + portal "no record" -> NOT_FOUND, placeholder cached
  - cache miss + portal hit -> MATCH, row upserted

All HTTP is mocked via respx; we never touch the live portal.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

import httpx
import pytest
import respx
from sqlalchemy import select

from app.config import settings
from app.integrations import rera_karnataka
from app.integrations.rera_karnataka import RERAResult, lookup
from app.models.db import RERARecord


# Karnataka RERA ids look like 'PRM/KA/RERA/...' per specs/database.md.
# The literal slashes in the id make `respx.get(url_string)` matching
# brittle (respx URL-encodes them, httpx sends them raw), so we mock
# against a compiled regex on the host+path instead.
SAMPLE_ID = "PRM/KA/RERA/1251/446/PR/171019/001234"


def _project_url_regex() -> re.Pattern[str]:
    base = settings.rera_karnataka_base.rstrip("/")
    return re.compile(re.escape(base) + r"/projectViewDetails(\?.*)?$")


def _match_html(project_name: str, builder: str, status_text: str = "Registered") -> str:
    """A vaguely realistic Karnataka RERA project-detail page."""
    return f"""
    <!doctype html>
    <html><body>
      <h1>Project Details</h1>
      <table>
        <tr><th>Project Name</th><td>{project_name}</td></tr>
        <tr><th>Promoter Name</th><td>{builder}</td></tr>
        <tr><th>Project Status</th><td>{status_text}</td></tr>
        <tr><th>RERA Id</th><td>{SAMPLE_ID}</td></tr>
      </table>
    </body></html>
    """


_NOT_FOUND_HTML = """
<!doctype html>
<html><body>
  <h1>Project Details</h1>
  <p>No record found for the given project id.</p>
</body></html>
"""


# ---------------------------------------------------------------------------
# 1. NOT_PROVIDED
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_none_returns_not_provided(db_session):
    result = await lookup(None, db_session)
    assert isinstance(result, RERAResult)
    assert result.status == "NOT_PROVIDED"
    assert result.project is None


@pytest.mark.asyncio
async def test_empty_string_returns_not_provided(db_session):
    result = await lookup("   ", db_session)
    assert result.status == "NOT_PROVIDED"


# ---------------------------------------------------------------------------
# 2. Cache hit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_hit_returns_match(db_session, monkeypatch):
    # Pre-seed a fresh row.
    db_session.add(
        RERARecord(
            state="karnataka",
            rera_id=SAMPLE_ID,
            project_name="Skylark Esta",
            builder_name="Skylark Mansions",
            status="registered",
            raw={"seeded": True},
            fetched_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    # Make _fetch_remote blow up if it's called — proves we hit cache only.
    async def _boom(*args, **kwargs):
        raise AssertionError("HTTP must not be called on cache hit")

    monkeypatch.setattr(rera_karnataka, "_fetch_remote", _boom)

    result = await lookup(SAMPLE_ID, db_session)

    assert result.status == "MATCH"
    assert result.project is not None
    assert result.project.rera_id == SAMPLE_ID
    assert result.project.project_name == "Skylark Esta"
    assert result.project.builder_name == "Skylark Mansions"
    assert result.project.status == "registered"


# ---------------------------------------------------------------------------
# 3. Cache miss + transport error -> PORTAL_UNREACHABLE
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_cache_miss_unreachable(db_session):
    respx.get(url=_project_url_regex()).mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    result = await lookup(SAMPLE_ID, db_session)

    assert result.status == "PORTAL_UNREACHABLE"
    assert result.project is None

    # Importantly: nothing should be cached for a transport failure.
    rows = db_session.execute(select(RERARecord)).scalars().all()
    assert rows == []


@pytest.mark.asyncio
@respx.mock
async def test_cache_miss_5xx_unreachable(db_session):
    """A 5xx is also treated as PORTAL_UNREACHABLE (don't cache)."""
    respx.get(url=_project_url_regex()).mock(
        return_value=httpx.Response(503, text="<html>maintenance</html>")
    )

    result = await lookup(SAMPLE_ID, db_session)

    assert result.status == "PORTAL_UNREACHABLE"
    rows = db_session.execute(select(RERARecord)).scalars().all()
    assert rows == []


# ---------------------------------------------------------------------------
# 4. Cache miss + "no record" -> NOT_FOUND, placeholder cached
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_cache_miss_not_found_caches(db_session):
    respx.get(url=_project_url_regex()).mock(
        return_value=httpx.Response(200, text=_NOT_FOUND_HTML)
    )

    result = await lookup(SAMPLE_ID, db_session)

    assert result.status == "NOT_FOUND"
    assert result.project is None

    # A placeholder row should have been written so the next 7 days serve
    # NOT_FOUND from cache without hitting the portal again.
    rows = db_session.execute(
        select(RERARecord).where(RERARecord.rera_id == SAMPLE_ID)
    ).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.state == "karnataka"
    assert row.project_name is None
    assert row.builder_name is None
    assert row.status is None


@pytest.mark.asyncio
@respx.mock
async def test_404_returns_not_found_and_caches(db_session):
    respx.get(url=_project_url_regex()).mock(
        return_value=httpx.Response(404, text="not found")
    )

    result = await lookup(SAMPLE_ID, db_session)

    assert result.status == "NOT_FOUND"
    rows = db_session.execute(select(RERARecord)).scalars().all()
    assert len(rows) == 1
    assert rows[0].project_name is None


# ---------------------------------------------------------------------------
# 5. Cache miss + project found -> MATCH, row upserted
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_cache_miss_match_caches(db_session):
    respx.get(url=_project_url_regex()).mock(
        return_value=httpx.Response(
            200,
            text=_match_html("Prestige Falcon City", "Prestige Estates Projects"),
        )
    )

    result = await lookup(SAMPLE_ID, db_session)

    assert result.status == "MATCH"
    assert result.project is not None
    assert result.project.rera_id == SAMPLE_ID
    assert result.project.project_name == "Prestige Falcon City"
    assert result.project.builder_name == "Prestige Estates Projects"
    assert result.project.status == "registered"

    # Persisted in the cache table.
    rows = db_session.execute(
        select(RERARecord).where(RERARecord.rera_id == SAMPLE_ID)
    ).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.state == "karnataka"
    assert row.project_name == "Prestige Falcon City"
    assert row.builder_name == "Prestige Estates Projects"
    assert row.status == "registered"


# ---------------------------------------------------------------------------
# Bonus: lossy parse — page exists but structure unfamiliar -> still MATCH
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
async def test_match_with_unrecognised_html_still_returns_match(db_session):
    """If the id resolves to a real page but the parser can't extract
    fields, we still return MATCH (with None fields) per the spec."""
    respx.get(url=_project_url_regex()).mock(
        return_value=httpx.Response(
            200,
            text="<html><body><div>some unrelated layout</div></body></html>",
        )
    )

    result = await lookup(SAMPLE_ID, db_session)

    assert result.status == "MATCH"
    assert result.project is not None
    assert result.project.rera_id == SAMPLE_ID
    # Fields legitimately unknown — that's allowed.
    assert result.project.project_name is None
    assert result.project.builder_name is None
