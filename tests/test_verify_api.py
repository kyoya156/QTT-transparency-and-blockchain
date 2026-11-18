"""Verify endpoint against the in-memory fake contract. No network."""
import pytest
from fastapi.testclient import TestClient

from tests.test_chain_bridge import SECRET, FakeLedger
from transparency import api, chain, merkle, records

T = "2026-11-16T09:30:00+07:00"
SALT = bytes(range(16))


@pytest.fixture
def setup():
    fake = FakeLedger()
    client = chain.LedgerClient(fake)
    api.app.dependency_overrides[api.get_ledger] = lambda: (client, SECRET)
    rec = records.income("BANK-9", 250_000, "D-002", T, donor_name="Lan")
    client.record(chain.ref_id(SECRET, rec["id"]), merkle.leaf_hash(rec, SALT))
    yield TestClient(api.app), rec, fake
    api.app.dependency_overrides.clear()


def test_match_returns_block_time(setup):
    http, rec, fake = setup
    r = http.post("/verify", json={"record": rec, "salt": SALT.hex()})
    assert r.status_code == 200
    d = r.json()
    assert d["match"] and d["found"]
    assert d["block_timestamp"] == fake.entries[chain.ref_id(SECRET, rec["id"])][1]
    assert d["block_time"].endswith("+00:00")
    assert "on_chain" not in d
    assert "does not prove" in d["note"]


def test_tampered_record_found_but_no_match(setup):
    http, rec, _ = setup
    r = http.post("/verify", json={"record": {**rec, "amount": 260_000}, "salt": SALT.hex()}).json()
    assert r["found"] and not r["match"] and r["block_time"] is None


def test_wrong_salt_no_match(setup):
    http, rec, _ = setup
    r = http.post("/verify", json={"record": rec, "salt": "00" * 16}).json()
    assert r["found"] and not r["match"]


def test_unknown_record_not_found(setup):
    http, rec, _ = setup
    r = http.post("/verify", json={"record": {**rec, "id": "BANK-404"}, "salt": SALT.hex()}).json()
    assert not r["found"] and not r["match"]

@pytest.mark.parametrize("body", [
    {"record": {"amount": 1}, "salt": "00"},
    {"record": {"id": "X"}, "salt": "zz"},
    {"record": {"id": "X"}, "salt": ""},
])
def test_bad_input_422(setup, body):
    assert setup[0].post("/verify", json=body).status_code == 422


def test_chain_down_503(setup):
    class Down:
        def call(self, *a):
            raise ConnectionError("rpc")
    api.app.dependency_overrides[api.get_ledger] = lambda: (chain.LedgerClient(Down()), SECRET)
    r = setup[0].post("/verify", json={"record": {"id": "X"}, "salt": "00"})
    assert r.status_code == 503
