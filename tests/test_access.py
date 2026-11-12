import contextlib
import json

import pytest
from fastapi.testclient import TestClient

from app import access, models
from app.api import search as search_api
from app.db import get_db
from app.main import app
from app.sync.sync_chunks import reconcile


def add_chunks(db, rows):
    for i, (st, sid) in enumerate(rows, start=1):
        db.add(models.Chunk(src_id=i, source_type=st, source_id=sid, content=f"c{i}", content_hash=str(i), labels=[]))
    db.commit()


def labels(db, sid):
    return db.query(models.Chunk).filter_by(source_id=sid).first().labels


@pytest.fixture()
def admin(db):
    u, tok = access.create_user(db, "a@x.org", "Admin", "admin")
    db.commit()
    return u, tok


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


def test_clean_departments():
    assert access.clean_departments(["Finance", "finance", "admin", "volunteers"]) == ["finance", "volunteers"]
    with pytest.raises(ValueError):
        access.clean_departments(["hr"])


def test_unlabelled_by_default_then_source_beats_type(db, admin):
    add_chunks(db, [("web", "p1"), ("web", "p2"), ("post", "f1")])
    assert labels(db, "p1") == []                                   # chua gan nhan = chi admin
    access.set_source_rule(db, admin[0], "web", None, ["volunteers"])   # mac dinh theo loai
    access.set_source_rule(db, admin[0], "web", "p2", ["finance"])      # rieng cho p2
    db.commit()
    assert labels(db, "p1") == ["volunteers"]
    assert labels(db, "p2") == ["finance"]
    assert labels(db, "f1") == []                                   # loai khac khong bi anh huong
    access.clear_source_rule(db, "web", "p2")
    db.commit()
    assert labels(db, "p2") == ["volunteers"]                       # quay ve nhan theo loai
    access.clear_source_rule(db, "web", None)
    db.commit()
    assert labels(db, "p1") == [] and labels(db, "p2") == []        # bo het nhan -> lai chi admin


def test_sync_new_chunk_inherits_label(db, admin):
    access.set_source_rule(db, admin[0], "web", "s1", ["finance"])
    db.commit()
    items = [{"id": 1, "source_type": "web", "source_id": "s1", "content": "a", "metadata": {}},
             {"id": 2, "source_type": "web", "source_id": "s2", "content": "b", "metadata": {}}]
    reconcile(db, items)
    db.commit()
    assert labels(db, "s1") == ["finance"]
    assert labels(db, "s2") == []


def test_tool_access(db, admin):
    fin, _ = access.create_user(db, "f@x.org", "Fin", "finance")
    assert access.can_use_tool(db, admin[0], "search_knowledge")        # admin luon duoc
    assert not access.can_use_tool(db, fin, "search_knowledge")         # chua gan nhan
    access.set_tool_rule(db, admin[0], "search_knowledge", ["finance"])
    assert access.can_use_tool(db, fin, "search_knowledge")
    assert not access.can_use_tool(db, fin, "payment_lookup")
    assert not access.can_use_tool(db, admin[0], "not_a_tool")


def test_token_is_hashed_and_inactive_rejected(db, admin):
    u, tok = admin
    assert tok not in (u.token_hash or "")
    assert access.find_user_by_token(db, tok).id == u.id
    assert access.find_user_by_token(db, "wrong") is None
    u.is_active = False
    assert access.find_user_by_token(db, tok) is None


def test_admin_api_requires_admin(db, client, admin):
    fin, ftok = access.create_user(db, "f@x.org", "Fin", "finance")
    db.commit()
    assert client.get("/api/admin/sources").status_code == 401
    assert client.get("/api/admin/sources", headers=hdr(ftok)).status_code == 403
    assert client.put("/api/admin/access/source", headers=hdr(ftok),
                      json={"source_type": "web", "departments": ["finance"]}).status_code == 403
    assert client.get("/api/admin/sources", headers=hdr(admin[1])).status_code == 200


def test_admin_labels_data_and_audits(db, client, admin):
    add_chunks(db, [("web", "p1")])
    r = client.put("/api/admin/access/source", headers=hdr(admin[1]),
                   json={"source_type": "web", "source_id": "p1", "departments": ["finance", "admin"]})
    assert r.status_code == 200 and r.json()["departments"] == ["finance"]
    assert labels(db, "p1") == ["finance"]
    items = client.get("/api/admin/sources", headers=hdr(admin[1])).json()["items"]
    assert items[0]["departments"] == ["finance"] and items[0]["labelled"] is True
    bad = client.put("/api/admin/access/source", headers=hdr(admin[1]),
                     json={"source_type": "web", "source_id": "p1", "departments": ["hr"]})
    assert bad.status_code == 422
    log = client.get("/api/admin/audit?action=label_change", headers=hdr(admin[1])).json()["items"]
    assert len(log) == 1


def test_search_denied_then_allowed_and_audited(db, client, admin, monkeypatch):
    fin, ftok = access.create_user(db, "f@x.org", "Fin", "finance")
    db.commit()

    class Hit:
        def __init__(self, i): self.chunk = type("C", (), {"id": i})()

    class Res:
        chunks = [Hit(7), Hit(9)]
        def as_dict(self): return {"chunks": [7, 9]}

    monkeypatch.setattr(search_api, "retrieve", lambda *a, **k: Res())
    monkeypatch.setattr(search_api, "user_scope", lambda user: contextlib.nullcontext(db))
    r = client.post("/api/search", headers=hdr(ftok), json={"query": "hoc bong"})
    assert r.status_code == 403
    assert db.query(models.AuditLog).filter_by(action="tool_denied", user_id=fin.id).count() == 1
    access.set_tool_rule(db, admin[0], "search_knowledge", ["finance"])
    db.commit()
    r = client.post("/api/search", headers=hdr(ftok), json={"query": "hoc bong"})
    assert r.status_code == 200
    a = db.query(models.AuditLog).filter_by(action="search").one()
    assert a.department == "finance" and json.loads(a.chunk_ids) == [7, 9]
