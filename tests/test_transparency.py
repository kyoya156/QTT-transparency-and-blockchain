import datetime
import json

import pytest

from transparency import batch, ledger, merkle
from transparency.anchor import LocalAnchor

DAY = "2026-11-16"


@pytest.fixture
def env(tmp_path):
    anchor = LocalAnchor(tmp_path / "anchor.jsonl")
    batch.build(DAY, ledger.synthetic_day(datetime.date.fromisoformat(DAY), n=11), tmp_path, anchor)
    return tmp_path, anchor


@pytest.mark.parametrize("n", [1, 2, 3, 5, 8, 11])
def test_every_leaf_proves(n):
    recs = ledger.synthetic_day(datetime.date(2026, 11, 16), n=n)
    salts = [bytes([i]) * 16 for i in range(n)]
    leaves = [merkle.leaf_hash(r, s) for r, s in zip(recs, salts)]
    r = merkle.root(leaves).hex()
    for i in range(n):
        assert merkle.verify(recs[i], salts[i], merkle.proof(leaves, i), r)


def test_valid_proof_verifies(env):
    d, anchor = env
    ok, _ = batch.verify(batch.prove(DAY, f"{DAY}-004", d), anchor)
    assert ok


def test_tampered_amount_fails(env):
    d, anchor = env
    p = batch.prove(DAY, f"{DAY}-004", d)
    p["record"]["amount_vnd"] += 1000
    assert not batch.verify(p, anchor)[0]


def test_self_supplied_root_is_ignored(env):
    d, anchor = env
    p = batch.prove(DAY, f"{DAY}-004", d)
    p["record"]["amount_vnd"] += 1000
    p["root"] = "00" * 32
    assert not batch.verify(p, anchor)[0]


def test_same_day_cannot_be_anchored_twice(env):
    d, anchor = env
    with pytest.raises(ValueError):
        batch.build(DAY, ledger.synthetic_day(datetime.date(2026, 11, 16)), d, anchor)


def test_tampered_chain_detected(env):
    d, anchor = env
    batch.build("2026-11-17", ledger.synthetic_day(datetime.date(2026, 11, 17)), d, anchor)
    assert anchor.check_chain()
    lines = anchor.path.read_text().splitlines()
    first = json.loads(lines[0]); first["root"] = "ab" * 32
    anchor.path.write_text("\n".join([json.dumps(first)] + lines[1:]) + "\n")
    assert not anchor.check_chain()


def test_public_file_hides_records(env):
    d, _ = env
    text = (d / f"{DAY}.public.json").read_text()
    assert "amount_vnd" not in text and "counterparty" not in text
