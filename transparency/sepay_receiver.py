"""Test receiver for SePay webhooks. Logs only: no database, no chain, no LISTENER_KEY.

    uvicorn transparency.sepay_receiver:app --port 8200
    POST /webhook/sepay

Needs one of SEPAY_WEBHOOK_SECRET (HMAC, preferred) or SEPAY_API_KEY in chain/.env or the environment.
With neither set every call is refused: the receiver never accepts unauthenticated messages.
Each new transaction is appended to transparency_data/sepay-webhooks.jsonl (git-ignored: it holds
account numbers and memos). Repeats of the same SePay id are acknowledged and not logged again.
SePay must reach this from the internet: run a tunnel (e.g. `cloudflared tunnel --url http://localhost:8200`)
and give SePay the https URL + /webhook/sepay.
"""
from __future__ import annotations

import datetime
import json
import os
import pathlib
import threading

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import chain, sepay

LOG = pathlib.Path(os.environ.get("SEPAY_LOG", "transparency_data/sepay-webhooks.jsonl"))
_lock = threading.Lock()

app = FastAPI(title="SePay test receiver")


def _secret(name: str) -> str:
    return os.environ.get(name) or chain.load_env().get(name, "")


def _seen() -> set[str]:
    if not LOG.exists():
        return set()
    return {json.loads(line)["tx"]["source_tx_id"] for line in LOG.read_text(encoding="utf-8").splitlines() if line}


def _auth(request: Request, raw: bytes) -> None:
    sepay.authenticate(request.headers, raw, _secret("SEPAY_WEBHOOK_SECRET"), _secret("SEPAY_API_KEY"))


@app.post("/webhook/sepay")
async def webhook(request: Request) -> JSONResponse:
    raw = await request.body()
    try:
        _auth(request, raw)
    except sepay.AuthError as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=401)
    try:
        tx = sepay.parse(raw)
    except (ValueError, KeyError) as e:
        return JSONResponse({"success": False, "error": f"bad payload: {e}"}, status_code=400)
    with _lock:
        if tx["source_tx_id"] not in _seen():
            LOG.parent.mkdir(parents=True, exist_ok=True)
            entry = {"received_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                     "tx": tx, "raw": raw.decode("utf-8", "replace")}
            with LOG.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return JSONResponse(sepay.OK)
