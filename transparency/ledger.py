"""Synthetic ledger for development. Replace `synthetic_day` with the real bank export once available."""
from __future__ import annotations

import datetime
import random

CATEGORIES = ["scholarship", "tuition", "school supplies", "meals", "transport", "admin", "event"]
DONORS = ["donor-%03d" % n for n in range(1, 41)]


def synthetic_day(day: datetime.date, n: int = 25, seed: int = 0) -> list[dict]:
    rng = random.Random(f"{seed}-{day.isoformat()}")
    rows = []
    for i in range(n):
        incoming = rng.random() < 0.45
        rows.append({
            "id": f"{day.isoformat()}-{i:03d}",
            "date": day.isoformat(),
            "direction": "in" if incoming else "out",
            "amount_vnd": rng.randrange(50, 5000) * 1000,
            "category": "donation" if incoming else rng.choice(CATEGORIES),
            "counterparty": rng.choice(DONORS) if incoming else "beneficiary-%03d" % rng.randrange(1, 120),
        })
    return rows
