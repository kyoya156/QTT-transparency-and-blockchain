"""Quyen truy cap theo phong ban.

Quy tac: admin gan nhan (label) cho du lieu va cong cu. Phong ban khac chi dung duoc thu co nhan cua minh.
Khong co nhan = chi admin. Admin luon duoc dung moi thu (nen khong can ghi 'admin' vao nhan).
"""
import datetime
import hashlib
import json
import secrets

from sqlalchemy import update
from sqlalchemy.orm import Session

from . import models

DEPARTMENTS = ("admin", "finance", "volunteers")
LABELLABLE = tuple(d for d in DEPARTMENTS if d != "admin")

# Cong cu AI co the goi. Moi cong cu la mot muc admin gan nhan; chua gan = chi admin.
TOOLS = {
    "search_knowledge": "Search the knowledge base (website pages and Facebook posts)",
    "messenger_evidence": "Find the Messenger message that confirms a sponsorship (planned)",
    "payment_lookup": "Look up the payment status of a transfer in the Core database (planned)",
}


def clean_departments(values) -> list[str]:
    """Chuan hoa danh sach phong ban: bo trung, bo 'admin' (luon co quyen), tu choi ten la."""
    out = []
    for v in values or []:
        v = str(v).strip().lower()
        if v == "admin":
            continue
        if v not in LABELLABLE:
            raise ValueError(f"unknown department: {v!r}")
        if v not in out:
            out.append(v)
    return sorted(out)


# ---- nhan cho du lieu --------------------------------------------------------------------------
def source_key(source_type: str, source_id: str | None) -> str:
    return f"source:{source_type}:{source_id if source_id else '*'}"


def tool_key(tool: str) -> str:
    return f"tool:{tool}"


def load_source_rules(db: Session) -> dict[str, list[str]]:
    rows = db.query(models.AccessRule).filter(models.AccessRule.key.like("source:%")).all()
    return {r.key: list(r.departments or []) for r in rows}


def effective_labels(rules: dict[str, list[str]], source_type: str, source_id: str) -> list[str]:
    """Nhan cua mot nguon: quy tac rieng cho nguon > quy tac theo loai > khong co (chi admin)."""
    for key in (source_key(source_type, source_id), source_key(source_type, None)):
        if key in rules:
            return list(rules[key])
    return []


def recompute_labels(db: Session, source_type: str | None = None, source_id: str | None = None) -> int:
    """Tinh lai chunks.labels tu cac quy tac. Tra ve so chunk duoc cap nhat. Khong commit."""
    rules = load_source_rules(db)
    q = db.query(models.Chunk.source_type, models.Chunk.source_id).distinct()
    if source_type:
        q = q.filter(models.Chunk.source_type == source_type)
    if source_id:
        q = q.filter(models.Chunk.source_id == source_id)
    total = 0
    for st, sid in q.all():
        res = db.execute(update(models.Chunk)
                         .where(models.Chunk.source_type == st, models.Chunk.source_id == sid)
                         .values(labels=effective_labels(rules, st, sid)))
        total += res.rowcount or 0
    return total


def set_source_rule(db: Session, user, source_type: str, source_id: str | None, departments) -> list[str]:
    deps = clean_departments(departments)
    key = source_key(source_type, source_id)
    rule = db.query(models.AccessRule).filter_by(key=key).one_or_none()
    if rule is None:
        db.add(models.AccessRule(key=key, departments=deps, updated_by=user.id))
    else:
        rule.departments, rule.updated_by = deps, user.id
        rule.updated_at = datetime.datetime.now(datetime.timezone.utc)
    db.flush()
    recompute_labels(db, source_type)      # quy tac theo loai anh huong ca cac nguon khong co quy tac rieng
    return deps


def clear_source_rule(db: Session, source_type: str, source_id: str | None) -> bool:
    n = db.query(models.AccessRule).filter_by(key=source_key(source_type, source_id)).delete()
    db.flush()
    recompute_labels(db, source_type)
    return bool(n)


# ---- cong cu -----------------------------------------------------------------------------------
def tool_departments(db: Session, tool: str) -> list[str]:
    r = db.query(models.AccessRule).filter_by(key=tool_key(tool)).one_or_none()
    return list(r.departments or []) if r else []


def can_use_tool(db: Session, user, tool: str) -> bool:
    if tool not in TOOLS:
        return False
    return user.department == "admin" or user.department in tool_departments(db, tool)


def set_tool_rule(db: Session, user, tool: str, departments) -> list[str]:
    if tool not in TOOLS:
        raise ValueError(f"unknown tool: {tool!r}")
    deps = clean_departments(departments)
    r = db.query(models.AccessRule).filter_by(key=tool_key(tool)).one_or_none()
    if r is None:
        db.add(models.AccessRule(key=tool_key(tool), departments=deps, updated_by=user.id))
    else:
        r.departments, r.updated_by = deps, user.id
        r.updated_at = datetime.datetime.now(datetime.timezone.utc)
    db.flush()
    return deps


# ---- nguoi dung va token -----------------------------------------------------------------------
def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_user(db: Session, email: str, name: str, department: str) -> tuple[models.User, str]:
    """Tra ve (user, token). Token chi hien mot lan; DB chi giu ban bam."""
    if department not in DEPARTMENTS:
        raise ValueError(f"unknown department: {department!r}")
    token = secrets.token_urlsafe(32)
    u = models.User(email=email.strip().lower(), name=name, department=department,
                    token_hash=hash_token(token), is_active=True)
    db.add(u)
    db.flush()
    return u, token


def find_user_by_token(db: Session, token: str):
    u = db.query(models.User).filter_by(token_hash=hash_token(token)).one_or_none()
    return u if u is not None and u.is_active else None


def audit(db: Session, user, action: str, query: str | None = None, chunk_ids=None, detail: dict | None = None):
    db.add(models.AuditLog(user_id=getattr(user, "id", None), department=getattr(user, "department", None),
                           action=action, query=query,
                           chunk_ids=json.dumps(list(chunk_ids)) if chunk_ids is not None else None,
                           detail=json.dumps(detail, ensure_ascii=False) if detail else None))
