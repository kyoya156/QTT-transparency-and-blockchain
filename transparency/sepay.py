"""SePay bank feed: webhook authentication and payload parsing (adapter #1 of the bank feeds).

Docs: https://developer.sepay.vn/en/sepay-webhooks/tich-hop-webhook
Auth, one of:
  HMAC : X-SePay-Signature = "sha256=" + hex(HMAC-SHA256(secret, f"{X-SePay-Timestamp}.{raw body}"))
  Key  : Authorization = "Apikey <key>"
SePay counts a delivery as done only on HTTP 200/201 with body exactly {"success": true} within 30 s,
and may resend the same `id` (retries, manual replays), so callers must dedupe on it.
"""
from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import time as _time

VN_TZ = datetime.timezone(datetime.timedelta(hours=7))
TOLERANCE_S = 300
OK = {"success": True}


class AuthError(Exception):
    pass


def sign(secret: str, timestamp: int | str, raw_body: bytes) -> str:
    msg = str(timestamp).encode() + b"." + raw_body
    return "sha256=" + hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def check_hmac(secret: str, timestamp: str | None, signature: str | None, raw_body: bytes,
               now: float | None = None, tolerance: int = TOLERANCE_S) -> None:
    if not timestamp or not signature:
        raise AuthError("missing signature headers")
    try:
        ts = int(timestamp)
    except ValueError:
        raise AuthError("bad timestamp") from None
    if abs((now if now is not None else _time.time()) - ts) > tolerance:
        raise AuthError("timestamp outside tolerance")
    if not hmac.compare_digest(sign(secret, ts, raw_body), signature):
        raise AuthError("bad signature")


def check_apikey(key: str, authorization: str | None) -> None:
    if not authorization or not authorization.startswith("Apikey "):
        raise AuthError("missing api key")
    if not hmac.compare_digest(authorization[len("Apikey "):], key):
        raise AuthError("bad api key")


def authenticate(headers, raw_body: bytes, secret: str = "", key: str = "") -> None:
    """HMAC if a secret is configured, else API key. With neither configured, refuse everything."""
    if secret:
        check_hmac(secret, headers.get("x-sepay-timestamp"), headers.get("x-sepay-signature"), raw_body)
    elif key:
        check_apikey(key, headers.get("authorization"))
    else:
        raise AuthError("no SEPAY_WEBHOOK_SECRET or SEPAY_API_KEY configured")


def parse(raw_body: bytes) -> dict:
    """SePay JSON -> normalised transaction. Keeps the bank's own fields; makes no record decisions."""
    p = json.loads(raw_body)
    if not isinstance(p, dict):
        raise ValueError("payload is not an object")
    if p.get("transferType") not in ("in", "out"):
        raise ValueError("transferType must be 'in' or 'out'")
    amount = p.get("transferAmount")
    if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
        raise ValueError("transferAmount must be a positive integer")
    if p.get("id") is None:
        raise ValueError("id missing")
    # SePay sends Vietnam local time without offset.
    t = datetime.datetime.strptime(p["transactionDate"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=VN_TZ)
    return {
        "source": "sepay",
        "source_tx_id": f"SEPAY-{p['id']}",
        "direction": p["transferType"],
        "amount": amount,
        "currency": "VND",
        "time": t.isoformat(),
        "bank": p.get("gateway") or "",
        "account_number": p.get("accountNumber") or "",
        "memo": p.get("content") or "",
        "code": p.get("code") or None,                    # payment code SePay extracted from the memo by prefix
        "bank_reference": p.get("referenceCode") or "",
        "balance_after": p.get("accumulated") or None,   # 0 = bank does not report it
    }
