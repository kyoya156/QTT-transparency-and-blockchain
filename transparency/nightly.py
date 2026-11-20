"""Measure 6 (team, 2026-11-19): nightly automatic check of ledger_records against itself and the chain.

    python -m transparency.nightly            # read-only on chain; exit 1 if any problem

Per row: record_json is canonical; salt + record re-hash to the stored leaf; ref_id = HMAC(REFID_SECRET, id);
stored original message hashes to the record's source_hash;
stored donor name + name_salt give donor_name_hash. Across rows: seq 1, 2, 3 ... with no gaps,
prev = leaf of the record before, balance = previous balance +/- amount (record 1 starts from OPENING_BALANCE).
Against the chain: every stamped row's leaf is on chain under its ref_id. Also lists late stamps and rows
still unstamped after LATE_AFTER. Result: one audit_log row ("ledger_check") with the summary.

Not checked yet: that every Recorded event on chain has a row (needs reading contract events).
A clean result means nothing changed since stamping. It does not prove the records are true.
"""
from __future__ import annotations

import datetime
import hashlib
import json

from sqlalchemy.orm import Session

from app import models

from . import chain, merkle, records

LATE_AFTER = datetime.timedelta(minutes=10)


def check(db: Session, client: chain.LedgerClient | None, secret: bytes, opening: int,
          now: datetime.datetime | None = None) -> dict:
    now = now or datetime.datetime.now(datetime.timezone.utc)
    problems: list[dict] = []
    late: list[str] = []
    unstamped: list[str] = []

    def bad(row, what):
        problems.append({"id": row.source_tx_id, "seq": row.seq, "problem": what})

    rows = db.query(models.LedgerRecord).order_by(models.LedgerRecord.seq.is_(None), models.LedgerRecord.seq,
                                                  models.LedgerRecord.id).all()
    prev_leaf, prev_balance, expect_seq = records.GENESIS, opening, 1
    for row in rows:
        try:
            rec = json.loads(row.record_json)
        except ValueError:
            bad(row, "record_json is not JSON")
            continue
        if merkle.canonical(rec).decode("utf-8") != row.record_json:
            bad(row, "record_json is not in canonical form")
        if "0x" + merkle.leaf_hash(rec, bytes.fromhex(row.salt)).hex() != row.leaf:
            bad(row, "record + salt do not give the stored leaf")
        if row.donor_name is not None and (not row.name_salt or rec.get("donor_name_hash") !=
                                           records.name_hash(row.donor_name, bytes.fromhex(row.name_salt))):
            bad(row, "stored donor name does not match donor_name_hash")
        if "0x" + chain.ref_id(secret, rec.get("id", "")).hex() != row.ref_id:
            bad(row, "ref_id does not match the record id")

        if row.seq is None or "seq" not in rec:
            bad(row, "no seq: record made before measures 1-3")
        else:
            if rec["seq"] != row.seq:
                bad(row, f"seq column {row.seq} differs from record seq {rec['seq']}")
            if row.seq != expect_seq:
                bad(row, f"expected seq {expect_seq}: records missing or out of order")
            if rec.get("prev") != prev_leaf:
                bad(row, "prev does not equal the leaf of the record before")
            if records.balance_before(rec) != prev_balance:
                bad(row, f"balance does not follow: started from {records.balance_before(rec)}, "
                         f"previous balance was {prev_balance}")
            if row.source_raw is not None and \
                    "0x" + hashlib.sha256(row.source_raw.encode("utf-8")).hexdigest() != rec.get("source_hash"):
                bad(row, "stored original message does not match source_hash")
            expect_seq, prev_leaf, prev_balance = row.seq + 1, row.leaf, rec["balance"]

        if row.chain_tx:
            if row.stamp_late:
                late.append(row.source_tx_id)
            if client is not None:
                e = client.entry(bytes.fromhex(row.ref_id[2:]))
                if e is None:
                    bad(row, "has a chain tx but nothing is on chain under its ref_id")
                elif "0x" + e["leaf"].hex() != row.leaf:
                    bad(row, "leaf on chain differs from the stored leaf")
        elif row.anchor_day is None:
            t = datetime.datetime.fromisoformat(rec["time"]) if "time" in rec else None
            if t is None or now - t > LATE_AFTER:
                unstamped.append(row.source_tx_id)

    return {"checked_at": now.isoformat(), "rows": len(rows), "ok": not problems,
            "problems": problems, "late_stamps": late, "unstamped": unstamped,
            "chain_checked": client is not None}


def run(db: Session, client, secret: bytes, opening: int) -> dict:
    result = check(db, client, secret, opening)
    db.add(models.AuditLog(action="ledger_check", detail=json.dumps(result, ensure_ascii=False)))
    db.commit()
    return result


def _main() -> int:
    from . import listener

    env = chain.load_env()
    secret = (listener._env("REFID_SECRET") or "").encode("utf-8")
    if not secret:
        print("REFID_SECRET missing in chain/.env")
        return 2
    client, _, _ = chain.from_env(env, write=False)
    with listener.get_sessions()() as db:
        result = run(db, client, secret, listener.opening_balance())
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] and not result["unstamped"] else 1


if __name__ == "__main__":
    raise SystemExit(_main())
