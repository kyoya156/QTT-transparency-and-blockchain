"""Listener: SePay message -> ledger_records -> fake chain. No network."""
import json
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from tests.test_chain_bridge import SECRET, FakeLedger
from transparency import chain, listener, merkle, sepay

KEY = "hook-secret"
PAYLOAD = {"id": 100750702, "gateway": "MBBank", "transactionDate": "2026-11-19 10:53:00", "accountNumber": "1",
           "subAccount": None, "code": None, "content": "chuyen tien", "transferType": "in",
           "description": "", "transferAmount": 2000, "referenceCode": "FT1", "accumulated": 0}


@pytest.fixture
def world():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    models.LedgerRecord.__table__.create(eng)
    sessions = sessionmaker(bind=eng, expire_on_commit=False)
    fake = FakeLedger()
    client = chain.LedgerClient(fake)
    listener.app.dependency_overrides = {}
    orig = (listener.get_sessions, listener.get_ledger, listener.get_auth)
    listener.get_sessions = lambda: sessions
    listener.get_ledger = lambda: (client, SECRET)
    listener.get_auth = lambda: (KEY, "")
    yield TestClient(listener.app), sessions, fake
    listener.get_sessions, listener.get_ledger, listener.get_auth = orig


def post(http, **kw):
    raw = json.dumps({**PAYLOAD, **kw}).encode()
    ts = int(time.time())
    return http.post("/webhook/sepay", content=raw,
                     headers={"X-SePay-Timestamp": str(ts), "X-SePay-Signature": sepay.sign(KEY, ts, raw)})


def rows(sessions):
    with sessions() as db:
        return db.query(models.LedgerRecord).all()


def test_build_record_temporary_rules():
    tx = sepay.parse(json.dumps(PAYLOAD).encode())
    rec = listener.build_record(tx, prefix="TEST-")
    assert rec["id"] == "TEST-SEPAY-100750702"
    assert rec["donor_id"] == "NO-CODE" and rec["donor_name"] == "Anonymous"
    assert "memo" not in rec and rec["time"] == "2026-11-19T10:53:00+07:00"
    out = listener.build_record({**tx, "direction": "out", "code": "R023"}, prefix="")
    assert out["recipient_id"] == "R023" and out["recipient_type"] == "unassigned"


def test_money_in_stored_and_stamped(world):
    http, sessions, fake = world
    r = post(http)
    assert r.status_code == 200 and r.json() == {"success": True}
    [row] = rows(sessions)
    rec = json.loads(row.record_json)
    assert rec["direction"] == "in" and row.chain_tx
    ref = chain.ref_id(SECRET, rec["id"])
    assert fake.entries[ref][0] == merkle.leaf_hash(rec, bytes.fromhex(row.salt))


def test_repeat_is_acked_not_duplicated(world):
    http, sessions, fake = world
    post(http)
    post(http)
    assert len(rows(sessions)) == 1 and len(fake.entries) == 1


def test_chain_down_then_retry(world, monkeypatch):
    http, sessions, fake = world
    real_send = fake.send
    monkeypatch.setattr(fake, "send", lambda *a: (_ for _ in ()).throw(ConnectionError("rpc down")))
    assert post(http, transferType="out", id=5).json() == {"success": True}
    [row] = rows(sessions)
    assert row.chain_tx is None and row.salt               # saved even though the chain failed
    monkeypatch.setattr(fake, "send", real_send)
    assert listener.stamp_pending() == 1
    assert rows(sessions)[0].chain_tx


def test_bad_signature_stores_nothing(world):
    http, sessions, _ = world
    raw = json.dumps(PAYLOAD).encode()
    r = http.post("/webhook/sepay", content=raw, headers={"X-SePay-Timestamp": str(int(time.time())),
                                                         "X-SePay-Signature": "sha256=00"})
    assert r.status_code == 401 and rows(sessions) == []
