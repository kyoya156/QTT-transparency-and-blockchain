"""Readable transparency records, behind the same department permissions as the rest of the app.

The chain stores only hashes (contract v3). The readable record lives here:
- money in  -> needs read access to table label 'bank_transaction'
- money out -> needs read access to table label 'disbursement'
admin/dev read everything. Every read and every refusal goes to the audit log.
A reader gets the record and its salt, so they can re-check the hash on chain themselves (POST /verify).
"""
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from transparency import chain, merkle

from .. import access, models
from ..auth import current_user
from ..db import get_db

router = APIRouter(prefix="/api/ledger")
TABLE_FOR = {"in": "bank_transaction", "out": "disbursement"}


def store(db: Session, rec: dict, salt: bytes, ref: bytes, chain_tx: str | None = None,
          anchor_day: str | None = None) -> models.LedgerRecord:
    """Save a record and its salt before (or right after) sending its leaf. Not committed."""
    row = models.LedgerRecord(
        source_tx_id=rec["id"], direction=rec["direction"],
        record_json=merkle.canonical(rec).decode("utf-8"), salt=salt.hex(),
        ref_id="0x" + bytes(ref).hex(), leaf="0x" + merkle.leaf_hash(rec, salt).hex(),
        chain_tx=chain_tx, anchor_day=anchor_day)
    db.add(row)
    db.flush()
    return row


def readable_directions(db: Session, user) -> list[str]:
    return [d for d, table in TABLE_FOR.items() if access.can_read_table(db, user, table)]


def _live_client():
    client, _, _ = chain.from_env(write=False)
    return client


def chain_client_factory():
    """Dependency returning a factory, so the live chain is only contacted when check_chain=true.
    Tests override this with a fake."""
    return _live_client


def _out(row: models.LedgerRecord) -> dict:
    return {"source_tx_id": row.source_tx_id, "direction": row.direction, "record": json.loads(row.record_json),
            "salt": row.salt, "ref_id": row.ref_id, "leaf": row.leaf, "chain_tx": row.chain_tx,
            "anchor_day": row.anchor_day}


@router.get("/records")
def list_records(direction: str | None = Query(default=None, pattern="^(in|out)$"),
                 limit: int = Query(default=50, ge=1, le=500), offset: int = Query(default=0, ge=0),
                 user=Depends(current_user), db: Session = Depends(get_db)):
    allowed = readable_directions(db, user)
    wanted = [direction] if direction else allowed
    if not wanted or any(d not in allowed for d in wanted):
        access.audit(db, user, "ledger_denied", detail={"direction": direction})
        db.commit()
        raise HTTPException(403, "your department may not read these records")
    rows = (db.query(models.LedgerRecord).filter(models.LedgerRecord.direction.in_(wanted))
            .order_by(models.LedgerRecord.id.desc()).offset(offset).limit(limit).all())
    access.audit(db, user, "ledger_read", detail={"directions": wanted, "ids": [r.source_tx_id for r in rows]})
    db.commit()
    return {"records": [_out(r) for r in rows]}


@router.get("/records/{source_tx_id}")
def get_record(source_tx_id: str, check_chain: bool = False, user=Depends(current_user),
               db: Session = Depends(get_db), ledger_client=Depends(chain_client_factory)):
    row = db.query(models.LedgerRecord).filter_by(source_tx_id=source_tx_id).one_or_none()
    if row is None or row.direction not in readable_directions(db, user):
        # Same answer for "missing" and "not allowed", so ids cannot be probed.
        access.audit(db, user, "ledger_denied", detail={"id": source_tx_id})
        db.commit()
        raise HTTPException(404, "record not found")
    out = _out(row)
    if check_chain:
        if row.chain_tx is None and row.anchor_day:
            out["chain"] = {"checked": False, "reason": "history row: verify with its day's Merkle proof"}
        else:
            try:
                ok, ts = ledger_client().verify(bytes.fromhex(row.ref_id[2:]),
                                                    merkle.leaf_hash(out["record"], bytes.fromhex(row.salt)))
            except Exception as exc:
                raise HTTPException(503, f"chain unreachable: {type(exc).__name__}") from None
            out["chain"] = {"checked": True, "match": ok, "block_timestamp": ts}
    access.audit(db, user, "ledger_read", detail={"id": source_tx_id, "check_chain": check_chain})
    db.commit()
    return out
