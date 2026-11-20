"""Measure 4 (insert-only guard) and measure 6 (nightly check). SQLite, fake chain."""
import json

import pytest
from sqlalchemy import create_engine, exc, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.api.ledger import store
from tests.test_chain_bridge import SECRET, FakeLedger
from transparency import chain, guard, merkle, nightly, records

T = "2026-11-16T09:30:00+07:00"
SRC = "0x" + "cd" * 32
OPENING = 1000


@pytest.fixture
def db():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    guard.install(eng)
    s = sessionmaker(bind=eng, expire_on_commit=False)()
    yield s, eng
    s.close()


def add_chain(s, client, n=3, stamp=True):
    prev, bal = records.GENESIS, OPENING
    for i in range(1, n + 1):
        base = records.income(f"B-{i}", 100 * i, "D-1", T) if i % 2 else records.expense(f"B-{i}", 50, "R-1", T)
        rec = records.link(base, i, prev, bal, SRC)
        salt = bytes([i]) * 16
        ref = chain.ref_id(SECRET, rec["id"])
        tx = client.record(ref, merkle.leaf_hash(rec, salt)).tx_hash if stamp else None
        row = store(s, rec, salt, ref, chain_tx=tx)
        prev, bal = row.leaf, rec["balance"]
    s.commit()


def test_update_and_delete_refused(db):
    s, _ = db
    add_chain(s, chain.LedgerClient(FakeLedger()), n=1)
    for sql in ("UPDATE ledger_records SET record_json = '{}'", "UPDATE ledger_records SET chain_tx = '0x1'",
                "DELETE FROM ledger_records"):
        with pytest.raises(exc.DatabaseError, match="insert-only"):
            s.execute(text(sql))
        s.rollback()


def test_stamp_columns_can_be_filled_once(db):
    s, _ = db
    add_chain(s, chain.LedgerClient(FakeLedger()), n=1, stamp=False)
    row = s.query(models.LedgerRecord).one()
    row.chain_tx, row.stamp_late = "0x" + "11" * 32, False
    s.commit()
    row.chain_tx = "0x" + "22" * 32
    with pytest.raises(exc.DatabaseError, match="insert-only"):
        s.commit()


def test_clean_ledger_passes(db):
    s, _ = db
    client = chain.LedgerClient(FakeLedger())
    add_chain(s, client)
    r = nightly.check(s, client, SECRET, OPENING)
    assert r["ok"] and r["rows"] == 3 and r["unstamped"] == [] and r["problems"] == []


def tamper(eng, sql):
    with eng.begin() as c:
        c.exec_driver_sql("DROP TRIGGER ledger_no_update")
        c.exec_driver_sql("DROP TRIGGER ledger_no_delete")
        c.exec_driver_sql(sql)


def problems(s, client, opening=OPENING):
    s.expire_all()
    return [p["problem"] for p in nightly.check(s, client, SECRET, opening)["problems"]]


def test_edited_amount_is_caught(db):
    s, eng = db
    client = chain.LedgerClient(FakeLedger())
    add_chain(s, client)
    tamper(eng, "UPDATE ledger_records SET record_json = replace(record_json, '\"amount\":100,', "
                "'\"amount\":900,') WHERE seq = 1")
    assert "record + salt do not give the stored leaf" in problems(s, client)


def test_deleted_record_breaks_the_links(db):
    s, eng = db
    client = chain.LedgerClient(FakeLedger())
    add_chain(s, client)
    tamper(eng, "DELETE FROM ledger_records WHERE seq = 2")
    found = problems(s, client)
    assert any("expected seq 2" in p for p in found)
    assert "prev does not equal the leaf of the record before" in found


def test_consistent_rewrite_is_caught_by_the_chain(db):
    s, eng = db
    client = chain.LedgerClient(FakeLedger())
    add_chain(s, client, n=1)
    row = s.query(models.LedgerRecord).one()
    rec = {**json.loads(row.record_json), "amount": 900, "balance": OPENING + 900}
    leaf = "0x" + merkle.leaf_hash(rec, bytes.fromhex(row.salt)).hex()
    tamper(eng, f"UPDATE ledger_records SET record_json = '{merkle.canonical(rec).decode()}', leaf = '{leaf}'")
    assert problems(s, client) == ["leaf on chain differs from the stored leaf"]


def test_wrong_opening_balance_is_caught(db):
    s, _ = db
    client = chain.LedgerClient(FakeLedger())
    add_chain(s, client)
    assert any("balance does not follow" in p for p in problems(s, client, opening=0))


def test_run_writes_audit_row(db):
    s, _ = db
    client = chain.LedgerClient(FakeLedger())
    add_chain(s, client, n=2, stamp=False)
    r = nightly.run(s, client, SECRET, OPENING)
    assert r["unstamped"] == ["B-1", "B-2"]
    [a] = s.query(models.AuditLog).filter_by(action="ledger_check").all()
    assert json.loads(a.detail)["rows"] == 2
