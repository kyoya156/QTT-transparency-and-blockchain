"""SePay adapter + test receiver. No network."""
import json
import time

import pytest
from fastapi.testclient import TestClient

from transparency import sepay, sepay_receiver

SECRET = "test-secret"
PAYLOAD = {
    "id": 92704, "gateway": "MBBank", "transactionDate": "2026-11-19 14:02:37", "accountNumber": "0123499999",
    "subAccount": "", "code": None, "content": "Ung ho quy", "transferType": "in", "description": "",
    "transferAmount": 2000, "accumulated": 19077000, "referenceCode": "MBVCB.3278907687",
}


def _raw(**kw) -> bytes:
    return json.dumps({**PAYLOAD, **kw}).encode()


def test_parse_in_keeps_vietnam_time():
    tx = sepay.parse(_raw())
    assert tx["source_tx_id"] == "SEPAY-92704"
    assert tx["direction"] == "in" and tx["amount"] == 2000
    assert tx["time"] == "2026-11-19T14:02:37+07:00"
    assert tx["balance_after"] == 19077000


def test_parse_out_and_missing_balance():
    tx = sepay.parse(_raw(transferType="out", accumulated=0))
    assert tx["direction"] == "out" and tx["balance_after"] is None


@pytest.mark.parametrize("bad", [{"transferType": "x"}, {"transferAmount": 0}, {"transferAmount": "5"}])
def test_parse_rejects(bad):
    with pytest.raises(ValueError):
        sepay.parse(_raw(**bad))


def test_hmac_ok_and_tampered():
    raw, ts = _raw(), int(time.time())
    sig = sepay.sign(SECRET, ts, raw)
    sepay.check_hmac(SECRET, str(ts), sig, raw)
    with pytest.raises(sepay.AuthError):
        sepay.check_hmac(SECRET, str(ts), sig, _raw(transferAmount=2_000_000))
    with pytest.raises(sepay.AuthError):
        sepay.check_hmac(SECRET, str(ts - 1000), sepay.sign(SECRET, ts - 1000, raw), raw)


def test_apikey():
    sepay.check_apikey("k1", "Apikey k1")
    with pytest.raises(sepay.AuthError):
        sepay.check_apikey("k1", "Apikey k2")


@pytest.fixture
def http(tmp_path, monkeypatch):
    monkeypatch.setattr(sepay_receiver, "LOG", tmp_path / "log.jsonl")
    monkeypatch.setattr(sepay_receiver, "_secret", lambda n: SECRET if n == "SEPAY_WEBHOOK_SECRET" else "")
    return TestClient(sepay_receiver.app)


def _post(http, raw, secret=SECRET):
    ts = int(time.time())
    return http.post("/webhook/sepay", content=raw,
                     headers={"X-SePay-Timestamp": str(ts), "X-SePay-Signature": sepay.sign(secret, ts, raw)})


def test_receiver_logs_once_and_acks_repeats(http):
    raw = _raw()
    for _ in range(2):
        r = _post(http, raw)
        assert r.status_code == 200 and r.json() == {"success": True}
    lines = sepay_receiver.LOG.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["tx"]["source_tx_id"] == "SEPAY-92704"


def test_receiver_refuses_bad_signature(http):
    r = _post(http, _raw(), secret="wrong")
    assert r.status_code == 401
    assert not sepay_receiver.LOG.exists()


def test_receiver_refuses_when_unconfigured(http, monkeypatch):
    monkeypatch.setattr(sepay_receiver, "_secret", lambda n: "")
    assert _post(http, _raw()).status_code == 401
