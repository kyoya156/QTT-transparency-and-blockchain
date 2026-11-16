"""Build, anchor and verify one day's batch.

Two outputs per day:
  public  <day>.public.json  : root, count and leaf hashes. Safe to publish, reveals nothing about the records.
  private <day>.private.json : records and salts. Stays internal; a record plus its salt is the proof for one entry.
"""
from __future__ import annotations

import json
import os
import pathlib

from . import merkle


def build(day: str, records: list[dict], out_dir: str | pathlib.Path, anchor) -> dict:
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    records = sorted(records, key=lambda r: r["id"])
    salts = [os.urandom(16) for _ in records]
    leaves = [merkle.leaf_hash(r, s) for r, s in zip(records, salts)]
    root_hex = merkle.root(leaves).hex()
    block = anchor.publish(day, root_hex, len(records))
    (out / f"{day}.public.json").write_text(json.dumps(
        {"day": day, "root": root_hex, "count": len(records), "leaves": [x.hex() for x in leaves], "anchor": block},
        indent=1), encoding="utf-8")
    (out / f"{day}.private.json").write_text(json.dumps(
        {"day": day, "records": records, "salts": [s.hex() for s in salts]}, indent=1, ensure_ascii=False),
        encoding="utf-8")
    return block


def prove(day: str, record_id: str, out_dir: str | pathlib.Path) -> dict:
    out = pathlib.Path(out_dir)
    pub = json.loads((out / f"{day}.public.json").read_text(encoding="utf-8"))
    priv = json.loads((out / f"{day}.private.json").read_text(encoding="utf-8"))
    idx = next(i for i, r in enumerate(priv["records"]) if r["id"] == record_id)
    leaves = [bytes.fromhex(x) for x in pub["leaves"]]
    return {"day": day, "record": priv["records"][idx], "salt": priv["salts"][idx],
            "path": merkle.proof(leaves, idx), "root": pub["root"]}


def verify(proof: dict, anchor) -> tuple[bool, str]:
    """Check a proof against the anchored root, not against the root inside the proof."""
    block = anchor.get(proof["day"])
    if block is None:
        return False, "day is not anchored"
    if not anchor.check_chain():
        return False, "anchor chain is broken"
    ok = merkle.verify(proof["record"], bytes.fromhex(proof["salt"]), [tuple(p) for p in proof["path"]], block["root"])
    return ok, "record matches the anchored root" if ok else "record does not match the anchored root"
