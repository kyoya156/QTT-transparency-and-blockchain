"""Quyen truy cap theo phong ban.

Vai tro:
- admin: xem het, gan nhan du lieu/bang/cong cu, sua quyen (qua dashboard admin).
- dev: truy van va sua noi dung co so du lieu (xem het; ghi qua quyen GRANT cua Core DB).
- finance: chi doc thong tin tai chinh (giao dich, thong tin nha tai tro de doi chieu...).
- volunteer: chi doc thong tin muc thap, can duyet (phan cong tai tro, thong tin hoc sinh co ban).
Quy tac: admin gan nhan cho du lieu/bang/cong cu; finance va volunteer chi dung duoc thu co nhan cua minh.
Khong co nhan = chi admin va dev. admin/dev khong can ghi vao nhan.
"""
import datetime
import hashlib
import json
import secrets

from sqlalchemy import update
from sqlalchemy.orm import Session

from . import models

DEPARTMENTS = ("admin", "dev", "finance", "volunteer")
FULL_ACCESS = ("admin", "dev")                       # doc moi thu, khong can nhan
LABELLABLE = tuple(d for d in DEPARTMENTS if d not in FULL_ACCESS)

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
        if v in FULL_ACCESS:
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
    return user.department in FULL_ACCESS or user.department in tool_departments(db, tool)


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


# ---- bang cua Core DB ---------------------------------------------------------------------------
# Ten bang lay tu ERD (WIP) trong gradproj.drawio; Topic 4 co the doi ten -> sua o day.
# kind: data = gan nhan duoc | financial = khong xoa cung | system = chi admin/dev, khong gan nhan | audit = chi them
CORE_TABLES = {
    "province": ("Provinces", ["finance", "volunteer"], "data"),
    "commune": ("Communes (representative contact)", ["finance", "volunteer"], "data"),
    "village": ("Villages (chief contact)", ["finance", "volunteer"], "data"),
    "school": ("Schools (principal contact, group link)", ["finance", "volunteer"], "data"),
    "school_site": ("School sites", ["finance", "volunteer"], "data"),
    "school_year": ("School years", ["finance", "volunteer"], "data"),
    "class": ("Classes (homeroom teacher)", ["finance", "volunteer"], "data"),
    "student": ("Students: name, gender, birth date, ethnicity", ["volunteer"], "data"),
    "enrollment": ("Student enrolment in a class", ["volunteer"], "data"),
    "measurement": ("Student height and weight", [], "data"),
    "family_info": ("Parents, family circumstances, special conditions", [], "data"),
    "student_image": ("Student photos", [], "data"),
    "image_result": ("Processed photos and their review", [], "data"),
    "publication": ("Photo publication and permission", [], "data"),
    "school_case": ("School support cases and authorisation", [], "data"),
    "sponsor": ("Sponsors: ACN code, name, phone, email", ["finance"], "data"),
    "sponsorship_assignment": ("Sponsor, NE code and meal plan assignments", ["finance", "volunteer"], "data"),
    "ne_code": ("Student sponsorship codes (NE)", ["finance", "volunteer"], "data"),
    "meal_plan": ("Meal plans and rates", ["finance", "volunteer"], "data"),
    "school_meal_plan": ("Meal plans offered by each school", ["finance", "volunteer"], "data"),
    "bank_transaction": ("Incoming transfers", ["finance"], "financial"),
    "transaction_allocation": ("Transfer allocated to assignments", ["finance"], "financial"),
    "disbursement": ("Payments to schools", ["finance"], "financial"),
    "app_user": ("Accounts", [], "system"),
    "role": ("Roles", [], "system"),
    "user_role": ("User-role links", [], "system"),
    "import_batch": ("Import batches", [], "system"),
    "import_issue": ("Import data issues", [], "system"),
    "audit_log": ("Audit trail (insert only)", [], "audit"),
}


def table_key(table: str) -> str:
    return f"table:{table}"


def table_departments(db: Session, table: str) -> list[str]:
    r = db.query(models.AccessRule).filter_by(key=table_key(table)).one_or_none()
    return list(r.departments or []) if r else []


def can_read_table(db: Session, user, table: str) -> bool:
    if table not in CORE_TABLES:
        return False
    return user.department in FULL_ACCESS or user.department in table_departments(db, table)


def can_write_table(user, table: str) -> bool:
    """Chi dev sua noi dung; audit_log chi them (khong ai sua)."""
    return user.department == "dev" and table in CORE_TABLES and CORE_TABLES[table][2] != "audit"


def set_table_rule(db: Session, user, table: str, departments) -> list[str]:
    if table not in CORE_TABLES:
        raise ValueError(f"unknown table: {table!r}")
    if CORE_TABLES[table][2] in ("system", "audit"):
        raise ValueError(f"{table} is admin/dev only and cannot be labelled")
    deps = clean_departments(departments)
    r = db.query(models.AccessRule).filter_by(key=table_key(table)).one_or_none()
    if r is None:
        db.add(models.AccessRule(key=table_key(table), departments=deps, updated_by=user.id))
    else:
        r.departments, r.updated_by = deps, user.id
        r.updated_at = datetime.datetime.now(datetime.timezone.utc)
    db.flush()
    return deps


def apply_default_table_labels(db: Session, user) -> list[str]:
    """Gan nhan de xuat cho cac bang CHUA co quy tac (khong de len lua chon cua admin). Tra ve ten bang da gan."""
    done = []
    for name, (_, deps, kind) in CORE_TABLES.items():
        if kind in ("system", "audit"):
            continue
        if db.query(models.AccessRule).filter_by(key=table_key(name)).first() is None:
            set_table_rule(db, user, name, deps)
            done.append(name)
    return done


def core_grants_sql(db: Session) -> str:
    """SQL GRANT cho Core DB tu cac nhan hien tai, de Topic 4 chay bang tai khoan chu.

    core_admin: doc het | core_dev: doc het + INSERT/UPDATE (+DELETE tru bang tai chinh), audit_log chi INSERT
    core_finance / core_volunteer: chi SELECT tren bang duoc gan nhan.
    """
    roles = ("core_admin", "core_dev", "core_finance", "core_volunteer")
    out = ["-- Sinh tu dong tu nhan truy cap. Chay lai moi khi nhan thay doi.", "BEGIN;"]
    for r in roles:
        out.append(f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{r}') "
                   f"THEN CREATE ROLE {r} NOLOGIN; END IF; END $$;")
    out.append("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM " + ", ".join(roles) + ";")
    for name, (_, _, kind) in CORE_TABLES.items():
        out.append(f"GRANT SELECT ON {name} TO core_admin, core_dev;")
        if kind == "audit":
            out.append(f"GRANT INSERT ON {name} TO core_dev;")
        elif kind == "financial":
            out.append(f"GRANT INSERT, UPDATE ON {name} TO core_dev;")
        else:
            out.append(f"GRANT INSERT, UPDATE, DELETE ON {name} TO core_dev;")
        if kind in ("system", "audit"):
            continue
        for dep in table_departments(db, name):
            out.append(f"GRANT SELECT ON {name} TO core_{dep};")
    out.append("COMMIT;")
    return "\n".join(out) + "\n"


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


def audit(db: Session, user, action: str, query: str | None = None, chunk_ids=None, detail: dict | None = None,
          correlation_id: str | None = None):
    db.add(models.AuditLog(user_id=getattr(user, "id", None), department=getattr(user, "department", None),
                           action=action, query=query,
                           chunk_ids=json.dumps(list(chunk_ids)) if chunk_ids is not None else None,
                           detail=json.dumps(detail, ensure_ascii=False) if detail else None,
                           correlation_id=correlation_id))
