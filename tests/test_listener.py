"""Listener: SePay message -> ledger_records -> fake chain. No network. Measures 1-5."""
import datetime
import json
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from tests.test_chain_bridge import SECRET, FakeLedger
from transparency import chain, guard, listener, merkle, records, sepay

KEY = "hook-secret"


def vn_now(minutes_ago=0):
    t = datetime.datetime.now(sepay.VN_TZ) - datetime.timedelta(minutes=minutes_ago)
    return t.strftime("%Y-%m-%d %H:%M:%S")


PAYLOAD = {"id": 100750702, "gateway": "MBBank", "transactionDate": "2026-11-19 10:53:00", "accountNumber": "1",
           "subAccount": None, "code": None, "content": "chuyen tien", "transferType": "in",
           "description": "", "transferAmount": 2000, "referenceCode": "FT1", "accumulated": 0}


@pytest.fixture
def world(monkeypatch):
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    guard.install(eng)
    sessions = sessionmaker(bind=eng, expire_on_commit=False)
    fake = FakeLedger()
    client = chain.LedgerClient(fake)
    monkeypatch.setattr(listener, "get_sessions", lambda: sessions)
    monkeypatch.setattr(listener, "get_ledger", lambda: (client, SECRET))
    monkeypatch.setattr(listener, "get_auth", lambda: (KEY, ""))
    monkeypatch.setenv("OPENING_BALANCE", "10000")
    monkeypatch.setenv("LISTENER_ID_PREFIX", "TEST-")
    yield TestClient(listener.app), sessions, fake, eng


def raw_of(**kw):
    return json.dumps({**PAYLOAD, "transactionDate": vn_now(), **kw}).encode()


def post_raw(http, raw):
    ts = int(time.time())
    return http.post("/webhook/sepay", content=raw,
                     headers={"X-SePay-Timestamp": str(ts), "X-SePay-Signature": sepay.sign(KEY, ts, raw)})


def post(http, **kw):
    return post_raw(http, raw_of(**kw))


def rows(sessions):
    with sessions() as db:
        return db.query(models.LedgerRecord).order_by(models.LedgerRecord.seq).all()


def audits(sessions, action):
    with sessions() as db:
        return [json.loads(a.detail) for a in db.query(models.AuditLog).filter_by(action=action)]


def test_build_record_temporary_rules():
    tx = sepay.parse(json.dumps(PAYLOAD).encode())
    rec = listener.build_record(tx, prefix="TEST-")
    assert rec["id"] == "TEST-SEPAY-100750702"
    assert rec["donor_id"] == "NO-CODE" and rec["donor_name"] == "Anonymous"
    assert "memo" not in rec and rec["time"] == "2026-11-19T10:53:00+07:00"
    out = listener.build_record({**tx, "direction": "out", "code": "R023"}, prefix="")
    assert out["recipient_id"] == "R023" and out["recipient_type"] == "unassigned"


def test_money_in_stored_and_stamped(world):
    http, sessions, fake, _ = world
    raw = raw_of()
    r = post_raw(http, raw)
    assert r.status_code == 200 and r.json() == {"success": True}
    [row] = rows(sessions)
    rec = json.loads(row.record_json)
    assert rec["direction"] == "in" and row.chain_tx and row.stamped_at and row.stamp_late is False
    assert rec["seq"] == 1 and rec["prev"] == records.GENESIS and rec["balance"] == 12000
    assert row.source_raw.encode() == raw and rec["source_hash"] == listener.source_hash(raw)
    assert json.loads(row.source_auth)["x-sepay-signature"].startswith("sha256=")
    ref = chain.ref_id(SECRET, rec["id"])
    assert fake.entries[ref][0] == merkle.leaf_hash(rec, bytes.fromhex(row.salt))


def test_records_are_linked_with_running_balance(world):
    http, sessions, _, _ = world
    post(http, id=1, transferAmount=5000)
    post(http, id=2, transferType="out", transferAmount=3000)
    post(http, id=3, transferAmount=1)
    a, b, c = rows(sessions)
    ra, rb, rc = (json.loads(r.record_json) for r in (a, b, c))
    assert [r["seq"] for r in (ra, rb, rc)] == [1, 2, 3]
    assert rb["prev"] == a.leaf and rc["prev"] == b.leaf
    assert [r["balance"] for r in (ra, rb, rc)] == [15000, 12000, 12001]


def test_repeat_is_acked_not_duplicated(world):
    http, sessions, fake, _ = world
    raw = raw_of()
    post_raw(http, raw)
    post_raw(http, raw)
    assert len(rows(sessions)) == 1 and len(fake.entries) == 1


def test_future_bank_time_refused(world):
    http, sessions, _, _ = world
    future = (datetime.datetime.now(sepay.VN_TZ) + datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    assert post(http, transactionDate=future).status_code == 400 and rows(sessions) == []


def test_late_stamp_flagged_and_audited(world):
    http, sessions, _, _ = world
    post(http, transactionDate=vn_now(minutes_ago=30))
    [row] = rows(sessions)
    assert row.chain_tx and row.stamp_late is True
    [a] = audits(sessions, "ledger_late_stamp")
    assert a["id"] == row.source_tx_id


def chain_down(monkeypatch, fake):
    real = fake.send
    monkeypatch.setattr(fake, "send", lambda *a: (_ for _ in ()).throw(ConnectionError("rpc down")))
    return lambda: monkeypatch.setattr(fake, "send", real)


def test_chain_down_then_startup_retry_rebuilds_from_stored_original(world, monkeypatch):
    http, sessions, fake, _ = world
    up = chain_down(monkeypatch, fake)
    assert post(http, transferType="out", id=5).json() == {"success": True}
    [row] = rows(sessions)
    assert row.chain_tx is None and row.salt               # saved even though the chain failed
    up()
    assert listener.stamp_pending() == 1
    assert rows(sessions)[0].chain_tx


def edit_row_bypassing_guard(eng, sql):
    with eng.begin() as c:
        c.exec_driver_sql("DROP TRIGGER ledger_no_update")
        c.exec_driver_sql(sql)
    guard.install(eng)


def test_resend_after_db_edit_is_not_stamped(world, monkeypatch):
    http, sessions, fake, eng = world
    up = chain_down(monkeypatch, fake)
    raw = raw_of(transferAmount=500000)
    post_raw(http, raw)
    up()
    # Someone with database control edits the unstamped record (and its leaf, so it looks consistent).
    [row] = rows(sessions)
    rec = {**json.loads(row.record_json), "amount": 50000, "balance": 60000}
    leaf = "0x" + merkle.leaf_hash(rec, bytes.fromhex(row.salt)).hex()
    edit_row_bypassing_guard(eng, f"UPDATE ledger_records SET record_json='{merkle.canonical(rec).decode()}', "
                                  f"leaf='{leaf}'")
    post_raw(http, raw)                                    # SePay resends the real message
    assert rows(sessions)[0].chain_tx is None and fake.entries == {}
    assert audits(sessions, "ledger_tamper")


def test_resend_of_unstamped_record_stamps_when_unchanged(world, monkeypatch):
    http, sessions, fake, _ = world
    up = chain_down(monkeypatch, fake)
    raw = raw_of()
    post_raw(http, raw)
    up()
    post_raw(http, raw)
    assert rows(sessions)[0].chain_tx and not audits(sessions, "ledger_tamper")


def test_startup_retry_refuses_edited_original(world, monkeypatch):
    http, sessions, fake, eng = world
    up = chain_down(monkeypatch, fake)
    post(http)
    up()
    edit_row_bypassing_guard(eng, "UPDATE ledger_records SET source_raw = replace(source_raw, '2000', '9000')")
    assert listener.stamp_pending() == 0 and fake.entries == {}
    assert audits(sessions, "ledger_tamper")


def test_bad_signature_stores_nothing(world):
    http, sessions, _, _ = world
    raw = raw_of()
    r = http.post("/webhook/sepay", content=raw, headers={"X-SePay-Timestamp": str(int(time.time())),
                                                         "X-SePay-Signature": "sha256=00"})
    assert r.status_code == 401 and rows(sessions) == []
