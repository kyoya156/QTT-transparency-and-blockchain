"""Webhook listener: SePay message -> record + salt -> database -> stamp on chain.

    uvicorn transparency.listener:app --port 8200
    POST /webhook/sepay

Flow per new transaction:
  1. check SePay's signature, parse;
  2. build the record (TEMPORARY rules below), new random salt, leaf computed in memory;
  3. save record + salt in ledger_records and commit (a salt must never be lost: without it the
     record can never be checked again);
  4. answer SePay {"success": true} (it allows 30 s), then stamp leaf on chain in the background
     from the in-memory values, never re-read from the database; save the tx hash.
A repeat of the same SePay id is acknowledged; if it was never stamped, stamping is retried.
Rows still unstamped (chain was down) are retried at startup.

TEMPORARY record rules until the team decides (meeting 2026-11-19), see reminder.md:
  - record id = LISTENER_ID_PREFIX + "SEPAY-<id>", default prefix "TEST-" so the dashboard skips them;
  - donor_id / recipient_id = the code SePay extracted from the memo, else "NO-CODE";
  - donor_name = Anonymous; recipient_type = unassigned; memo text is not put in the record.
Needs in chain/.env: SEPAY_WEBHOOK_SECRET (or SEPAY_API_KEY), REFID_SECRET, LISTENER_KEY, CONTRACT_ADDRESS.
Database: LISTENER_DB_URL, else the app's DATABASE_URL, else sqlite file transparency_data/ledger.db.
"""
from __future__ import annotations

import functools
import logging
import os
import pathlib
import secrets

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.api.ledger import store

from . import chain, merkle, records, sepay

log = logging.getLogger("listener")
NO_CODE = "NO-CODE"
SALT_BYTES = 16

app = FastAPI(title="Transparency listener")


def _env(name: str) -> str:
    return os.environ.get(name) or chain.load_env().get(name, "")


def build_record(tx: dict, prefix: str | None = None) -> dict:
    """TEMPORARY mapping from a SePay transaction to our record shape (see module docstring)."""
    if prefix is None:
        prefix = os.environ.get("LISTENER_ID_PREFIX", chain.load_env().get("LISTENER_ID_PREFIX", "TEST-"))
    rid = prefix + tx["source_tx_id"]
    party = tx.get("code") or NO_CODE
    if tx["direction"] == "in":
        return records.income(rid, tx["amount"], party, tx["time"], currency=tx["currency"])
    return records.expense(rid, tx["amount"], party, tx["time"], currency=tx["currency"])


@functools.lru_cache(maxsize=1)
def _sessions() -> sessionmaker:
    url = os.environ.get("LISTENER_DB_URL") or os.environ.get("DATABASE_URL") or ""
    if not url:
        pathlib.Path("transparency_data").mkdir(exist_ok=True)
        url = "sqlite:///transparency_data/ledger.db"
    eng = create_engine(url, pool_pre_ping=True)
    models.LedgerRecord.__table__.create(eng, checkfirst=True)
    return sessionmaker(bind=eng, expire_on_commit=False)


@functools.lru_cache(maxsize=1)
def _live() -> tuple[chain.LedgerClient, bytes]:
    secret = _env("REFID_SECRET").encode("utf-8")
    if not secret:
        raise RuntimeError("REFID_SECRET missing in chain/.env")
    client, _, _ = chain.from_env(write=True)
    return client, secret


# Overridden in tests.
def get_sessions() -> sessionmaker:
    return _sessions()


def get_ledger() -> tuple[chain.LedgerClient, bytes]:
    return _live()


def get_auth() -> tuple[str, str]:
    return _env("SEPAY_WEBHOOK_SECRET"), _env("SEPAY_API_KEY")


def stamp(sessions: sessionmaker, client: chain.LedgerClient, source_tx_id: str, ref: bytes, leaf: bytes) -> None:
    try:
        res = client.record(ref, leaf)
    except chain.ConflictError:
        log.error("CONFLICT %s: refId on chain holds a different leaf. Investigate, do not overwrite.", source_tx_id)
        return
    except Exception:
        log.exception("stamp failed for %s; row stays unstamped and is retried later", source_tx_id)
        return
    log.info("stamped %s: %s %s", source_tx_id, res.status, res.tx_hash or "")
    if res.tx_hash:
        with sessions() as db:
            row = db.query(models.LedgerRecord).filter_by(source_tx_id=source_tx_id).one()
            row.chain_tx = res.tx_hash
            db.commit()


def _hex(s: str) -> bytes:
    return bytes.fromhex(s.removeprefix("0x"))


@app.post("/webhook/sepay")
async def webhook(request: Request, tasks: BackgroundTasks) -> JSONResponse:
    raw = await request.body()
    try:
        sepay.authenticate(request.headers, raw, *get_auth())
    except sepay.AuthError as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=401)
    try:
        rec = build_record(sepay.parse(raw))
    except (ValueError, KeyError) as e:
        return JSONResponse({"success": False, "error": f"bad payload: {e}"}, status_code=400)

    sessions = get_sessions()
    client, secret = get_ledger()
    with sessions() as db:
        row = db.query(models.LedgerRecord).filter_by(source_tx_id=rec["id"]).one_or_none()
        if row is None:
            salt = secrets.token_bytes(SALT_BYTES)
            ref, leaf = chain.ref_id(secret, rec["id"]), merkle.leaf_hash(rec, salt)
            store(db, rec, salt, ref)
            db.commit()
        elif row.chain_tx is None:
            # Retry of an unstamped row: the only case that uses stored values.
            ref, leaf = _hex(row.ref_id), _hex(row.leaf)
        else:
            return JSONResponse(sepay.OK)
    tasks.add_task(stamp, sessions, client, rec["id"], ref, leaf)
    return JSONResponse(sepay.OK)


def stamp_pending() -> int:
    """Stamp every row that has no chain tx yet (e.g. the chain was unreachable). Returns how many were tried."""
    sessions = get_sessions()
    client, _ = get_ledger()
    with sessions() as db:
        pending = [(r.source_tx_id, _hex(r.ref_id), _hex(r.leaf))
                   for r in db.query(models.LedgerRecord).filter(models.LedgerRecord.chain_tx.is_(None),
                                                                 models.LedgerRecord.anchor_day.is_(None))]
    for sid, ref, leaf in pending:
        stamp(sessions, client, sid, ref, leaf)
    return len(pending)


@app.on_event("startup")
def _retry_pending() -> None:
    logging.basicConfig(level=logging.INFO)
    try:
        n = stamp_pending()
        if n:
            log.info("retried %d unstamped rows", n)
    except Exception:
        log.exception("startup retry skipped")
