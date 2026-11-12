"""Phieu de nghi sua so lieu (correction ticket).

finance/volunteer de nghi (chi voi bang ho doc duoc) -> admin duyet -> dev ap dung. Moi buoc ghi nhat ky.
Nguoi de nghi khong duoc duyet; nguoi duyet khong duoc ap dung (tach nhiem vu). AI chi soan phieu, khong duyet/ap dung.
Luu y: nguyen mau nay KHONG ghi vao Core DB; 'apply' ghi nhan dev da sua (kem gia tri truoc/sau) de doi chieu.
"""
import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import access, models
from ..auth import current_user
from ..db import get_db

router = APIRouter(prefix="/api")
TERMINAL = ("rejected", "applied", "cancelled")


class TicketIn(BaseModel):
    table_name: str = Field(min_length=1, max_length=64)
    record_id: str = Field(min_length=1, max_length=128)
    field_name: str = Field(min_length=1, max_length=64)
    current_value: str | None = Field(default=None, max_length=2000)
    proposed_value: str = Field(min_length=1, max_length=2000)
    reason: str = Field(min_length=3, max_length=2000)
    evidence: str | None = Field(default=None, max_length=2000)


class DecisionIn(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=2000)


class ApplyIn(BaseModel):
    applied_value: str | None = Field(default=None, max_length=2000)   # mac dinh = gia tri de nghi
    note: str | None = Field(default=None, max_length=2000)


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _view(t: models.CorrectionTicket) -> dict:
    iso = lambda d: d.isoformat() if d else None  # noqa: E731
    return {"id": t.id, "requester_id": t.requester_id, "table_name": t.table_name, "record_id": t.record_id,
            "field_name": t.field_name, "current_value": t.current_value, "proposed_value": t.proposed_value,
            "reason": t.reason, "evidence": t.evidence, "status": t.status, "created_at": iso(t.created_at),
            "decided_by": t.decided_by, "decided_at": iso(t.decided_at), "decision_note": t.decision_note,
            "applied_by": t.applied_by, "applied_at": iso(t.applied_at), "applied_value": t.applied_value,
            "apply_note": t.apply_note}


def _get(db: Session, ticket_id: int) -> models.CorrectionTicket:
    t = db.get(models.CorrectionTicket, ticket_id)
    if t is None:
        raise HTTPException(404, "no such ticket")
    return t


def _visible(user, t: models.CorrectionTicket) -> bool:
    return user.department in access.FULL_ACCESS or t.requester_id == user.id


def _log(db, user, action, t, **detail):
    access.audit(db, user, action, correlation_id=f"ticket:{t.id}",
                 detail={"ticket": t.id, "table": t.table_name, "record": t.record_id, "field": t.field_name, **detail})


@router.get("/me")
def me(user=Depends(current_user)):
    return {"id": user.id, "email": user.email, "name": user.name, "department": user.department}


@router.post("/tickets")
def create(body: TicketIn, user=Depends(current_user), db: Session = Depends(get_db)):
    if user.department not in access.LABELLABLE:
        raise HTTPException(403, "only finance and volunteer open tickets (dev and admin change data directly)")
    if body.table_name not in access.CORE_TABLES or access.CORE_TABLES[body.table_name][2] in ("system", "audit"):
        raise HTTPException(422, "unknown or non-correctable table")
    if not access.can_read_table(db, user, body.table_name):
        access.audit(db, user, "tool_denied", detail={"ticket_on": body.table_name})
        db.commit()
        raise HTTPException(403, "you can only open tickets on data you may read")
    t = models.CorrectionTicket(requester_id=user.id, status="open", **body.model_dump())
    db.add(t)
    db.flush()
    _log(db, user, "ticket_created", t, proposed=t.proposed_value)
    db.commit()
    return _view(t)


@router.get("/tickets")
def list_tickets(status: str | None = None, user=Depends(current_user), db: Session = Depends(get_db)):
    q = db.query(models.CorrectionTicket).order_by(models.CorrectionTicket.id.desc())
    if user.department not in access.FULL_ACCESS:
        q = q.filter(models.CorrectionTicket.requester_id == user.id)
    if status:
        q = q.filter(models.CorrectionTicket.status == status)
    return {"items": [_view(t) for t in q.limit(200)]}


@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
    t = _get(db, ticket_id)
    if not _visible(user, t):
        raise HTTPException(404, "no such ticket")          # khong lo su ton tai cua phieu nguoi khac
    return _view(t)


@router.post("/tickets/{ticket_id}/cancel")
def cancel(ticket_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
    t = _get(db, ticket_id)
    if t.requester_id != user.id:
        raise HTTPException(404, "no such ticket")
    if t.status != "open":
        raise HTTPException(409, f"ticket is {t.status}")
    t.status = "cancelled"
    _log(db, user, "ticket_cancelled", t)
    db.commit()
    return _view(t)


@router.post("/tickets/{ticket_id}/decision")
def decide(ticket_id: int, body: DecisionIn, user=Depends(current_user), db: Session = Depends(get_db)):
    if user.department != "admin":
        raise HTTPException(403, "only admin approves or rejects")
    t = _get(db, ticket_id)
    if t.requester_id == user.id:
        raise HTTPException(403, "you cannot decide your own ticket")
    if t.status != "open":
        raise HTTPException(409, f"ticket is {t.status}")
    if not body.approve and not (body.note or "").strip():
        raise HTTPException(422, "a rejection needs a note")
    t.status = "approved" if body.approve else "rejected"
    t.decided_by, t.decided_at, t.decision_note = user.id, _now(), body.note
    _log(db, user, "ticket_decided", t, decision=t.status, note=body.note)
    db.commit()
    return _view(t)


@router.post("/tickets/{ticket_id}/apply")
def apply(ticket_id: int, body: ApplyIn, user=Depends(current_user), db: Session = Depends(get_db)):
    if user.department != "dev":
        raise HTTPException(403, "only dev applies approved changes")
    t = _get(db, ticket_id)
    if t.status != "approved":
        raise HTTPException(409, f"ticket is {t.status}, not approved")
    if user.id in (t.requester_id, t.decided_by):
        raise HTTPException(403, "the person who requested or approved cannot apply")
    t.status = "applied"
    t.applied_by, t.applied_at = user.id, _now()
    t.applied_value = body.applied_value if body.applied_value is not None else t.proposed_value
    t.apply_note = body.note
    _log(db, user, "ticket_applied", t, before=t.current_value, after=t.applied_value, reason=t.reason)
    db.commit()
    return _view(t)
