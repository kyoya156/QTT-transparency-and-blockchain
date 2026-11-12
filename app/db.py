"""Database plumbing: engine, sessions, and the idempotent schema bootstrap."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

# `unaccent()` is STABLE, so it cannot be indexed or used in a generated column
# until it is wrapped in an IMMUTABLE function. Vietnamese `đ` is not covered by
# every unaccent rule set, so map it explicitly. Result: "CỔ PHẦN" and "co phan"
# produce the same tsvector, which is what sponsors typing without accents need.
_EXTENSION_SQL = (
    "CREATE EXTENSION IF NOT EXISTS vector",
    "CREATE EXTENSION IF NOT EXISTS unaccent",
)

_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION immutable_unaccent(txt text)
RETURNS text
LANGUAGE sql
IMMUTABLE
PARALLEL SAFE
AS $fn$
    SELECT lower(translate(unaccent('unaccent', txt), 'đĐ', 'dd'))
$fn$;
"""


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(
        get_settings().database_url,
        pool_pre_ping=True,
        future=True,
    )
    

@lru_cache(maxsize=1)
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Commit on success, roll back on error, always close."""
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency: a read/write session per request."""
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()


def init_schema(engine: Engine | None = None) -> None:
    """Create extensions, the unaccent helper, and every table. Safe to re-run."""
    from app.models import Base  # local import: models depend on settings

    engine = engine or get_engine()
    with engine.begin() as conn:
        for statement in _EXTENSION_SQL:
            conn.execute(text(statement))
        conn.execute(text(_FUNCTION_SQL))
    Base.metadata.create_all(engine)
