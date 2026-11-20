"""Citation check. An answer is only shown if every claim traces to a chunk that was actually retrieved."""
from __future__ import annotations

import re

from app.rag.guardrails import contains_personal_data

_CITE = re.compile(r"\[(\d+)\]")


def cited_ids(text: str) -> list[str]:
    seen: list[str] = []
    for m in _CITE.findall(text):
        if m not in seen:
            seen.append(m)
    return seen


def check(text: str, retrieved_ids: set[str]) -> tuple[bool, str | None]:
    """Return (ok, failure_reason)."""
    ids = cited_ids(text)
    if not ids:
        return False, "no_citation"
    if any(i not in retrieved_ids for i in ids):
        return False, "unknown_citation"
    if contains_personal_data(text):
        return False, "personal_data"
    return True, None
