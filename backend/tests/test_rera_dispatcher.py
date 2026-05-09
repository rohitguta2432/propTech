"""Tests for `app.integrations.rera` — the per-state dispatcher.

The dispatcher infers state from the rera_id shape, with `state_hint`
overriding inference. We monkey-patch each state module's `lookup` to
record which one got called, so tests don't depend on HTTP.
"""
from __future__ import annotations

import pytest

from app.integrations import rera, rera_karnataka, rera_maharashtra
from app.integrations.rera_karnataka import RERAResult


@pytest.fixture()
def call_recorder(monkeypatch):
    """Replace each state module's `lookup` with a recorder.

    Yields a dict with `calls` (list of tuples ``(state, rera_id)``).
    Both modules return a benign NOT_PROVIDED so the dispatcher just
    forwards and we observe which one it picked.
    """
    calls: list[tuple[str, str | None]] = []

    async def _ka_lookup(rera_id, db):
        calls.append(("karnataka", rera_id))
        return RERAResult(status="NOT_PROVIDED")

    async def _mh_lookup(rera_id, db):
        calls.append(("maharashtra", rera_id))
        return RERAResult(status="NOT_PROVIDED")

    monkeypatch.setattr(rera_karnataka, "lookup", _ka_lookup)
    monkeypatch.setattr(rera_maharashtra, "lookup", _mh_lookup)

    return {"calls": calls}


@pytest.mark.asyncio
async def test_routes_karnataka_id_to_karnataka_module(db_session, call_recorder):
    rera_id = "PRM/KA/RERA/1251/446/PR/171019/001234"
    result = await rera.lookup(rera_id, db_session)

    assert result.status == "NOT_PROVIDED"
    assert call_recorder["calls"] == [("karnataka", rera_id)]


@pytest.mark.asyncio
async def test_routes_maharashtra_id_to_maharashtra_module(db_session, call_recorder):
    rera_id = "P52800019287"
    result = await rera.lookup(rera_id, db_session)

    assert result.status == "NOT_PROVIDED"
    assert call_recorder["calls"] == [("maharashtra", rera_id)]


@pytest.mark.asyncio
async def test_state_hint_overrides_inference(db_session, call_recorder):
    """A Karnataka-pattern id with state_hint='maharashtra' must go
    to the Maharashtra module."""
    rera_id = "PRM/KA/RERA/1251/446/PR/171019/001234"
    result = await rera.lookup(rera_id, db_session, state_hint="maharashtra")

    assert result.status == "NOT_PROVIDED"
    assert call_recorder["calls"] == [("maharashtra", rera_id)]


@pytest.mark.asyncio
async def test_state_hint_case_insensitive(db_session, call_recorder):
    """Mixed-case state_hint should still resolve."""
    rera_id = "PRM/KA/RERA/1251/446/PR/171019/001234"
    await rera.lookup(rera_id, db_session, state_hint="Maharashtra")

    assert call_recorder["calls"] == [("maharashtra", rera_id)]


@pytest.mark.asyncio
async def test_unknown_state_hint_falls_back_to_inference(
    db_session, call_recorder
):
    """An unrecognised state_hint is ignored — inference takes over.
    A Maharashtra-pattern id should still route to Maharashtra."""
    rera_id = "P52800019287"
    await rera.lookup(rera_id, db_session, state_hint="zimbabwe")

    assert call_recorder["calls"] == [("maharashtra", rera_id)]


@pytest.mark.asyncio
async def test_unknown_pattern_falls_back_to_karnataka(db_session, call_recorder):
    """Ids that don't match any known pattern default to Karnataka."""
    rera_id = "WBHIRA/1234/2026"
    result = await rera.lookup(rera_id, db_session)

    assert result.status == "NOT_PROVIDED"
    assert call_recorder["calls"] == [("karnataka", rera_id)]


@pytest.mark.asyncio
async def test_none_id_falls_back_to_karnataka(db_session, call_recorder):
    """None id still gets dispatched (default state) so the underlying
    module returns NOT_PROVIDED."""
    await rera.lookup(None, db_session)

    assert call_recorder["calls"] == [("karnataka", None)]


@pytest.mark.asyncio
async def test_id_with_embedded_slash_ka_routes_to_karnataka(
    db_session, call_recorder
):
    """Ids that contain `/KA/` even without `PRM/` should still resolve."""
    rera_id = "OTHER/KA/2026/0001"
    await rera.lookup(rera_id, db_session)

    assert call_recorder["calls"] == [("karnataka", rera_id)]
