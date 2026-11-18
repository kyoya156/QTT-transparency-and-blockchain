"""Bridge tests against an in-memory fake of TransparencyLedger. No network, no web3 needed."""
import datetime

import pytest

from transparency import batch, chain, ledger, merkle, records

SECRET = b"test-secret"


class FakeLedger:
    """Mirrors the contract rules: refId write-once, day write-once, no zero values."""

    def __init__(self):
        self.entries, self.batches, self.sent, self.payloads, self.t = {}, {}, [], [], 1_700_000_000

    def call(self, name, *args):
        if name == "entries":
            return self.entries.get(args[0], (b"\x00" * 32, 0, 0, 0, 0))
        if name == "batches":
            return self.batches.get(args[0], (b"\x00" * 32, 0, 0))
        raise AssertionError(name)

    def send(self, name, *args):
        self.t += 2
        self.sent.append(name)
        if name in ("recordIncome", "recordExpense"):
            ref, leaf, data = args
            if ref in self.entries:
                raise RuntimeError("AlreadyRecorded")
            self.payloads.append(data)
            self.entries[ref] = (leaf, data[0], data[1], self.t, 1 if name == "recordIncome" else 2)
        elif name == "anchorBatch":
            day, root, count = args
            if day in self.batches:
                raise RuntimeError("DayAlreadyAnchored")
            self.batches[day] = (root, count, self.t)
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
    assert c.record(r, ref, leaf).status == "sent"
    ok, ts = c.verify(ref, merkle.leaf_hash(r, salt))
    assert ok and ts
    e = c.entry(ref)
    assert e["amount"] == 500_000 and e["tx_time"] == chain.unix_time(T) and e["direction"] == "in"


def test_income_public_fields_hide_name_by_default(fake):
    c = chain.LedgerClient(fake)
    r, _, leaf = _rec()
    c.record(r, chain.ref_id(SECRET, "a"), leaf)
    assert fake.payloads[-1] == (500_000, chain.unix_time(T), "VND", "D-001", "")
    c.record(r, chain.ref_id(SECRET, "b"), leaf, publish_names=True)
    assert fake.payloads[-1][-1] == "Lan"


def test_expense_public_fields(fake):
    c = chain.LedgerClient(fake)
    r, _, leaf = _rec("out", 200_000)
    c.record(r, chain.ref_id(SECRET, r["id"]), leaf)
    assert fake.sent == ["recordExpense"]
    assert fake.payloads[-1] == (200_000, chain.unix_time(T), "VND", "R-017", "unassigned")


def test_retry_does_not_send_twice(fake):
    c = chain.LedgerClient(fake)
    r, _, leaf = _rec("out")
    ref = chain.ref_id(SECRET, "BANK-1")
    c.record(r, ref, leaf)
    assert c.record(r, ref, leaf).status == "exists"
    assert fake.sent == ["recordExpense"]


def test_same_ref_different_leaf_is_a_conflict(fake):
    c = chain.LedgerClient(fake)
    r_in, _, _ = _rec("in")
    r_out, _, _ = _rec("out")
    ref = chain.ref_id(SECRET, "BANK-1")
    c.record(r_in, ref, b"" * 32)
    with pytest.raises(chain.ConflictError):
        c.record(r_in, ref, b"" * 32)
    with pytest.raises(chain.ConflictError):
        c.record(r_out, ref, b"" * 32)


def test_tampered_record_fails_verify(fake):
    c = chain.LedgerClient(fake)
    r, salt, leaf = _rec()
    ref = chain.ref_id(SECRET, r["id"])
    c.record(r, ref, leaf)
    r["amount"] += 1000
    assert c.verify(ref, merkle.leaf_hash(r, salt)) == (False, None)
    assert c.verify(chain.ref_id(SECRET, "unknown"), leaf) == (False, None)


def test_bad_inputs_rejected(fake):
    c = chain.LedgerClient(fake)
    r, _, _ = _rec()
    with pytest.raises(ValueError):
        c.record({**r, "direction": "sideways"}, b"" * 32, b"" * 32)
    with pytest.raises(ValueError):
        c.record(r, b"" * 31, b"" * 32)
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
