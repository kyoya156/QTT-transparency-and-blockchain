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
        _access_control(engine)


def _access_control(engine: Engine) -> None:
    """Vai tro chatbot_app + RLS: nguoi dung chi doc duoc chunk co nhan trung phong ban (admin: tat ca).

    Chunk chua gan nhan (labels rong) chi admin doc duoc. Idempotent.
    """
    with engine.begin() as c:
        c.exec_driver_sql("ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS correlation_id varchar(64);")
        c.exec_driver_sql("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS labels text[] NOT NULL DEFAULT '{}';")
        c.exec_driver_sql(
            "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'chatbot_app') "
            "THEN CREATE ROLE chatbot_app NOLOGIN; END IF; END $$;")
        c.exec_driver_sql("GRANT USAGE ON SCHEMA public TO chatbot_app;")
        c.exec_driver_sql("GRANT SELECT ON chunks TO chatbot_app;")
        c.exec_driver_sql("GRANT INSERT ON audit_log TO chatbot_app;")
        c.exec_driver_sql("GRANT USAGE, SELECT ON SEQUENCE audit_log_id_seq TO chatbot_app;")
        c.exec_driver_sql("ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;")
        c.exec_driver_sql("DROP POLICY IF EXISTS chunk_dept_read ON chunks;")
        c.exec_driver_sql(
            "CREATE POLICY chunk_dept_read ON chunks FOR SELECT TO chatbot_app USING ("
            "current_setting('app.full_read', true) = 'on' "
            "OR labels && string_to_array(coalesce(current_setting('app.depts', true), ''), ','));")
