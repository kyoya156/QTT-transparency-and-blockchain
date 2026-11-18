"""Verify endpoint: record + salt -> rebuild leaf -> contract verify -> block time.

    uvicorn transparency.api:app --port 8100
    POST /verify  {"record": {...exact stored record...}, "salt": "<hex>"}

A match proves the record existed unchanged at the block time. It does not prove the record is true.
Read-only: needs CONTRACT_ADDRESS and REFID_SECRET (chain/.env), never LISTENER_KEY.
Allowed browser origins for the dashboard: VERIFY_CORS_ORIGINS (comma separated), default none.
"""
from __future__ import annotations

import datetime
import functools
import os

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from . import chain, merkle

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
    on_chain = None if entry is None else {
        "direction": entry["direction"],
        "amount": entry["amount"],
        "bank_time": _iso(entry["tx_time"]),
    }
    return {
        "match": match,
        "found": entry is not None,   # found but no match = record or salt was changed
        "block_time": _iso(entry["recorded_at"]) if match else None,
        "block_timestamp": entry["recorded_at"] if match else None,
        "on_chain": on_chain,
        "leaf": "0x" + leaf.hex(),
        "ref_id": "0x" + ref.hex(),
        "note": NOTE,
    }


@app.get("/health")
def health() -> dict:
    return {"ok": True}
