#!/usr/bin/env python
"""Local transparency pipeline.

    python scripts/transparency.py batch 2026-11-16            # synthetic day, build + anchor
    python scripts/transparency.py prove 2026-11-16 2026-11-16-003 > proof.json
    python scripts/transparency.py verify proof.json
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from transparency import batch, ledger  # noqa: E402
from transparency.anchor import LocalAnchor  # noqa: E402

DATA = Path("transparency_data")


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dir", default=str(DATA))
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("batch"); b.add_argument("day")
    pr = sub.add_parser("prove"); pr.add_argument("day"); pr.add_argument("record_id")
    v = sub.add_parser("verify"); v.add_argument("proof_file")
    a = p.parse_args(argv)
    anchor = LocalAnchor(Path(a.dir) / "anchor.jsonl")
    if a.cmd == "batch":
        day = datetime.date.fromisoformat(a.day)
        block = batch.build(a.day, ledger.synthetic_day(day), a.dir, anchor)
        print(json.dumps(block, indent=1))
    elif a.cmd == "prove":
        print(json.dumps(batch.prove(a.day, a.record_id, a.dir), indent=1, ensure_ascii=False))
    else:
        ok, msg = batch.verify(json.loads(Path(a.proof_file).read_text(encoding="utf-8")), anchor)
        print(("OK: " if ok else "FAIL: ") + msg)
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
