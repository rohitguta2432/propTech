"""Maharashtra RERA verification integration.

Looks up a RERA project ID against the MahaRERA registry, with a 7-day
Postgres cache (`rera_records` table, scoped to `state="maharashtra"`)
in front of the live portal.

Public surface: same shape as `rera_karnataka` — we reuse `RERAProject`
and `RERAResult` from there so callers can branch on state without
caring about which dataclass they got back.

    - lookup(rera_id, db) -> RERAResult

The function is fail-soft: any unhandled exception is converted to
PORTAL_UNREACHABLE. Cache misses that resolve cleanly (MATCH or
NOT_FOUND) are upserted into `rera_records`; transport-level failures
are NOT cached so we can retry on the next call.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import settings
from app.integrations.rera_karnataka import RERAProject, RERAResult
from app.models.db import RERARecord

log = logging.getLogger(__name__)

# How long a cached row is considered fresh.
CACHE_TTL = timedelta(days=7)

# httpx timeout for a single remote call.
REMOTE_TIMEOUT = 5.0

# State value stamped on every row we write.
STATE = "maharashtra"

# Sentinel returned by `_fetch_remote` when the portal is unreachable.
# Distinguished from `None` (= "no record for this id").
UNREACHABLE: Literal["UNREACHABLE"] = "UNREACHABLE"


# Best-guess MahaRERA portal endpoint. The real portal lives at
# https://maharera.maharashtra.gov.in — the project search query string
# accepts a `ProjectRegisteredId` parameter on the public-facing search
# page. Wrap this in `settings.rera_maharashtra_base` so it's overridable
# from the environment without code changes.
_DEFAULT_MAHARERA_BASE = "https://maharera.maharashtra.gov.in"


def _portal_base() -> str:
    """Resolve the MahaRERA base URL (settings override → default)."""
    return getattr(settings, "rera_maharashtra_base", _DEFAULT_MAHARERA_BASE).rstrip("/")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def lookup(rera_id: str | None, db: Session) -> RERAResult:
    """Verify a RERA id against the Maharashtra registry.

    Behaviour mirrors `rera_karnataka.lookup` exactly — the only
    difference is which portal we hit and which state we stamp on the
    cache rows.

      - rera_id is None / empty             -> NOT_PROVIDED
      - cache hit (row fresher than 7 days) -> MATCH or NOT_FOUND from cache
      - cache miss + portal unreachable     -> PORTAL_UNREACHABLE (no cache)
      - cache miss + project found          -> upsert + MATCH
      - cache miss + no project             -> upsert NOT_FOUND placeholder + NOT_FOUND

    Never raises.
    """
    if not rera_id:
        return RERAResult(status="NOT_PROVIDED")

    rera_id = rera_id.strip()
    if not rera_id:
        return RERAResult(status="NOT_PROVIDED")

    try:
        cached = _read_cache(db, rera_id)
        if cached is not None:
            return _result_from_cached_row(cached)

        remote = await _fetch_remote(rera_id)

        if remote == UNREACHABLE:
            # Don't cache transport failures.
            return RERAResult(status="PORTAL_UNREACHABLE")

        if remote is None:
            # Definitive "no such id" — cache a placeholder so we don't
            # re-hit the portal for 7 days.
            _upsert_not_found(db, rera_id)
            return RERAResult(status="NOT_FOUND")

        # Found a project — cache the parsed fields and return MATCH.
        _upsert_project(db, remote)
        return RERAResult(status="MATCH", project=remote)

    except Exception:  # pragma: no cover — last-ditch safety net
        log.exception("rera_maharashtra.lookup failed for rera_id=%s", rera_id)
        return RERAResult(status="PORTAL_UNREACHABLE")


# ---------------------------------------------------------------------------
# Cache helpers (state-scoped to Maharashtra)
# ---------------------------------------------------------------------------

def _read_cache(db: Session, rera_id: str) -> RERARecord | None:
    """Return a fresh cache row, or None if missing / stale."""
    row = db.execute(
        select(RERARecord).where(
            RERARecord.state == STATE,
            RERARecord.rera_id == rera_id,
        )
    ).scalar_one_or_none()

    if row is None:
        return None

    fetched_at = row.fetched_at
    if fetched_at is None:
        return None

    # Postgres returns tz-aware datetimes; SQLite (used in tests) returns
    # naive — normalise both to UTC for the staleness comparison.
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) - fetched_at > CACHE_TTL:
        return None

    return row


def _result_from_cached_row(row: RERARecord) -> RERAResult:
    """A cached row with all-None fields is our NOT_FOUND placeholder."""
    if row.project_name is None and row.builder_name is None and row.status is None:
        return RERAResult(status="NOT_FOUND")

    project = RERAProject(
        rera_id=row.rera_id,
        project_name=row.project_name,
        builder_name=row.builder_name,
        status=row.status,
        raw=row.raw or {},
    )
    return RERAResult(status="MATCH", project=project)


def _upsert_project(db: Session, project: RERAProject) -> None:
    _upsert_row(
        db,
        rera_id=project.rera_id,
        project_name=project.project_name,
        builder_name=project.builder_name,
        status=project.status,
        raw=project.raw,
    )


def _upsert_not_found(db: Session, rera_id: str) -> None:
    _upsert_row(
        db,
        rera_id=rera_id,
        project_name=None,
        builder_name=None,
        status=None,
        raw=None,
    )


def _upsert_row(
    db: Session,
    *,
    rera_id: str,
    project_name: str | None,
    builder_name: str | None,
    status: str | None,
    raw: dict[str, Any] | None,
) -> None:
    """Idempotent write: insert-or-update on (state, rera_id).

    Uses Postgres' `INSERT ... ON CONFLICT DO UPDATE`. For SQLite (tests),
    falls back to a manual SELECT-then-UPDATE/INSERT.
    """
    now = datetime.now(timezone.utc)
    dialect = db.bind.dialect.name if db.bind is not None else ""

    if dialect == "postgresql":
        stmt = pg_insert(RERARecord).values(
            state=STATE,
            rera_id=rera_id,
            project_name=project_name,
            builder_name=builder_name,
            status=status,
            raw=raw,
            fetched_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="rera_state_rera_unique",
            set_={
                "project_name": stmt.excluded.project_name,
                "builder_name": stmt.excluded.builder_name,
                "status": stmt.excluded.status,
                "raw": stmt.excluded.raw,
                "fetched_at": stmt.excluded.fetched_at,
            },
        )
        db.execute(stmt)
    else:
        existing = db.execute(
            select(RERARecord).where(
                RERARecord.state == STATE,
                RERARecord.rera_id == rera_id,
            )
        ).scalar_one_or_none()

        if existing is None:
            db.add(
                RERARecord(
                    state=STATE,
                    rera_id=rera_id,
                    project_name=project_name,
                    builder_name=builder_name,
                    status=status,
                    raw=raw,
                    fetched_at=now,
                )
            )
        else:
            existing.project_name = project_name
            existing.builder_name = builder_name
            existing.status = status
            existing.raw = raw
            existing.fetched_at = now

    db.commit()


# ---------------------------------------------------------------------------
# Remote fetch + HTML parsing
# ---------------------------------------------------------------------------

async def _fetch_remote(
    rera_id: str,
    client: httpx.AsyncClient | None = None,
) -> RERAProject | None | Literal["UNREACHABLE"]:
    """Fetch + parse the MahaRERA project page.

    Args:
        rera_id: The project id to look up.
        client:  Optional pre-built httpx client (used by tests to inject
                 a respx-mocked client).

    Returns:
        - RERAProject : a parsed project (MATCH).
        - None        : the portal definitively returned "no such project".
        - "UNREACHABLE" sentinel : transport failure / non-2xx.
    """
    base = _portal_base()
    # Best-guess endpoint per spec — the public project search page on
    # MahaRERA accepts a `ProjectRegisteredId` query parameter. If the
    # real portal moves, override `settings.rera_maharashtra_base`.
    url = f"{base}/projects/project-search?ProjectRegisteredId={rera_id}"

    owns_client = client is None
    try:
        if owns_client:
            client = httpx.AsyncClient(timeout=REMOTE_TIMEOUT)
        try:
            response = await client.get(url, follow_redirects=True)
        except httpx.HTTPError:
            log.warning("rera_maharashtra: transport error for %s", rera_id, exc_info=True)
            return UNREACHABLE
    finally:
        if owns_client and client is not None:
            await client.aclose()

    # 404 = definitively no such project
    if response.status_code == 404:
        return None

    # Anything else non-2xx is treated as portal unreachable so we don't
    # cache a phantom NOT_FOUND on a 5xx blip.
    if response.status_code >= 400:
        log.warning(
            "rera_maharashtra: status=%s for %s", response.status_code, rera_id
        )
        return UNREACHABLE

    return _parse_project_html(rera_id, response.text)


def _parse_project_html(rera_id: str, html: str) -> RERAProject | None:
    """Parse a MahaRERA project search result page.

    Like Karnataka, the parser is deliberately lossy: if the page exists
    for this id but the structure is unrecognisable, we still return a
    minimal RERAProject (status MATCH). Only an explicit "no record"
    sentinel returns None.
    """
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True).lower()

    # Sentinel phrases the portal shows when an id doesn't resolve.
    not_found_markers = (
        "no record found",
        "no records found",
        "no result found",
        "no results found",
        "no project found",
        "no projects found",
        "no data found",
        "not registered",
        "invalid project",
    )
    if any(marker in text for marker in not_found_markers):
        return None

    project_name = _extract_field(soup, ("project name", "name of project"))
    builder_name = _extract_field(
        soup,
        ("promoter name", "name of promoter", "promoter", "builder name"),
    )
    status = _extract_field(soup, ("project status", "status"))

    return RERAProject(
        rera_id=rera_id,
        project_name=project_name,
        builder_name=builder_name,
        status=_normalise_status(status),
        raw={"html_len": len(html)},
    )


def _extract_field(soup: BeautifulSoup, label_keywords: tuple[str, ...]) -> str | None:
    """Look for a `<label>: <value>` pair in the page.

    MahaRERA renders fields as either table rows (`<th>label</th><td>value</td>`)
    or label-value pairs in `<div>` siblings. We try both shapes and
    return the first match. None if nothing recognisable.
    """
    for keyword in label_keywords:
        keyword_lc = keyword.lower()

        for th in soup.find_all(["th", "td", "label", "strong", "b"]):
            label_text = th.get_text(" ", strip=True).lower().rstrip(":")
            if not label_text:
                continue
            if keyword_lc not in label_text:
                continue
            # Try a sibling cell on the same row first.
            sibling = th.find_next_sibling(["td", "span", "div"])
            if sibling is not None:
                value = sibling.get_text(" ", strip=True)
                if value:
                    return value
            # Fallback: any descendant value of the parent row.
            parent = th.parent
            if parent is not None:
                for cell in parent.find_all(["td", "span", "div"]):
                    if cell is th:
                        continue
                    value = cell.get_text(" ", strip=True)
                    if value and keyword_lc not in value.lower():
                        return value

    return None


def _normalise_status(raw: str | None) -> str | None:
    """Map portal status strings onto our canonical enum.

    See specs/database.md `rera_records.status` — 'registered' | 'expired' | 'cancelled'.
    """
    if not raw:
        return None
    lc = raw.lower()
    if "expire" in lc or "lapsed" in lc:
        return "expired"
    if "cancel" in lc or "revoke" in lc:
        return "cancelled"
    if "register" in lc or "active" in lc or "approved" in lc:
        return "registered"
    return raw  # passthrough for anything we don't recognise
