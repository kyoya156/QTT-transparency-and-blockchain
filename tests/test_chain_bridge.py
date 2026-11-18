"""Bridge tests against an in-memory fake of TransparencyLedger. No network, no web3 needed."""
import datetime

import pytest

from transparency import batch, chain, ledger, merkle, records

SECRET = b"test-secret"


class FakeLedger:
    """Mirrors the v3 contract rules: refId write-once, day write-once, hash only."""

    def __init__(self):
        self.entries, self.batches, self.sent, self.payloads, self.t = {}, {}, [], [], 1_700_000_000

    def call(self, name, *args):
        if name == "entries":
            return self.entries.get(args[0], (b"\x00" * 32, 0))
        if name == "batches":
            return self.batches.get(args[0], (b"\x00" * 32, 0, 0))
        raise AssertionError(name)

    def send(self, name, *args):
        self.t += 2
        self.sent.append(name)
        self.payloads.append(args)
        if name == "record":
            ref, leaf = args
            if ref in self.entries:
                raise RuntimeError("AlreadyRecorded")
            self.entries[ref] = (leaf, self.t)
        elif name == "anchorBatch":
            day, root, count = args
            if day in self.batches:
                raise RuntimeError("DayAlreadyAnchored")
            self.batches[day] = (root, count, self.t)
        else:
            raise AssertionError(name)
        return {"tx_hash": "0x%064x" % len(self.sent), "block": len(self.sent)}


@pytest.fixture
def fake():
    return FakeLedger()


T = "2026-11-16T09:30:00+07:00"


def _rec(direction="in", amount=500_000):
    if direction == "in":
        r = records.income("BANK-1", amount, "D-001", T, donor_name="Lan")
    else:
        r = records.expense("BANK-1", amount, "R-017", T)
    salt = bytes(16)
    return r, salt, merkle.leaf_hash(r, salt)


def test_ref_id_is_stable_and_secret_dependent():
    a = chain.ref_id(SECRET, "BANK-123")
    assert len(a) == 32 and a == chain.ref_id(SECRET, "BANK-123")
    assert a != chain.ref_id(b"other", "BANK-123")
    with pytest.raises(ValueError):
        chain.ref_id(b"", "BANK-123")


def test_day_number():
    assert chain.day_number("2026-11-16") == 20261116


def test_record_then_verify(fake):
    c = chain.LedgerClient(fake)
    r, salt, leaf = _rec()
    ref = chain.ref_id(SECRET, r["id"])
    assert c.record(ref, leaf).status == "sent"
    ok, ts = c.verify(ref, merkle.leaf_hash(r, salt))
    assert ok and ts
    assert c.entry(ref) == {"leaf": leaf, "recorded_at": ts}


def test_only_hashes_reach_the_chain(fake):
    c = chain.LedgerClient(fake)
    for direction in ("in", "out"):
        r, _, leaf = _rec(direction)
        c.record(chain.ref_id(SECRET, direction), leaf)
    for args in fake.payloads:
        assert all(isinstance(a, bytes) and len(a) == 32 for a in args)
    assert fake.sent == ["record", "record"]


def test_retry_does_not_send_twice(fake):
    c = chain.LedgerClient(fake)
    _, _, leaf = _rec("out")
    ref = chain.ref_id(SECRET, "BANK-1")
    c.record(ref, leaf)
    assert c.record(ref, leaf).status == "exists"
    assert fake.sent == ["record"]


def test_same_ref_different_leaf_is_a_conflict(fake):
    c = chain.LedgerClient(fake)
    _, _, leaf_in = _rec("in")
    _, _, leaf_out = _rec("out")
    ref = chain.ref_id(SECRET, "BANK-1")
    c.record(ref, leaf_in)
    with pytest.raises(chain.ConflictError):
        c.record(ref, leaf_out)


def test_tampered_record_fails_verify(fake):
    c = chain.LedgerClient(fake)
    r, salt, leaf = _rec()
    ref = chain.ref_id(SECRET, r["id"])
    c.record(ref, leaf)
    r["amount"] += 1000
    assert c.verify(ref, merkle.leaf_hash(r, salt)) == (False, None)
    assert c.verify(chain.ref_id(SECRET, "unknown"), leaf) == (False, None)


def test_bad_inputs_rejected(fake):
    c = chain.LedgerClient(fake)
    with pytest.raises(ValueError):
        c.record(b"\x01" * 31, b"\x01" * 32)
    with pytest.raises(ValueError):
        chain.unix_time("2026-11-16T09:30:00")


def test_batch_pipeline_on_chain_anchor(fake, tmp_path):
    """batch.build/prove/verify work unchanged with the on-chain anchor."""
    anchor = chain.BaseSepoliaAnchor(fake)
    day = "2026-11-16"
    batch.build(day, ledger.synthetic_day(datetime.date.fromisoformat(day), n=7), tmp_path, anchor)
    assert batch.verify(batch.prove(day, f"{day}-003", tmp_path), anchor)[0]
    p = batch.prove(day, f"{day}-003", tmp_path)
    p["record"]["amount_vnd"] += 1
    assert not batch.verify(p, anchor)[0]
    with pytest.raises(ValueError):
        anchor.publish(day, "11" * 32, 1)
    assert fake.sent == ["anchorBatch"]


def test_load_env_reads_file_without_exporting(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text("# comment\nCONTRACT_ADDRESS=0xabc\nREFID_SECRET='s'\n", encoding="utf-8")
    monkeypatch.delenv("CONTRACT_ADDRESS", raising=False)
    env = chain.load_env(f)
    assert env["CONTRACT_ADDRESS"] == "0xabc" and env["REFID_SECRET"] == "s"
