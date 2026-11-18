"""Readable records behind department permissions; chain holds only the hash."""
import pytest
from fastapi.testclient import TestClient

from app import access, models
from app.api import ledger as ledger_api
from app.db import get_db
from app.main import app
from tests.test_chain_bridge import SECRET, FakeLedger
from transparency import chain, merkle, records

T = "2026-11-16T09:30:00+07:00"
SALT = bytes(range(16))


@pytest.fixture()
def world(db):
    users = {}
    for dept in ("admin", "dev", "finance", "volunteer"):
        u, tok = access.create_user(db, f"{dept}@x.org", dept, dept)
        users[dept] = {"Authorization": f"Bearer {tok}"}
    access.apply_default_table_labels(db, db.query(models.User).filter_by(department="admin").one())
    client = chain.LedgerClient(FakeLedger())
    for rec in (records.income("IN-1", 500_000, "D-001", T, donor_name="Lan"),
                records.expense("OUT-1", 200_000, "R-017", T)):
        ref = chain.ref_id(SECRET, rec["id"])
        res = client.record(ref, merkle.leaf_hash(rec, SALT))
        ledger_api.store(db, rec, SALT, ref, chain_tx=res.tx_hash)
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[ledger_api.chain_client_factory] = lambda: (lambda: client)
    yield TestClient(app), users
    app.dependency_overrides.clear()


def ids(resp):
    return sorted(r["source_tx_id"] for r in resp.json()["records"])


def test_needs_login(world):
    assert world[0].get("/api/ledger/records").status_code == 401


def test_admin_and_dev_read_everything(world):
    c, u = world
    for dept in ("admin", "dev"):
        assert ids(c.get("/api/ledger/records", headers=u[dept])) == ["IN-1", "OUT-1"]


def test_finance_reads_by_default_labels(world):
    c, u = world
    assert ids(c.get("/api/ledger/records", headers=u["finance"])) == ["IN-1", "OUT-1"]
    r = c.get("/api/ledger/records/IN-1", headers=u["finance"]).json()
    assert r["record"]["donor_name"] == "Lan" and r["salt"] == SALT.hex()
    assert r["leaf"] == "0x" + merkle.leaf_hash(r["record"], bytes.fromhex(r["salt"])).hex()


def test_volunteer_is_refused_and_logged(world, db):
    c, u = world
    assert c.get("/api/ledger/records", headers=u["volunteer"]).status_code == 403
    assert c.get("/api/ledger/records?direction=in", headers=u["volunteer"]).status_code == 403
    assert c.get("/api/ledger/records/IN-1", headers=u["volunteer"]).status_code == 404   # same as missing
    assert db.query(models.AuditLog).filter_by(action="ledger_denied").count() == 3


def test_label_change_takes_effect(world, db):
    c, u = world
    admin = db.query(models.User).filter_by(department="admin").one()
    access.set_table_rule(db, admin, "disbursement", ["volunteer"])
    db.commit()
    assert ids(c.get("/api/ledger/records", headers=u["volunteer"])) == ["OUT-1"]
    assert c.get("/api/ledger/records?direction=out", headers=u["finance"]).status_code == 403


def test_check_chain_and_tamper(world, db):
    c, u = world
    r = c.get("/api/ledger/records/OUT-1?check_chain=true", headers=u["finance"]).json()
    assert r["chain"]["checked"] and r["chain"]["match"] and r["chain"]["block_timestamp"]
    row = db.query(models.LedgerRecord).filter_by(source_tx_id="OUT-1").one()
    row.record_json = row.record_json.replace("200000", "900000")
    db.commit()
    r = c.get("/api/ledger/records/OUT-1?check_chain=true", headers=u["finance"]).json()
    assert r["chain"]["match"] is False


def test_reads_are_audited(world, db):
    c, u = world
    c.get("/api/ledger/records/IN-1", headers=u["finance"])
    assert db.query(models.AuditLog).filter_by(action="ledger_read").count() == 1
