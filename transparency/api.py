"""Verify endpoint: record + salt -> rebuild leaf -> contract verify -> block time.

    uvicorn transparency.api:app --port 8100
    POST /verify  {"record": {...exact stored record...}, "salt": "<hex>"}

A match proves the record existed unchanged at the block time. It does not prove the record is true.
    GET  /public/records   public list for the dashboard: record as hashed + salt + chain link

The chain holds only hashes; /verify returns nothing the caller did not send. Public records hold no readable
donor name (only donor_name_hash); readable names go through the app's permissions: app/api/ledger.py.
Read-only: needs CONTRACT_ADDRESS and REFID_SECRET (chain/.env), never LISTENER_KEY.
Allowed browser origins for the dashboard: VERIFY_CORS_ORIGINS (comma separated), default none.
"""
from __future__ import annotations

import datetime
import functools
import json
import os

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from app import models

from . import chain, merkle
from . import db as ledger_db

NOTE = "A match shows this record existed unchanged at the block time. It does not prove the record is true."

app = FastAPI(title="Transparency verify")
_origins = [o.strip() for o in os.environ.get("VERIFY_CORS_ORIGINS", "").split(",") if o.strip()]
if _origins:
    app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_methods=["GET", "POST"], allow_headers=["*"])


class VerifyIn(BaseModel):
    record: dict
    salt: str

    @field_validator("record")
    @classmethod
    def _has_id(cls, v: dict) -> dict:
        if not isinstance(v.get("id"), str) or not v["id"].strip():
            raise ValueError("record.id (the source transaction id) is required")
        return v

    @field_validator("salt")
    @classmethod
    def _hex(cls, v: str) -> str:
        try:
            b = bytes.fromhex(v.removeprefix("0x"))
        except ValueError:
            raise ValueError("salt must be hex") from None
        if not b:
            raise ValueError("salt is empty")
        return v


@functools.lru_cache(maxsize=1)
def _live() -> tuple[chain.LedgerClient, bytes]:
    env = chain.load_env()
    secret = env.get("REFID_SECRET", "").encode("utf-8")
    if not secret:
        raise RuntimeError("REFID_SECRET missing in chain/.env")
    client, _, _ = chain.from_env(env, write=False)
    return client, secret


def get_ledger() -> tuple[chain.LedgerClient, bytes]:
    """Overridden in tests with a fake contract."""
    return _live()


def _iso(ts: int | None) -> str | None:
    return None if not ts else datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).isoformat()


@app.post("/verify")
def verify(body: VerifyIn, ledger: tuple = Depends(get_ledger)) -> dict:
    client, secret = ledger
    ref = chain.ref_id(secret, body.record["id"])
    leaf = merkle.leaf_hash(body.record, bytes.fromhex(body.salt.removeprefix("0x")))
    try:
        entry = client.entry(ref)
    except Exception as exc:  # RPC down, timeout
        raise HTTPException(503, f"chain unreachable: {type(exc).__name__}") from None
    match = entry is not None and entry["leaf"] == leaf
    return {
        "match": match,
        "found": entry is not None,   # found but no match = record or salt was changed
        "block_time": _iso(entry["recorded_at"]) if match else None,
        "block_timestamp": entry["recorded_at"] if match else None,
        "leaf": "0x" + leaf.hex(),
        "ref_id": "0x" + ref.hex(),
        "note": NOTE,
    }


BASESCAN_TX = "https://sepolia.basescan.org/tx/"


def get_sessions():
    """Overridden in tests."""
    return ledger_db.sessions()


@app.get("/public/records")
def public_records(limit: int = Query(default=50, ge=1, le=500), offset: int = Query(default=0, ge=0),
                   include_test: bool = False, sessions=Depends(get_sessions)) -> dict:
    """Public list for the dashboard (option A, team 2026-11-19): each record exactly as hashed, with its salt,
    so anyone can recompute the leaf (POST /verify, or by hand) and compare it with the chain.
    Never returns readable donor names, name salts or the original bank message. Newest first.
    TEST- records are hidden unless include_test=true."""
    with sessions() as db:
        q = db.query(models.LedgerRecord).filter(models.LedgerRecord.seq.isnot(None))
        if not include_test:
            q = q.filter(~models.LedgerRecord.source_tx_id.startswith("TEST-"))
        rows = q.order_by(models.LedgerRecord.seq.desc()).offset(offset).limit(limit).all()
    out = []
    for r in rows:
        rec = json.loads(r.record_json)
        if "donor_name" in rec:      # old shape with a readable name inside: never public
            continue
        out.append({"seq": r.seq, "record": rec, "salt": r.salt, "leaf": r.leaf, "chain_tx": r.chain_tx,
                    "chain_link": BASESCAN_TX + r.chain_tx if r.chain_tx else None,
                    "stamped_at": r.stamped_at.isoformat() if r.stamped_at else None,
                    "stamp_late": r.stamp_late, "anchor_day": r.anchor_day})
    return {"records": out, "note": NOTE}


@app.get("/health")
def health() -> dict:
    return {"ok": True}
