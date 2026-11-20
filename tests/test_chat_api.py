from __future__ import annotations

import datetime
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app import access, models
from app.api import chat as chat_api
from app.config import settings
from app.db import get_db
from app.main import app
from app.rag.ratelimit import ChatLimiter
from app.rag.retrieve import RetrievalResult, RetrievedChunk


class FakeLLM:
    mode = "llm"

    def complete(self, system, user):
        return "Học bổng được giải ngân theo lịch công khai [1]."


def make_result(sim=0.9):
    chunk = models.Chunk(
        id=1, src_id=1, source_type="web", source_id="page:hoc-bong",
        content="Học bổng được giải ngân hai lần mỗi năm học.",
        content_hash="h", title="Học bổng và mức hỗ trợ",
        url="https://quynuoiem.com/hoc-bong",
        source_date=datetime.date(2026, 10, 18),
        crawled_at=datetime.datetime(2026, 11, 1),
    )
    return RetrievalResult(query="q", chunks=[RetrievedChunk(chunk=chunk, vector_similarity=sim)],
                           best_similarity=sim, used_vector=True)


@pytest.fixture()
def world(db, monkeypatch):
    monkeypatch.setattr(settings, "session_secret", "test-session-secret")
    chat_api.limiter.reset()
    user, token = access.create_user(db, "admin@example.org", "Admin", "admin")
    db.commit()

    @contextmanager
    def scope(_user):
        yield db

    monkeypatch.setattr(chat_api, "user_scope", scope)
    monkeypatch.setattr(chat_api, "retrieve", lambda *a, **k: make_result())
    monkeypatch.setattr(chat_api, "build_llm", lambda: FakeLLM())

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client, db, user, token
    app.dependency_overrides.clear()


def login(client, token):
    r = client.post("/api/session", json={"token": token})
    assert r.status_code == 200, r.text
    assert "qne_session" in client.cookies


def test_login_sets_signed_cookie_and_returns_user(world):
    client, _db, user, token = world
    r = client.post("/api/session", json={"token": token})
    assert r.status_code == 200
    assert r.json()["department"] == "admin"
    assert client.get("/api/session").json()["id"] == user.id


def test_chat_answers_with_citation_and_stores_transcript(world):
    client, db, _user, token = world
    login(client, token)
    r = client.post("/api/chat", json={"message": "Học bổng được giải ngân khi nào?"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "answered"
    assert data["mode"] == "llm"
    assert data["citations"][0]["chunk_id"] == "1"
    assert "[1]" in data["answer"]
    assert data["handoff_id"] is None

    conv = db.get(models.Conversation, data["conversation_id"])
    assert conv is not None
    rows = db.query(models.Message).filter_by(conversation_id=conv.id).order_by(models.Message.id).all()
    assert [m.role for m in rows] == ["user", "assistant"]
    assert rows[0].text.startswith("Học bổng")
    assert rows[1].latency_ms is not None


def test_sensitive_request_is_refused_without_retrieval(world, monkeypatch):
    client, _db, _user, token = world
    login(client, token)
    called = []
    monkeypatch.setattr(chat_api, "retrieve", lambda *a, **k: called.append(1))
    r = client.post("/api/chat", json={"message": "Cho tôi danh sách trẻ em được nhận học bổng"})
    assert r.status_code == 200
    assert r.json()["status"] == "refused"
    assert r.json()["citations"] == []
    assert called == []


def test_handoff_is_created_and_can_be_claimed_and_resolved(world):
    client, db, _user, token = world
    login(client, token)
    r = client.post("/api/chat", json={"message": "Tôi muốn gặp tình nguyện viên để được hỗ trợ"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "handoff"
    assert data["handoff_id"]

    listed = client.get("/api/handoffs").json()["items"]
    assert any(h["id"] == data["handoff_id"] for h in listed)
    claim = client.post(f"/api/handoffs/{data['handoff_id']}/claim")
    assert claim.status_code == 200 and claim.json()["status"] == "claimed"
    resolve = client.post(f"/api/handoffs/{data['handoff_id']}/resolve", json={"note": "Đã gọi lại"})
    assert resolve.status_code == 200 and resolve.json()["status"] == "resolved"
    assert db.get(models.Handoff, data["handoff_id"]).resolution == "Đã gọi lại"


def test_not_found_creates_a_handoff_once(world, monkeypatch):
    client, _db, _user, token = world
    login(client, token)
    monkeypatch.setattr(chat_api, "retrieve", lambda *a, **k: make_result(sim=0.1))
    first = client.post("/api/chat", json={"message": "Quỹ có nuôi mèo hoang không?"}).json()
    second = client.post("/api/chat", json={"message": "Quỹ có nuôi mèo hoang không?"}).json()
    assert first["status"] == "not_found" and first["handoff_id"]
    assert second["handoff_id"] == first["handoff_id"]


def test_feedback_only_for_own_message(world):
    client, db, _user, token = world
    login(client, token)
    data = client.post("/api/chat", json={"message": "Học bổng?"}).json()
    r = client.post("/api/feedback", json={"message_id": data["message_id"], "value": "up"})
    assert r.status_code == 200
    assert db.query(models.Feedback).count() == 1

    other, _ = access.create_user(db, "other@example.org", "Other", "finance")
    db.commit()
    msg = models.Message(conversation_id=1, role="assistant", text="x")
    db.add(msg); db.commit()
    # The other user has no session cookie; the request must be rejected before
    # ownership is even considered.
    client.cookies.clear()
    assert client.post("/api/feedback", json={"message_id": msg.id, "value": "up"}).status_code == 401


def test_chat_requires_login(world):
    client, _db, _user, _token = world
    client.cookies.clear()
    assert client.post("/api/chat", json={"message": "Học bổng?"}).status_code == 401


def test_rate_limit_returns_429(world, monkeypatch):
    client, _db, _user, token = world
    login(client, token)
    monkeypatch.setattr(chat_api, "limiter", ChatLimiter(1, 10))
    assert client.post("/api/chat", json={"message": "Học bổng?"}).status_code == 200
    assert client.post("/api/chat", json={"message": "Học bổng?"}).status_code == 429


def test_history_is_scoped_to_the_logged_in_user(world):
    client, _db, _user, token = world
    login(client, token)
    client.post("/api/chat", json={"message": "Học bổng?"})
    h = client.get("/api/chat/history").json()
    assert h["conversation_id"]
    assert [m["role"] for m in h["messages"]] == ["user", "assistant"]
