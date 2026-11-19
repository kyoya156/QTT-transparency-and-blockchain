"""Send a fake, correctly signed SePay webhook to a receiver (testing and demos, no bank needed).

    python scripts/sepay_simulate.py in 500000 --memo "Ung ho quy"
    python scripts/sepay_simulate.py out 200000 --url http://localhost:8200/webhook/sepay

Signs with SEPAY_WEBHOOK_SECRET (or sends SEPAY_API_KEY) from chain/.env, like SePay would.
Ids start at 900000000 so they never collide with real SePay ids in the log.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import random
import sys
import time

import httpx

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from transparency import chain, sepay  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("direction", choices=["in", "out"])
    ap.add_argument("amount", type=int)
    ap.add_argument("--memo", default="DEMO transfer")
    ap.add_argument("--url", default="http://localhost:8200/webhook/sepay")
    ap.add_argument("--id", type=int, default=None, help="reuse an id to test dedupe")
    a = ap.parse_args()

    env = chain.load_env()
    secret = os.environ.get("SEPAY_WEBHOOK_SECRET") or env.get("SEPAY_WEBHOOK_SECRET", "")
    key = os.environ.get("SEPAY_API_KEY") or env.get("SEPAY_API_KEY", "")
    now = datetime.datetime.now(sepay.VN_TZ)
    payload = {
        "id": a.id or random.randint(900_000_000, 999_999_999),
        "gateway": "MBBank", "transactionDate": now.strftime("%Y-%m-%d %H:%M:%S"),
        "accountNumber": "0000000000", "subAccount": "", "code": None, "content": a.memo,
        "transferType": a.direction, "description": a.memo, "transferAmount": a.amount,
        "accumulated": 0, "referenceCode": f"DEMO{int(time.time())}",
    }
    raw = json.dumps(payload, ensure_ascii=False).encode()
    headers = {"Content-Type": "application/json"}
    if secret:
        ts = int(time.time())
        headers |= {"X-SePay-Timestamp": str(ts), "X-SePay-Signature": sepay.sign(secret, ts, raw)}
    elif key:
        headers["Authorization"] = f"Apikey {key}"
    else:
        sys.exit("Set SEPAY_WEBHOOK_SECRET or SEPAY_API_KEY in chain/.env first.")
    r = httpx.post(a.url, content=raw, headers=headers, timeout=10)
    print(r.status_code, r.text, "id", payload["id"])


if __name__ == "__main__":
    main()
