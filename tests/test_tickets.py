import json

import pytest
from fastapi.testclient import TestClient

from app import access, models
from app.db import get_db
from app.main import app

BODY = {"table_name": "bank_transaction", "record_id": "TX-1", "field_name": "amount",
        "current_value": "500000", "proposed_value": "550000", "reason": "bank statement shows 550000",
        "evidence": "ref FT123"}


@pytest.fixture()
def world(db):
    users = {}
    for dept in ("admin", "dev", "finance", "volunteer"):
        u, tok = access.create_user(db, f"{dept}@x.org", dept, dept)
        users[dept] = (u, {"Authorization": f"Bearer {tok}"})
    access.apply_default_table_labels(db, users["admin"][0])
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app), users
    app.dependency_overrides.clear()


def test_full_flow_with_audit_trail(world, db):
    c, u = world
    t = c.post("/api/tickets", headers=u["finance"][1], json=BODY).json()
    assert t["status"] == "open"
    assert c.post(f"/api/tickets/{t['id']}/apply", headers=u["dev"][1], json={}).status_code == 409   # chua duyet
    d = c.post(f"/api/tickets/{t['id']}/decision", headers=u["admin"][1], json={"approve": True, "note": "ok"})
    assert d.json()["status"] == "approved"
    a = c.post(f"/api/tickets/{t['id']}/apply", headers=u["dev"][1], json={"note": "fixed in core db"}).json()
    assert a["status"] == "applied" and a["applied_value"] == "550000"
    rows = db.query(models.AuditLog).filter_by(correlation_id=f"ticket:{t['id']}").order_by(models.AuditLog.id).all()
    assert sorted(r.action for r in rows) == ["ticket_applied", "ticket_created", "ticket_decided"]
    applied = [r for r in rows if r.action == "ticket_applied"][0]
    detail = json.loads(applied.detail)
    assert detail["before"] == "500000" and detail["after"] == "550000" and applied.department == "dev"
    assert c.post(f"/api/tickets/{t['id']}/cancel", headers=u["finance"][1]).status_code == 409   # da dong


def test_who_can_do_what(world):
    c, u = world
    # chi finance/volunteer de nghi; chi tren bang doc duoc
    assert c.post("/api/tickets", headers=u["dev"][1], json=BODY).status_code == 403
    assert c.post("/api/tickets", headers=u["admin"][1], json=BODY).status_code == 403
    assert c.post("/api/tickets", headers=u["volunteer"][1], json=BODY).status_code == 403   # volunteer khong doc bank_transaction
    assert c.post("/api/tickets", headers=u["finance"][1], json={**BODY, "table_name": "family_info"}).status_code == 403
    assert c.post("/api/tickets", headers=u["finance"][1], json={**BODY, "table_name": "audit_log"}).status_code == 422
    assert c.post("/api/tickets", headers=u["finance"][1], json={**BODY, "table_name": "nope"}).status_code == 422
    t = c.post("/api/tickets", headers=u["finance"][1], json=BODY).json()
    # finance/dev khong duyet duoc
    for who in ("finance", "dev", "volunteer"):
        assert c.post(f"/api/tickets/{t['id']}/decision", headers=u[who][1], json={"approve": True}).status_code == 403
    # chi dev ap dung
    c.post(f"/api/tickets/{t['id']}/decision", headers=u["admin"][1], json={"approve": True})
    for who in ("admin", "finance"):
        assert c.post(f"/api/tickets/{t['id']}/apply", headers=u[who][1], json={}).status_code == 403


def test_visibility_and_reject_and_cancel(world):
    c, u = world
    t = c.post("/api/tickets", headers=u["finance"][1], json=BODY).json()
    assert c.get(f"/api/tickets/{t['id']}", headers=u["volunteer"][1]).status_code == 404   # phieu cua nguoi khac
    assert c.get("/api/tickets", headers=u["volunteer"][1]).json()["items"] == []
    assert len(c.get("/api/tickets", headers=u["dev"][1]).json()["items"]) == 1
    assert c.post(f"/api/tickets/{t['id']}/decision", headers=u["admin"][1], json={"approve": False}).status_code == 422
    r = c.post(f"/api/tickets/{t['id']}/decision", headers=u["admin"][1], json={"approve": False, "note": "no evidence"})
    assert r.json()["status"] == "rejected"
    assert c.post(f"/api/tickets/{t['id']}/decision", headers=u["admin"][1], json={"approve": True}).status_code == 409
    t2 = c.post("/api/tickets", headers=u["finance"][1], json=BODY).json()
    assert c.post(f"/api/tickets/{t2['id']}/cancel", headers=u["volunteer"][1]).status_code == 404
    assert c.post(f"/api/tickets/{t2['id']}/cancel", headers=u["finance"][1]).json()["status"] == "cancelled"
    assert c.get("/api/me", headers=u["dev"][1]).json()["department"] == "dev"
