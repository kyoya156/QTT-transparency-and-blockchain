"""Record shape for one bank transaction (decided with the owner 2026-11-18).

Money in : amount + donor name + donor ID + bank time
Money out: amount + recipient ID + recipient type + bank time

`time` is when the money moved (bank / dataset time). The chain adds its own block time separately.
Recipient type is open until the Kaggle data is cleaned; "unassigned" until then.
The salted hash of the canonical record is the `leaf` sent to the chain (merkle.leaf_hash).
"""
from __future__ import annotations

import datetime

ANONYMOUS = "Anonymous"
UNASSIGNED = "unassigned"


def _time(value: str | datetime.datetime) -> str:
    t = value if isinstance(value, datetime.datetime) else datetime.datetime.fromisoformat(value)
    if t.tzinfo is None:
        raise ValueError("time needs a timezone, e.g. 2026-11-16T09:30:00+07:00")
    return t.isoformat()


def _amount(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("amount must be a positive integer in the smallest unit (e.g. VND)")
    return value


def _required(name: str, value: str) -> str:
    value = (value or "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def income(source_tx_id: str, amount: int, donor_id: str, time, donor_name: str | None = None,
           currency: str = "VND") -> dict:
    return {
        "id": _required("source_tx_id", source_tx_id),
        "direction": "in",
        "amount": _amount(amount),
        "currency": _required("currency", currency).upper(),
        "donor_id": _required("donor_id", donor_id),
        "donor_name": (donor_name or "").strip() or ANONYMOUS,
        "time": _time(time),
    }


def expense(source_tx_id: str, amount: int, recipient_id: str, time, recipient_type: str | None = None,
            currency: str = "VND") -> dict:
    return {
        "id": _required("source_tx_id", source_tx_id),
        "direction": "out",
        "amount": _amount(amount),
        "currency": _required("currency", currency).upper(),
        "recipient_id": _required("recipient_id", recipient_id),
        "recipient_type": (recipient_type or "").strip().lower() or UNASSIGNED,
        "time": _time(time),
    }
