"""Shared test fixtures.

The production schema uses Postgres-specific column types (JSONB, INET).
For tests we run an in-memory SQLite engine, so we register dialect-level
compiler hooks that translate those types to portable equivalents (JSON
and TEXT). This keeps the production ORM untouched.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make `import app...` resolve when pytest is invoked from backend/.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import pytest
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker

# Register SQLite renderings for the Postgres-only column types so
# `Base.metadata.create_all` works against an in-memory SQLite engine.
@compiles(JSONB, "sqlite")  # type: ignore[misc]
def _compile_jsonb_sqlite(type_, compiler, **kw):  # noqa: ANN001
    return "JSON"


@compiles(INET, "sqlite")  # type: ignore[misc]
def _compile_inet_sqlite(type_, compiler, **kw):  # noqa: ANN001
    return "TEXT"


@compiles(BigInteger, "sqlite")  # type: ignore[misc]
def _compile_bigint_sqlite(type_, compiler, **kw):  # noqa: ANN001
    # SQLite treats `INTEGER PRIMARY KEY` as a ROWID alias (auto-incrementing).
    # `BIGINT PRIMARY KEY` is NOT an alias, so inserts without an explicit id
    # fail with "NOT NULL constraint failed". Map BigInteger -> INTEGER on
    # SQLite so the production schema's BigInteger PKs auto-increment in tests.
    return "INTEGER"


# Importing the models registers all tables on Base.metadata.
from app.db.base import Base  # noqa: E402
from app.models import db as _models  # noqa: E402,F401


@pytest.fixture()
def db_session() -> Session:
    """Fresh in-memory SQLite session per test."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
