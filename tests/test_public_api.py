"""GET /public/records: what the public dashboard gets. Fake chain, in-memory database."""
import json
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from tests import test_listener as tl
from tests.test_chain_bridge import SECRET, FakeLedger
from transparency import api, chain, guard, listener, sepay


@pytest.fixture
def world(monkeypatch):
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    guard.install(eng)
    sessions = sessionmaker(bind=eng, expire_on_commit=False)
    client = chain.LedgerClient(FakeLedger())
    monkeypatch.setattr(listener, "get_sessions", lambda: sessions)
    monkeypatch.setattr(listener, "get_ledger", lambda: (client, SECRET))
    monkeypatch.setattr(listener, "get_auth", lambda: (tl.KEY, ""))
    monkeypatch.setenv("OPENING_BALANCE", "0")
    api.app.dependency_overrides[api.get_sessions] = lambda: sessions
    api.app.dependency_overrides[api.get_ledger] = lambda: (client, SECRET)
    yield TestClient(listener.app), TestClient(api.app), monkeypatch
    api.app.dependency_overrides.clear()


def send(http, **kw):
    raw = tl.raw_of(**kw)
    ts = int(time.time())
    http.post("/webhook/sepay", content=raw,
              headers={"X-SePay-Timestamp": str(ts), "X-SePay-Signature": sepay.sign(tl.KEY, ts, raw)})


def test_public_records_verify_and_hide_private_fields(world):
    hook, pub, mp = world
    mp.setenv("LISTENER_ID_PREFIX", "")
    send(hook, id=1)
    send(hook, id=2, transferType="out", transferAmount=500)
    body = pub.get("/public/records").json()
    assert [r["seq"] for r in body["records"]] == [2, 1]
    text = json.dumps(body)
    for private in ("donor_name\"", "name_salt", "source_raw", "chuyen tien", "x-sepay"):
        assert private not in text
    for r in body["records"]:
        assert r["chain_link"].startswith("https://sepolia.basescan.org/tx/0x")
        v = pub.post("/verify", json={"record": r["record"], "salt": r["salt"]}).json()
        assert v["match"] and v["leaf"] == r["leaf"]


def test_test_records_hidden_by_default(world):
    hook, pub, mp = world
    mp.setenv("LISTENER_ID_PREFIX", "TEST-")
    send(hook, id=3)
    assert pub.get("/public/records").json()["records"] == []
    assert len(pub.get("/public/records?include_test=true").json()["records"]) == 1
