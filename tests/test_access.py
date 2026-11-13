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
    assert access.clean_departments(["Finance", "finance", "admin", "volunteer"]) == ["finance", "volunteer"]
    with pytest.raises(ValueError):
        access.clean_departments(["hr"])


def test_unlabelled_by_default_then_source_beats_type(db, admin):
    add_chunks(db, [("web", "p1"), ("web", "p2"), ("post", "f1")])
    assert labels(db, "p1") == []                                   # chua gan nhan = chi admin
    access.set_source_rule(db, admin[0], "web", None, ["volunteer"])   # mac dinh theo loai
    access.set_source_rule(db, admin[0], "web", "p2", ["finance"])      # rieng cho p2
    db.commit()
    assert labels(db, "p1") == ["volunteer"]
    assert labels(db, "p2") == ["finance"]
    assert labels(db, "f1") == []                                   # loai khac khong bi anh huong
    access.clear_source_rule(db, "web", "p2")
    db.commit()
    assert labels(db, "p2") == ["volunteer"]                       # quay ve nhan theo loai
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


def test_roles_dev_has_full_read_but_not_admin_api(db, client, admin):
    dev, dtok = access.create_user(db, "d@x.org", "Dev", "dev")
    db.commit()
    assert access.can_use_tool(db, dev, "search_knowledge")             # dev dung moi cong cu
    assert access.can_read_table(db, dev, "family_info")                # dev doc ca bang chua gan nhan
    assert access.can_write_table(dev, "student") and not access.can_write_table(dev, "audit_log")
    assert client.get("/api/admin/sources", headers=hdr(dtok)).status_code == 403   # nhung khong vao admin
    assert access.clean_departments(["dev", "admin", "finance"]) == ["finance"]


def test_table_labels_defaults_and_read_only_roles(db, client, admin):
    fin, _ = access.create_user(db, "f@x.org", "Fin", "finance")
    vol, _ = access.create_user(db, "v@x.org", "Vol", "volunteer")
    db.commit()
    assert not access.can_read_table(db, fin, "bank_transaction")       # chua gan nhan -> chi admin/dev
    assert client.post("/api/admin/access/tables/apply-defaults", headers=hdr(admin[1])).status_code == 200
    assert access.can_read_table(db, fin, "bank_transaction") and access.can_read_table(db, fin, "sponsor")
    assert not access.can_read_table(db, vol, "sponsor")                # volunteer khong thay thong tin nha tai tro
    assert access.can_read_table(db, vol, "sponsorship_assignment") and access.can_read_table(db, vol, "student")
    assert not access.can_read_table(db, fin, "student")
    assert not access.can_read_table(db, vol, "family_info")            # nhay cam: mac dinh chi admin/dev
    assert not access.can_write_table(fin, "bank_transaction")          # finance chi doc
    # admin da chon thi khong bi de len
    client.put("/api/admin/access/table/family_info", headers=hdr(admin[1]), json={"departments": ["volunteer"]})
    client.post("/api/admin/access/tables/apply-defaults", headers=hdr(admin[1]))
    assert access.can_read_table(db, vol, "family_info")
    assert client.put("/api/admin/access/table/audit_log", headers=hdr(admin[1]),
                      json={"departments": ["finance"]}).status_code == 422   # bang he thong khong gan nhan


def test_core_grants_sql(db, admin):
    access.apply_default_table_labels(db, admin[0])
    sql = access.core_grants_sql(db)
    assert "GRANT SELECT ON bank_transaction TO core_finance;" in sql
    assert "GRANT SELECT ON bank_transaction TO core_volunteer;" not in sql
    assert "GRANT SELECT ON student TO core_volunteer;" in sql
    assert "GRANT SELECT ON family_info TO core_finance;" not in sql and "core_volunteer;" not in \
        "\n".join(l for l in sql.splitlines() if "family_info" in l)
    assert "GRANT INSERT ON audit_log TO core_dev;" in sql              # audit chi them
    assert "GRANT INSERT, UPDATE ON bank_transaction TO core_dev;" in sql   # tai chinh khong xoa cung
    assert "GRANT INSERT, UPDATE, DELETE ON student TO core_dev;" in sql
    assert not any(l.startswith("GRANT") and ("core_finance" in l or "core_volunteer" in l) and "INSERT" in l
                   for l in sql.splitlines())                             # finance/volunteer khong co quyen ghi
    assert "app_user TO core_finance" not in sql
