"""API cho dashboard admin: gan nhan du lieu/cong cu, quan ly nguoi dung, xem nhat ky. Chi admin."""
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import access, models
from ..auth import require_admin
from ..db import get_db

router = APIRouter(prefix="/api/admin")


class SourceRuleIn(BaseModel):
    source_type: str = Field(min_length=1, max_length=16)
    source_id: str | None = None          # None = ap dung cho ca loai nguon (vd moi trang web)
    departments: list[str] = []           # [] = chi admin


class ToolRuleIn(BaseModel):
    departments: list[str] = []


class UserIn(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    name: str = Field(min_length=1, max_length=120)
    department: str


def _bad(e: ValueError):
    return HTTPException(422, str(e))


@router.get("/departments")
def departments(_=Depends(require_admin)):
    return {"departments": list(access.DEPARTMENTS), "labellable": list(access.LABELLABLE)}


@router.get("/sources")
def sources(source_type: str | None = None, limit: int = 200, offset: int = 0,
            _=Depends(require_admin), db: Session = Depends(get_db)):
    """Moi nguon (trang web, bai Page...) kem nhan hien tai. Nguon chua co nhan chi admin thay."""
    rules = access.load_source_rules(db)
    q = db.query(models.Chunk.source_type, models.Chunk.source_id, func.min(models.Chunk.title),
                 func.min(models.Chunk.url), func.count(models.Chunk.id)).group_by(
        models.Chunk.source_type, models.Chunk.source_id).order_by(models.Chunk.source_type, models.Chunk.source_id)
    if source_type:
        q = q.filter(models.Chunk.source_type == source_type)
    items = []
    for st, sid, title, url, n in q.offset(offset).limit(min(limit, 1000)).all():
        own = access.source_key(st, sid) in rules
        items.append({"source_type": st, "source_id": sid, "title": title, "url": url, "chunks": n,
                      "departments": access.effective_labels(rules, st, sid),
                      "labelled": own or access.source_key(st, None) in rules,
                      "has_own_rule": own})
    type_rules = {k.split(":", 2)[1]: v for k, v in rules.items() if k.endswith(":*")}
    return {"items": items, "type_rules": type_rules}


@router.put("/access/source")
def put_source(body: SourceRuleIn, admin=Depends(require_admin), db: Session = Depends(get_db)):
    try:
        deps = access.set_source_rule(db, admin, body.source_type, body.source_id, body.departments)
    except ValueError as e:
        raise _bad(e)
    access.audit(db, admin, "label_change",
                 detail={"kind": "source", "source_type": body.source_type, "source_id": body.source_id,
                         "departments": deps})
    db.commit()
    return {"departments": deps}


@router.delete("/access/source")
def delete_source(source_type: str, source_id: str | None = None, admin=Depends(require_admin),
                  db: Session = Depends(get_db)):
    """Bo nhan rieng: nguon quay ve nhan theo loai, hoac ve 'chua gan nhan' (chi admin)."""
    removed = access.clear_source_rule(db, source_type, source_id)
    access.audit(db, admin, "label_change",
                 detail={"kind": "source", "source_type": source_type, "source_id": source_id, "removed": removed})
    db.commit()
    return {"removed": removed}


@router.get("/tools")
def tools(_=Depends(require_admin), db: Session = Depends(get_db)):
    return {"items": [{"tool": t, "description": d, "departments": access.tool_departments(db, t)}
                      for t, d in access.TOOLS.items()]}


@router.put("/access/tool/{tool}")
def put_tool(tool: str, body: ToolRuleIn, admin=Depends(require_admin), db: Session = Depends(get_db)):
    try:
        deps = access.set_tool_rule(db, admin, tool, body.departments)
    except ValueError as e:
        raise _bad(e)
    access.audit(db, admin, "label_change", detail={"kind": "tool", "tool": tool, "departments": deps})
    db.commit()
    return {"departments": deps}


@router.get("/tables")
def tables(_=Depends(require_admin), db: Session = Depends(get_db)):
    """Bang cua Core DB va phong ban duoc doc. Bang chua gan nhan chi admin/dev doc duoc."""
    return {"items": [{"table": t, "description": d, "kind": k, "departments": access.table_departments(db, t),
                       "proposed": p, "labellable": k not in ("system", "audit")}
                      for t, (d, p, k) in access.CORE_TABLES.items()]}


@router.put("/access/table/{table}")
def put_table(table: str, body: ToolRuleIn, admin=Depends(require_admin), db: Session = Depends(get_db)):
    try:
        deps = access.set_table_rule(db, admin, table, body.departments)
    except ValueError as e:
        raise _bad(e)
    access.audit(db, admin, "label_change", detail={"kind": "table", "table": table, "departments": deps})
    db.commit()
    return {"departments": deps}


@router.post("/access/tables/apply-defaults")
def apply_defaults(admin=Depends(require_admin), db: Session = Depends(get_db)):
    """Gan nhan de xuat cho cac bang chua co quy tac (khong de len lua chon da luu)."""
    done = access.apply_default_table_labels(db, admin)
    access.audit(db, admin, "label_change", detail={"kind": "table_defaults", "tables": done})
    db.commit()
    return {"applied": done}


@router.get("/core-grants.sql")
def core_grants(_=Depends(require_admin), db: Session = Depends(get_db)):
    """SQL GRANT cho Core DB sinh tu nhan hien tai (de Topic 4 chay)."""
    return Response(access.core_grants_sql(db), media_type="text/plain")


@router.get("/users")
def users(_=Depends(require_admin), db: Session = Depends(get_db)):
    return {"items": [{"id": u.id, "email": u.email, "name": u.name, "department": u.department,
                       "is_active": u.is_active} for u in db.query(models.User).order_by(models.User.id)]}


@router.post("/users")
def create_user(body: UserIn, admin=Depends(require_admin), db: Session = Depends(get_db)):
    """Tao nguoi dung va tra token MOT LAN (DB chi giu ban bam)."""
    if db.query(models.User).filter_by(email=body.email.strip().lower()).first():
        raise HTTPException(409, "email already exists")
    try:
        user, token = access.create_user(db, body.email, body.name, body.department)
    except ValueError as e:
        raise _bad(e)
    access.audit(db, admin, "user_change", detail={"created": user.email, "department": user.department})
    db.commit()
    return {"id": user.id, "email": user.email, "department": user.department, "token": token}


@router.post("/users/{user_id}/deactivate")
def deactivate(user_id: int, admin=Depends(require_admin), db: Session = Depends(get_db)):
    u = db.get(models.User, user_id)
    if u is None:
        raise HTTPException(404, "no such user")
    if u.id == admin.id:
        raise HTTPException(409, "you cannot deactivate yourself")
    u.is_active = False
    access.audit(db, admin, "user_change", detail={"deactivated": u.email})
    db.commit()
    return {"ok": True}


@router.get("/audit")
def audit_log(limit: int = 100, action: str | None = None, _=Depends(require_admin), db: Session = Depends(get_db)):
    q = db.query(models.AuditLog).order_by(models.AuditLog.id.desc())
    if action:
        q = q.filter(models.AuditLog.action == action)
    return {"items": [{"id": a.id, "at": a.at.isoformat() if a.at else None, "user_id": a.user_id,
                       "department": a.department, "action": a.action, "query": a.query,
                       "chunk_ids": a.chunk_ids, "detail": a.detail} for a in q.limit(min(limit, 500))]}
