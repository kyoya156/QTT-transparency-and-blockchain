"""Record shape for one bank transaction (decided with the owner 2026-11-18).

Money in : amount + donor full name (or Anonymous) + donor ID + bank time
Money out: amount + recipient ID + recipient type + bank time

`time` is when the money moved (bank / dataset time). The chain adds its own block time separately.
Recipient type is open until the Kaggle data is cleaned; "unassigned" until then.
The salted hash of the canonical record is the `leaf` sent to the chain (merkle.leaf_hash).
"""
from __future__ import annotations

import datetime
import unicodedata

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


def _text(value: str | None) -> str:
    """One byte form per visible text. Vietnamese accents can be stored precomposed or as separate marks;
    without NFC the same-looking name would hash differently. Case and accents are kept as given."""
    return " ".join(unicodedata.normalize("NFC", value or "").split())


def _required(name: str, value: str) -> str:
    value = _text(value)
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
        "donor_name": _text(donor_name) or ANONYMOUS,   # full name, e.g. "Phạm Thanh Hùng"
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
        "recipient_type": _text(recipient_type).lower() or UNASSIGNED,
        "time": _time(time),
    }
