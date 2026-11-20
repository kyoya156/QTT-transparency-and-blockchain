from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app import access
from app.config import settings
from app.db import get_db
from app.main import app

DAY = "2026-11-16"


@pytest.fixture()
def world(db, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "session_secret", "test-session-secret")
    monkeypatch.setattr(settings, "transparency_dir", str(tmp_path / "transparency_data"))
    users = {}
    for dept in ("admin", "finance", "volunteer"):
        user, token = access.create_user(db, f"{dept}@example.org", dept.title(), dept)
        users[dept] = (user, token)
    db.commit()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client, db, users
    app.dependency_overrides.clear()


def login(client, token):
    r = client.post("/api/session", json={"token": token})
    assert r.status_code == 200, r.text


def test_admin_creates_batch_and_public_data_hides_records(world):
    client, _db, users = world
    login(client, users["admin"][1])
    r = client.post("/api/transparency/batch", json={"day": DAY})
    assert r.status_code == 200, r.text
    assert r.json()["block"]["count"] == 25

    status = client.get("/api/transparency/status").json()
    assert status["chain_ok"] is True
    assert status["blocks"][0]["day"] == DAY

    public = client.get(f"/api/transparency/batches/{DAY}").json()
    text = json.dumps(public)
    assert "amount_vnd" not in text and "counterparty" not in text


def test_finance_can_read_records_make_and_verify_proof(world):
    client, _db, users = world
    login(client, users["admin"][1])
    assert client.post("/api/transparency/batch", json={"day": DAY}).status_code == 200
    client.cookies.clear()

    login(client, users["finance"][1])
    records = client.get(f"/api/transparency/records/{DAY}")
    assert records.status_code == 200
    assert len(records.json()["records"]) == 25

    proof = client.post("/api/transparency/proof", json={"day": DAY, "record_id": f"{DAY}-004"})
    assert proof.status_code == 200, proof.text
    body = proof.json()
    assert client.post("/api/transparency/verify", json=body).json()["ok"] is True

    body["record"]["amount_vnd"] += 1000
    assert client.post("/api/transparency/verify", json=body).json()["ok"] is False


def test_volunteer_sees_roots_but_not_records_and_cannot_create(world):
    client, _db, users = world
    login(client, users["admin"][1])
    client.post("/api/transparency/batch", json={"day": DAY})
    client.cookies.clear()

    login(client, users["volunteer"][1])
    assert client.get("/api/transparency/status").status_code == 200
    assert client.get("/api/transparency/batches").status_code == 200
    assert client.get(f"/api/transparency/records/{DAY}").status_code == 403
    assert client.post("/api/transparency/batch", json={"day": "2026-11-17"}).status_code == 403


def test_finance_cannot_create_batch(world):
    client, _db, users = world
    login(client, users["finance"][1])
    assert client.post("/api/transparency/batch", json={"day": DAY}).status_code == 403


def test_invalid_day_is_rejected(world):
    client, _db, users = world
    login(client, users["admin"][1])
    assert client.get("/api/transparency/batches/not-a-day").status_code == 422
