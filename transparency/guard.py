"""Measure 4 (team, 2026-11-19): ledger_records is insert-only, enforced by the database itself.

Allowed: INSERT; one UPDATE per row that fills the stamp columns (chain_tx, stamped_at, stamp_late)
while chain_tx is still empty and changes nothing else. Refused: any other UPDATE, DELETE, TRUNCATE.
A correction is a new record (new seq, its own leaf on chain) that names the old one; the old row and
its chain entry stay forever.

Someone with database owner rights can still drop the trigger. The chain (measure 5) and the nightly
check (measure 6) are what catch that.
"""
from __future__ import annotations

from sqlalchemy import Engine

from app import models

TABLE = models.LedgerRecord.__tablename__
STAMP_COLUMNS = ("chain_tx", "stamped_at", "stamp_late")
MSG = "ledger_records is insert-only"


def _frozen() -> list[str]:
    return [c.name for c in models.LedgerRecord.__table__.columns if c.name not in STAMP_COLUMNS]


def _sqlite() -> list[str]:
    changed = " OR ".join(f"NEW.{c} IS NOT OLD.{c}" for c in _frozen())
    return [
        "DROP TRIGGER IF EXISTS ledger_no_update", "DROP TRIGGER IF EXISTS ledger_no_delete",
        f"CREATE TRIGGER ledger_no_update BEFORE UPDATE ON {TABLE} "
        f"WHEN OLD.chain_tx IS NOT NULL OR {changed} BEGIN SELECT RAISE(ABORT, '{MSG}'); END",
        f"CREATE TRIGGER ledger_no_delete BEFORE DELETE ON {TABLE} BEGIN SELECT RAISE(ABORT, '{MSG}'); END",
    ]


def _postgres() -> list[str]:
    changed = " OR ".join(f"NEW.{c} IS DISTINCT FROM OLD.{c}" for c in _frozen())
    cols = ", ".join(f"ADD COLUMN IF NOT EXISTS {c}" for c in (
        "seq integer UNIQUE", "source_raw text", "source_auth text",
        "stamped_at timestamptz", "stamp_late boolean", "donor_name text", "name_salt varchar(64)"))
    return [
        f"ALTER TABLE {TABLE} {cols}",   # tables made before 2026-11-20
        f"""CREATE OR REPLACE FUNCTION ledger_insert_only() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'UPDATE' THEN
    IF OLD.chain_tx IS NULL AND NOT ({changed}) THEN
      RETURN NEW;
    END IF;
  END IF;
  RAISE EXCEPTION '{MSG}';
END $$ LANGUAGE plpgsql""",
        f"DROP TRIGGER IF EXISTS ledger_insert_only_row ON {TABLE}",
        f"CREATE TRIGGER ledger_insert_only_row BEFORE UPDATE OR DELETE ON {TABLE} "
        "FOR EACH ROW EXECUTE FUNCTION ledger_insert_only()",
        f"DROP TRIGGER IF EXISTS ledger_insert_only_truncate ON {TABLE}",
        f"CREATE TRIGGER ledger_insert_only_truncate BEFORE TRUNCATE ON {TABLE} "
        "FOR EACH STATEMENT EXECUTE FUNCTION ledger_insert_only()",
    ]


def install(engine: Engine) -> None:
    """Create ledger_records (and audit_log) if missing and install the insert-only triggers. Idempotent."""
    models.LedgerRecord.__table__.create(engine, checkfirst=True)
    models.AuditLog.__table__.create(engine, checkfirst=True)
    stmts = {"sqlite": _sqlite, "postgresql": _postgres}.get(engine.dialect.name)
    if stmts is None:
        raise RuntimeError(f"no insert-only guard for {engine.dialect.name}")
    with engine.begin() as c:
        for s in stmts():
            c.exec_driver_sql(s)
