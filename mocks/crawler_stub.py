"""Local stand-in for the crawler endpoint, so the chatbot can be built against
the real contract before M0 lands in the crawler repo.

    MOCK_CRAWLER_KEY=dev-local-key \
    MOCK_CRAWLER_FILE=tests/fixtures/chunks_sample.json \
    .venv/Scripts/python.exe -m uvicorn mocks.crawler_stub:app --port 8001

    .venv/Scripts/python.exe scripts/sync_now.py --source http
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, Query
from fastapi.responses import JSONResponse

ALLOWED_SOURCE_TYPES = frozenset({"web", "post"})
DEFAULT_FILE = "tests/fixtures/chunks_sample.json"

app = FastAPI(title="Crawler stub", version="0.1.0")


def _api_key() -> str:
    return os.getenv("MOCK_CRAWLER_KEY", "dev-local-key")


def _rows() -> list[dict[str, Any]]:
    path = Path(os.getenv("MOCK_CRAWLER_FILE", DEFAULT_FILE))
    body = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(body, list):
        return [row for row in body if isinstance(row, dict)]
    return [row for row in body.get("chunks", []) if isinstance(row, dict)]


@app.get("/api/public/chunks")
def public_chunks(
    source_type: list[str] | None = Query(default=None),
    after_id: int = 0,
    limit: int = 500,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> JSONResponse:
    if x_api_key != _api_key():
        return JSONResponse({"error": "missing or invalid X-API-Key"}, status_code=401)

    requested = {value.lower() for value in (source_type or ALLOWED_SOURCE_TYPES)}
    forbidden = requested - ALLOWED_SOURCE_TYPES
    if forbidden:
        # this is the privacy boundary M0 is for: staff data must be unrequestable
        return JSONResponse(
            {"error": f"source_type not allowed: {sorted(forbidden)}"},
            status_code=403,
        )

    rows = sorted(
        (row for row in _rows() if row.get("source_type") in requested),
        key=lambda row: int(row.get("id", 0)),
    )
    limit = max(1, min(limit, 1000))
    page = [row for row in rows if int(row.get("id", 0)) > after_id][:limit]

    return JSONResponse(
        {
            "chunks": page,
            "items": page,  # the sync client reads `items`, ask.py-era exports read `chunks`
            "next_after_id": int(page[-1]["id"]) if page else None,
            "limit": limit,
        }
    )
