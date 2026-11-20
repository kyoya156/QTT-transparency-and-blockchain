"""Answer pipeline: guardrails -> confidence -> compose -> citation check -> reply or hand-off.

`retrieve` is injected so the same flow serves the HTTP path (labelled, RLS-scoped session) and tests.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

from sqlalchemy.orm import Session

from app import models
from app.rag import citations, guardrails
from app.rag.compose import INSUFFICIENT, LLMClient, compose
from app.rag.retrieve import RetrievalResult


@dataclass(slots=True)
class Answer:
    status: str                      # answered | not_found | refused | handoff
    text: str
    reason: str | None = None
    citations: list[dict] = field(default_factory=list)
    handoff_id: int | None = None
    mode: str = "rules"              # rules | llm | extractive


def _handoff(db: Session | None, conversation_id: int | None, reason: str, question: str,
             transcript: str | None = None) -> int | None:
    if db is None or conversation_id is None:
        return None
    row = models.Handoff(conversation_id=conversation_id, reason=reason,
                         transcript=transcript or json.dumps({"question": question}, ensure_ascii=False))
    db.add(row)
    db.flush()
    return row.id


def answer(question: str, retrieve_fn: Callable[[str], RetrievalResult], llm: LLMClient,
           db: Session | None = None, conversation_id: int | None = None,
           transcript: str | None = None) -> Answer:
    mode = getattr(llm, "mode", "llm")
    decision = guardrails.check_input(question)
    if decision.action == "refuse":
        return Answer("refused", guardrails.REFUSE_TEXT, decision.reason)
    if decision.action == "handoff":
        return Answer("handoff", guardrails.HANDOFF_TEXT, decision.reason,
                      handoff_id=_handoff(db, conversation_id, decision.reason, question, transcript))

    result = retrieve_fn(question)
    if not result.chunks or not result.is_confident:
        return Answer("not_found", guardrails.NOT_FOUND_TEXT, "low_confidence")

    try:
        text = compose(question, result, llm)
    except Exception:  # network, auth, quota: a person should see it rather than a silent failure
        return Answer("handoff", guardrails.HANDOFF_TEXT, "llm_error",
                      handoff_id=_handoff(db, conversation_id, "llm_error", question, transcript))

    if INSUFFICIENT in text:
        return Answer("not_found", guardrails.NOT_FOUND_TEXT, "llm_insufficient")

    ok, why = citations.check(text, {str(item.chunk.id) for item in result.chunks})
    if not ok:
        return Answer("handoff", guardrails.HANDOFF_TEXT, why,
                      handoff_id=_handoff(db, conversation_id, why, question, transcript))

    used = set(citations.cited_ids(text))
    cites = [item.citation for item in result.chunks if str(item.chunk.id) in used]
    return Answer("answered", text, citations=cites, mode=mode)
