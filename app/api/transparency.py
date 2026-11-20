"""HTTP wrapper around the local transparency prototype.

The CLI in `scripts/transparency.py` remains the source of truth. This module
only exposes the same public/private files to the page, with role checks:

* finance, admin, dev may see records and request a proof;
* volunteer may see the public batch list (roots and counts), never records;
* every write is audited.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import access
from ..auth import current_user
from ..config import settings
from ..db import get_db
from transparency import batch, ledger
from transparency.anchor import LocalAnchor

router = APIRouter(prefix="/api/transparency")
FINANCE_ROLES = ("admin", "dev", "finance")
READ_ROLES = ("admin", "dev", "finance", "volunteer")


class DayIn(BaseModel):
    day: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class ProofIn(DayIn):
    record_id: str = Field(min_length=1, max_length=128)


def _dir() -> Path:
    return Path(settings.transparency_dir)


def _anchor() -> LocalAnchor:
    return LocalAnchor(_dir() / "anchor.jsonl")


def _role(user, allowed):
    if user.department not in allowed:
        raise HTTPException(403, "your department may not use this data")
    return user


def _check_day(day: str) -> str:
    try:
        datetime.date.fromisoformat(day)
    except ValueError as exc:
        raise HTTPException(422, "invalid day") from exc
    return day


def _public(day: str) -> dict:
    path = _dir() / f"{_check_day(day)}.public.json"
    if not path.exists():
        raise HTTPException(404, "batch not found")
    return json.loads(path.read_text(encoding="utf-8"))


def _private(day: str) -> dict:
    path = _dir() / f"{_check_day(day)}.private.json"
    if not path.exists():
        raise HTTPException(404, "private batch not found")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/status")
def status(user=Depends(current_user)):
    _role(user, READ_ROLES)
    anchor = _anchor()
    blocks = anchor.blocks()
    batches = []
    for path in (sorted(_dir().glob("*.public.json")) if _dir().exists() else []):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            batches.append({"day": data.get("day"), "root": data.get("root"),
                            "count": data.get("count"), "anchor": data.get("anchor")})
        except (OSError, ValueError):
            continue
    return {"chain_ok": anchor.check_chain(), "blocks": blocks, "batches": batches,
            "data_dir": str(_dir()), "synthetic_note": "Bản demo dùng ledger tổng hợp, chưa phải sao kê ngân hàng thật."}


@router.get("/batches")
def batches(user=Depends(current_user)):
    _role(user, READ_ROLES)
    out = []
    for path in (sorted(_dir().glob("*.public.json")) if _dir().exists() else []):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            out.append({"day": data.get("day"), "root": data.get("root"),
                        "count": data.get("count"), "anchor": data.get("anchor")})
        except (OSError, ValueError):
            continue
    return {"items": out}


@router.get("/batches/{day}")
def one_batch(day: str, user=Depends(current_user)):
    _role(user, READ_ROLES)
    return _public(day)


@router.get("/records/{day}")
def records(day: str, user=Depends(current_user), db: Session = Depends(get_db)):
    _role(user, FINANCE_ROLES)
    data = _private(day)
    access.audit(db, user, "transparency_records", detail={"day": day, "count": len(data.get("records", []))})
    db.commit()
    return {"day": day, "records": data.get("records", [])}


@router.post("/batch")
def make_batch(body: DayIn, user=Depends(current_user), db: Session = Depends(get_db)):
    _role(user, ("admin", "dev"))
    try:
        day = datetime.date.fromisoformat(body.day)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    anchor = _anchor()
    if anchor.get(body.day) is not None:
        raise HTTPException(409, "day is already anchored")
    try:
        block = batch.build(body.day, ledger.synthetic_day(day), _dir(), anchor)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    access.audit(db, user, "transparency_batch", detail={"day": body.day, "count": block.get("count"),
                                                         "source": "synthetic"})
    db.commit()
    return {"ok": True, "block": block, "synthetic": True}


@router.post("/proof")
def make_proof(body: ProofIn, user=Depends(current_user), db: Session = Depends(get_db)):
    _role(user, FINANCE_ROLES)
    try:
        proof = batch.prove(body.day, body.record_id, _dir())
    except (StopIteration, FileNotFoundError) as exc:
        raise HTTPException(404, "record or batch not found") from exc
    access.audit(db, user, "transparency_proof", detail={"day": body.day, "record_id": body.record_id})
    db.commit()
    return proof


@router.post("/verify")
def verify(body: dict, user=Depends(current_user), db: Session = Depends(get_db)):
    _role(user, FINANCE_ROLES)
    try:
        ok, message = batch.verify(body, _anchor())
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(422, f"invalid proof: {exc}") from exc
    access.audit(db, user, "transparency_verify", detail={"day": body.get("day"), "ok": ok})
    db.commit()
    return {"ok": ok, "message": message}
