"""Khoi tao Postgres: extension, ham unaccent bat bien (de index duoc) va index tim kiem. Idempotent."""
from sqlalchemy import Engine

from .db import Base
from . import models  # noqa: F401  (dang ky bang)


def init_db(engine: Engine) -> None:
    if engine.dialect.name == "postgresql":
        with engine.begin() as c:
            c.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector;")
            c.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS unaccent;")
            # unaccent mac dinh khong IMMUTABLE nen khong dung duoc trong index: boc lai.
            c.exec_driver_sql(
                "CREATE OR REPLACE FUNCTION f_unaccent(text) RETURNS text AS "
                "$$ SELECT public.unaccent('public.unaccent', $1) $$ "
                "LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT;")
            c.exec_driver_sql(
                "CREATE OR REPLACE FUNCTION immutable_unaccent(text) RETURNS text AS "
                "$$ SELECT public.unaccent('public.unaccent', $1) $$ "
                "LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT;")
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "postgresql":
        with engine.begin() as c:
            # Tim tu khoa khong dau: "co phan" khop "CO PHAN" va "CỔ PHẦN".
            # Cung bieu thuc voi Chunk.tsv de truy van dung duoc index.
            c.exec_driver_sql("DROP INDEX IF EXISTS ix_chunks_fts;")
            c.exec_driver_sql(
                "CREATE INDEX ix_chunks_fts ON chunks "
                "USING gin (to_tsvector('simple'::regconfig, immutable_unaccent(content)));")
            c.exec_driver_sql("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS crawled_at timestamptz;")
