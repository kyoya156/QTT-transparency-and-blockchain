"""Webhook listener: SePay message -> record + salt -> database -> stamp on chain.

    uvicorn transparency.listener:app --port 8200
    POST /webhook/sepay

Flow per new transaction (measures 1-5, team 2026-11-19; detail in docs/MEASURES.md):
  1. check SePay's signature, parse; refuse a bank time in the future;
  2. under one lock: next seq, prev = leaf of the last record, running balance (measures 1-2),
     source_hash = sha256 of the signed message (measure 3); build the record, new salt, leaf in memory;
  3. save record + salt + original message + its signature headers in ledger_records and commit
     (a salt must never be lost: without it the record can never be checked again);
  4. answer SePay {"success": true} (it allows 30 s), then stamp the in-memory leaf in the background,
     never re-read from the database (measure 5); save tx hash + stamp time; flag and audit if the
     stamp is more than LATE_AFTER after bank time.
Unstamped rows are only stamped after a tamper check: on a SePay resend, the record is rebuilt from
the resent message; at startup, from the stored original (its HMAC re-checked). Mismatch = no stamp + alarm.

TEMPORARY record rules until the memo-code decision, see reminder.md:
  - record id = LISTENER_ID_PREFIX + "SEPAY-<id>", default prefix "TEST-" so the dashboard skips them;
  - donor_id / recipient_id = the code SePay extracted from the memo, else "NO-CODE";
  - donor_name = Anonymous (only its salted hash is in the record); recipient_type = unassigned; memo text is not put in the record.
Needs in chain/.env: SEPAY_WEBHOOK_SECRET (or SEPAY_API_KEY), REFID_SECRET, LISTENER_KEY, CONTRACT_ADDRESS,
OPENING_BALANCE (integer VND before record 1; 0 for tests).
Database: LISTENER_DB_URL, else the app's DATABASE_URL, else sqlite file transparency_data/ledger.db.
"""
from __future__ import annotations

import datetime
import functools
import hashlib
import json
import logging
import os
import secrets
import threading

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app import models
from app.api.ledger import store

from . import chain, merkle, records, sepay
from . import db as ledger_db

log = logging.getLogger("listener")
NO_CODE = "NO-CODE"
SALT_BYTES = 16
LATE_AFTER = datetime.timedelta(minutes=10)   # bank time is minute precision
_SEQ_LOCK = threading.Lock()                  # one numbering step at a time; the unique seq column backs it up

app = FastAPI(title="Transparency listener")


def _env(name: str) -> str:
    return os.environ.get(name) or chain.load_env().get(name, "")


def opening_balance() -> int:
    return int(_env("OPENING_BALANCE") or 0)


def build_record(tx: dict, prefix: str | None = None) -> dict:
    """TEMPORARY mapping from a SePay transaction to our record shape (see module docstring). Not linked yet."""
    if prefix is None:
        prefix = os.environ.get("LISTENER_ID_PREFIX", chain.load_env().get("LISTENER_ID_PREFIX", "TEST-"))
    rid = prefix + tx["source_tx_id"]
    party = tx.get("code") or NO_CODE
    if tx["direction"] == "in":
        return records.income(rid, tx["amount"], party, tx["time"], currency=tx["currency"])
    return records.expense(rid, tx["amount"], party, tx["time"], currency=tx["currency"])


def source_hash(raw: bytes) -> str:
    return "0x" + hashlib.sha256(raw).hexdigest()


def next_link(db: Session) -> tuple[int, str, int]:
    """(seq, prev, balance_before) for the next record, from the last stored record."""
    last = (db.query(models.LedgerRecord).filter(models.LedgerRecord.seq.isnot(None))
            .order_by(models.LedgerRecord.seq.desc()).first())
    if last is None:
        return 1, records.GENESIS, opening_balance()
    return last.seq + 1, last.leaf, json.loads(last.record_json)["balance"]


def rebuild(row: models.LedgerRecord, raw: bytes) -> bool:
    """Measure 5 tamper check: rebuild the stored record from a signed SePay message (plus its stored
    seq/prev/balance and salt). True only if it gives exactly the stored leaf."""
    stored = json.loads(row.record_json)
    tx = sepay.parse(raw)
    if not stored["id"].endswith(tx["source_tx_id"]):
        return False
    rec = build_record(tx, prefix=stored["id"][: -len(tx["source_tx_id"])])
    rec, _ = records.hide_name(rec, bytes.fromhex(row.name_salt) if row.name_salt else None)
    rec = records.link(rec, stored["seq"], stored["prev"], records.balance_before(stored), source_hash(raw))
    return "0x" + merkle.leaf_hash(rec, bytes.fromhex(row.salt)).hex() == row.leaf


def _alarm(sessions: sessionmaker, action: str, detail: dict) -> None:
    log.error("%s %s", action, detail)
    with sessions() as db:
        db.add(models.AuditLog(action=action, detail=json.dumps(detail, ensure_ascii=False)))
        db.commit()


@functools.lru_cache(maxsize=1)
def _live() -> tuple[chain.LedgerClient, bytes]:
    secret = _env("REFID_SECRET").encode("utf-8")
    if not secret:
        raise RuntimeError("REFID_SECRET missing in chain/.env")
    client, _, _ = chain.from_env(write=True)
    return client, secret


# Overridden in tests.
def get_sessions() -> sessionmaker:
    return ledger_db.sessions()


def get_ledger() -> tuple[chain.LedgerClient, bytes]:
    return _live()


def get_auth() -> tuple[str, str]:
    return _env("SEPAY_WEBHOOK_SECRET"), _env("SEPAY_API_KEY")


def stamp(sessions: sessionmaker, client: chain.LedgerClient, source_tx_id: str, ref: bytes, leaf: bytes,
          bank_time: str | None = None) -> None:
    try:
        res = client.record(ref, leaf)
    except chain.ConflictError:
        _alarm(sessions, "ledger_conflict", {"id": source_tx_id, "why": "refId on chain holds a different leaf"})
        return
    except Exception:
        log.exception("stamp failed for %s; row stays unstamped and is retried later", source_tx_id)
        return
    log.info("stamped %s: %s %s", source_tx_id, res.status, res.tx_hash or "")
    if not res.tx_hash:
        return
    now = datetime.datetime.now(datetime.timezone.utc)
    late = bank_time is not None and now - datetime.datetime.fromisoformat(bank_time) > LATE_AFTER
    with sessions() as db:
        row = db.query(models.LedgerRecord).filter_by(source_tx_id=source_tx_id).one()
        row.chain_tx, row.stamped_at, row.stamp_late = res.tx_hash, now, late
        db.commit()
    if late:
        _alarm(sessions, "ledger_late_stamp", {"id": source_tx_id, "bank_time": bank_time,
                                               "stamped_at": now.isoformat(), "tx": res.tx_hash,
                                               "todo": "check against the bank statement"})


def _hex(s: str) -> bytes:
    return bytes.fromhex(s.removeprefix("0x"))


def _auth_headers(headers) -> dict:
    return {k: headers[k] for k in ("x-sepay-timestamp", "x-sepay-signature") if headers.get(k)}


def _insert(sessions: sessionmaker, tx: dict, raw: bytes, auth: dict) -> tuple[dict, bytes, bytes] | None:
    """Number, link, save and commit a new record. Returns (record, ref, leaf), or None if it already exists."""
    _, secret = get_ledger()
    rid = build_record(tx)["id"]
    for _attempt in range(3):
        with _SEQ_LOCK, sessions() as db:
            if db.query(models.LedgerRecord).filter_by(source_tx_id=rid).count():
                return None
            seq, prev, before = next_link(db)
            name_salt = secrets.token_bytes(records.NAME_SALT_BYTES) if tx["direction"] == "in" else None
            rec, name = records.hide_name(build_record(tx), name_salt)
            rec = records.link(rec, seq, prev, before, source_hash(raw))
            salt = secrets.token_bytes(SALT_BYTES)
            ref, leaf = chain.ref_id(secret, rec["id"]), merkle.leaf_hash(rec, salt)
            try:
                store(db, rec, salt, ref, source_raw=raw, source_auth=auth, donor_name=name, name_salt=name_salt)
                db.commit()
                return rec, ref, leaf
            except IntegrityError:
                db.rollback()       # another worker took this seq (or this id); look again
    raise RuntimeError("could not number the record after 3 attempts")


@app.post("/webhook/sepay")
async def webhook(request: Request, tasks: BackgroundTasks) -> JSONResponse:
    raw = await request.body()
    try:
        sepay.authenticate(request.headers, raw, *get_auth())
    except sepay.AuthError as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=401)
    try:
        tx = sepay.parse(raw)
        records.check_not_future(build_record(tx))
    except (ValueError, KeyError) as e:
        return JSONResponse({"success": False, "error": f"bad payload: {e}"}, status_code=400)

    sessions = get_sessions()
    client, _ = get_ledger()
    new = _insert(sessions, tx, raw, _auth_headers(request.headers))
    if new is not None:
        rec, ref, leaf = new
        tasks.add_task(stamp, sessions, client, rec["id"], ref, leaf, rec["time"])
        return JSONResponse(sepay.OK)

    with sessions() as db:
        row = db.query(models.LedgerRecord).filter_by(source_tx_id=build_record(tx)["id"]).one()
    if row.chain_tx is None and row.anchor_day is None:
        # Resend of an unstamped record: stamp only if the resent signed message rebuilds the stored leaf.
        if rebuild(row, raw):
            tasks.add_task(stamp, sessions, client, row.source_tx_id, _hex(row.ref_id), _hex(row.leaf),
                           json.loads(row.record_json)["time"])
        else:
            _alarm(sessions, "ledger_tamper", {"id": row.source_tx_id,
                                               "why": "resent message does not rebuild the stored record; not stamped"})
    return JSONResponse(sepay.OK)


def _stored_original_ok(row: models.LedgerRecord, secret: str) -> bool:
    """The stored original still carries SePay's signature (HMAC mode) and rebuilds the stored leaf."""
    if row.source_raw is None:
        return False
    raw = row.source_raw.encode("utf-8")
    if secret:
        auth = json.loads(row.source_auth or "{}")
        ts = auth.get("x-sepay-timestamp") or "0"
        try:
            sepay.check_hmac(secret, ts, auth.get("x-sepay-signature"), raw, now=float(ts))
        except (sepay.AuthError, ValueError):
            return False
    return rebuild(row, raw)


def stamp_pending() -> int:
    """Stamp rows that have no chain tx yet (e.g. the chain was unreachable), each only after rebuilding it
    from its stored signed original. Returns how many were sent to the chain."""
    sessions = get_sessions()
    client, _ = get_ledger()
    secret, _ = get_auth()
    with sessions() as db:
        pending = db.query(models.LedgerRecord).filter(models.LedgerRecord.chain_tx.is_(None),
                                                       models.LedgerRecord.anchor_day.is_(None)).all()
    n = 0
    for r in pending:
        if not _stored_original_ok(r, secret):
            _alarm(sessions, "ledger_tamper", {"id": r.source_tx_id, "why": "stored original missing, unsigned "
                                               "or does not rebuild the stored record; not stamped"})
            continue
        stamp(sessions, client, r.source_tx_id, _hex(r.ref_id), _hex(r.leaf), json.loads(r.record_json)["time"])
        n += 1
    return n


@app.on_event("startup")
def _retry_pending() -> None:
    logging.basicConfig(level=logging.INFO)
    try:
        n = stamp_pending()
        if n:
            log.info("retried %d unstamped rows", n)
    except Exception:
        log.exception("startup retry skipped")
