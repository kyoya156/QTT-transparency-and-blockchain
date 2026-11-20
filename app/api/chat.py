"""M4: the internal chat endpoint.

One request = one answer with citations, a stored transcript, an audit row and,
when the assistant cannot answer, a hand-off ticket a volunteer can claim.
Retrieval runs in `user_scope`, so Postgres RLS and the department labels are the
same boundary the search endpoint already uses.
"""
from __future__ import annotations

import datetime
import json
import logging
import time
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import access, models
from ..auth import current_user
from ..config import settings
from ..db import get_db, user_scope
from ..rag import guardrails
from ..rag.answer import Answer, answer
from ..rag.compose import build_llm
from ..rag.embeddings import EmbedderError, get_embedder
from ..rag.ratelimit import ChatLimiter
from ..rag.retrieve import RetrievalResult, retrieve

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")
limiter = ChatLimiter(settings.chat_rate_limit_per_minute, settings.chat_rate_limit_per_hour)

SESSION_PREFIX = "u"


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=settings.chat_max_message_chars)
    conversation_id: int | None = None


class ChatOut(BaseModel):
    conversation_id: int
    message_id: int
    answer: str
    status: str
    mode: str
    reason: str | None = None
    citations: list[dict] = []
    handoff_id: int | None = None
    latency_ms: int


class FeedbackIn(BaseModel):
    message_id: int
    value: Literal["up", "down"]
    note: str | None = Field(default=None, max_length=2000)


class ResolveIn(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


def _session_prefix(user) -> str:
    return f"{SESSION_PREFIX}{user.id}:"


def _conversation(db: Session, user, conversation_id: int | None) -> models.Conversation:
    if conversation_id is not None:
        conv = db.get(models.Conversation, conversation_id)
        if conv is None or not conv.session_id.startswith(_session_prefix(user)):
            raise HTTPException(404, "conversation not found")
        return conv
    # Continue the user's latest thread when the client does not send an id.
    # This keeps the page simple and makes hand-off de-duplication meaningful.
    conv = (db.query(models.Conversation)
            .filter(models.Conversation.session_id.like(_session_prefix(user) + "%"))
            .order_by(models.Conversation.id.desc()).first())
    if conv is not None:
        return conv
    conv = models.Conversation(session_id=_session_prefix(user) + uuid.uuid4().hex)
    db.add(conv)
    db.flush()
    return conv


def _log(db: Session, conv: models.Conversation, role: str, text: str, *,
         intent: str | None = None, evidence_ids: list | None = None, latency_ms: int | None = None) -> models.Message:
    row = models.Message(conversation_id=conv.id, role=role, text=text, intent=intent,
                         evidence_ids=json.dumps(evidence_ids, ensure_ascii=False) if evidence_ids is not None else None,
                         latency_ms=latency_ms)
    db.add(row)
    db.flush()
    return row


def _transcript(db: Session, conv: models.Conversation) -> str:
    rows = db.query(models.Message).filter(models.Message.conversation_id == conv.id).order_by(models.Message.id).all()
    return json.dumps([{"role": m.role, "text": m.text, "at": m.created_at.isoformat() if m.created_at else None}
                       for m in rows], ensure_ascii=False)


def _handoff(db: Session, conv: models.Conversation, reason: str, question: str) -> int:
    existing = (db.query(models.Handoff)
                .filter(models.Handoff.conversation_id == conv.id,
                        models.Handoff.reason == reason,
                        models.Handoff.status.in_(("open", "claimed")))
                .first())
    if existing is not None:
        return existing.id
    row = models.Handoff(conversation_id=conv.id, reason=reason,
                         transcript=_transcript(db, conv) or json.dumps({"question": question}, ensure_ascii=False))
    db.add(row)
    db.flush()
    return row.id


def _retrieve_for_user(user, query: str) -> RetrievalResult:
    with user_scope(user) as db:
        use_vector = db.query(models.Chunk.id).filter(models.Chunk.embedding.is_not(None)).first() is not None
        embedding = None
        if use_vector:
            try:
                embedding = get_embedder().embed_query(query)
            except EmbedderError as exc:
                log.warning("chat vector search off: %s", exc)
                embedding = None
        return retrieve(query, session=db, k=settings.retrieval_k,
                        query_embedding=embedding, use_vector=embedding is not None)


@router.post("/chat", response_model=ChatOut)
def chat(body: ChatIn, user=Depends(current_user), db: Session = Depends(get_db)):
    if not access.can_use_tool(db, user, "search_knowledge"):
        access.audit(db, user, "tool_denied", detail={"tool": "search_knowledge"})
        db.commit()
        raise HTTPException(403, "your department may not use this tool")
    if not limiter.allow(f"user:{user.id}"):
        raise HTTPException(429, "too many messages; please wait a minute")

    conv = _conversation(db, user, body.conversation_id)
    _log(db, conv, "user", body.message, intent="question")
    started = time.perf_counter()

    try:
        result = answer(body.message, lambda q: _retrieve_for_user(user, q), build_llm(),
                        db=db, conversation_id=conv.id, transcript=_transcript(db, conv))
    except Exception:
        log.exception("chat pipeline failed")
        result = Answer("handoff", guardrails.HANDOFF_TEXT, "internal_error")

    if result.status == "not_found" and result.handoff_id is None:
        result.handoff_id = _handoff(db, conv, result.reason or "no_evidence", body.message)
    elif result.status == "handoff" and result.handoff_id is None:
        result.handoff_id = _handoff(db, conv, result.reason or "needs_human", body.message)

    latency_ms = int((time.perf_counter() - started) * 1000)
    chunk_ids = [c.get("chunk_id") for c in result.citations]
    assistant = _log(db, conv, "assistant", result.text, intent=result.status,
                     evidence_ids=chunk_ids, latency_ms=latency_ms)
    access.audit(db, user, "chat", query=body.message, chunk_ids=chunk_ids,
                 detail={"status": result.status, "mode": result.mode, "reason": result.reason},
                 correlation_id=f"conv:{conv.id}")
    db.commit()
    return ChatOut(conversation_id=conv.id, message_id=assistant.id, answer=result.text,
                   status=result.status, mode=result.mode, reason=result.reason,
                   citations=result.citations, handoff_id=result.handoff_id, latency_ms=latency_ms)


@router.post("/feedback")
def feedback(body: FeedbackIn, user=Depends(current_user), db: Session = Depends(get_db)):
    msg = db.get(models.Message, body.message_id)
    if msg is None:
        raise HTTPException(404, "message not found")
    conv = db.get(models.Conversation, msg.conversation_id)
    if conv is None or not conv.session_id.startswith(_session_prefix(user)):
        raise HTTPException(403, "not your conversation")
    db.add(models.Feedback(message_id=msg.id, value=body.value, note=body.note))
    access.audit(db, user, "feedback", detail={"message_id": msg.id, "value": body.value})
    db.commit()
    return {"ok": True}


@router.get("/chat/history")
def history(conversation_id: int | None = None, user=Depends(current_user), db: Session = Depends(get_db)):
    q = db.query(models.Conversation).filter(models.Conversation.session_id.like(_session_prefix(user) + "%"))
    if conversation_id is not None:
        q = q.filter(models.Conversation.id == conversation_id)
    conv = q.order_by(models.Conversation.id.desc()).first()
    if conv is None:
        return {"conversation_id": None, "messages": []}
    rows = (db.query(models.Message).filter(models.Message.conversation_id == conv.id)
            .order_by(models.Message.id).limit(settings.chat_history_limit).all())
    return {"conversation_id": conv.id,
            "messages": [{"id": m.id, "role": m.role, "text": m.text, "intent": m.intent,
                          "created_at": m.created_at.isoformat() if m.created_at else None} for m in rows]}


@router.get("/handoffs")
def list_handoffs(status: str = "open", user=Depends(current_user), db: Session = Depends(get_db)):
    if user.department not in ("admin", "dev", "volunteer"):
        raise HTTPException(403, "admin, dev or volunteer only")
    q = db.query(models.Handoff).order_by(models.Handoff.id.desc())
    if status:
        q = q.filter(models.Handoff.status == status)
    return {"items": [{"id": h.id, "conversation_id": h.conversation_id, "reason": h.reason,
                       "status": h.status, "claimed_by": h.claimed_by,
                       "claimed_at": h.claimed_at.isoformat() if h.claimed_at else None,
                       "created_at": h.created_at.isoformat() if h.created_at else None,
                       "transcript": h.transcript, "resolution": h.resolution}
                      for h in q.limit(200)]}


@router.post("/handoffs/{handoff_id}/claim")
def claim(handoff_id: int, user=Depends(current_user), db: Session = Depends(get_db)):
    if user.department not in ("admin", "volunteer"):
        raise HTTPException(403, "admin or volunteer only")
    row = db.get(models.Handoff, handoff_id)
    if row is None:
        raise HTTPException(404, "handoff not found")
    if row.status != "open":
        raise HTTPException(409, f"handoff is {row.status}")
    row.status = "claimed"
    row.claimed_by = user.id
    row.claimed_at = datetime.datetime.now(datetime.timezone.utc)
    access.audit(db, user, "handoff_claim", detail={"handoff_id": row.id})
    db.commit()
    return {"id": row.id, "status": row.status, "claimed_by": row.claimed_by}


@router.post("/handoffs/{handoff_id}/resolve")
def resolve(handoff_id: int, body: ResolveIn, user=Depends(current_user), db: Session = Depends(get_db)):
    if user.department not in ("admin", "volunteer"):
        raise HTTPException(403, "admin or volunteer only")
    row = db.get(models.Handoff, handoff_id)
    if row is None:
        raise HTTPException(404, "handoff not found")
    if row.status not in ("open", "claimed"):
        raise HTTPException(409, f"handoff is {row.status}")
    row.status = "resolved"
    row.resolution = body.note
    access.audit(db, user, "handoff_resolve", detail={"handoff_id": row.id})
    db.commit()
    return {"id": row.id, "status": row.status}
