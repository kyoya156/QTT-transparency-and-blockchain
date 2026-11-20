"""Record shape for one bank transaction (decided with the owner 2026-11-18).

Money in : amount + donor full name (or Anonymous) + donor ID + bank time
Money out: amount + recipient ID + recipient type + bank time
Every stored record is then linked (team, 2026-11-19, measures 1-3), see `link`:
  seq (1, 2, 3 ...), prev (leaf of record seq-1), balance (running, after this record),
  source_hash (sha256 of the original signed bank message, or of the source row for history imports).
Donor names (owner, 2026-11-20): plain text without diacritics, upper case: "Phạm Thanh Hùng" -> "PHAM THANH HUNG".
The stored record holds only donor_name_hash (salted with its own name_salt, see `hide_name`); the readable name
and name_salt stay in the database behind permissions. So the whole record + salt can be public and anyone
can re-check it against the chain, while the name stays private (team, 2026-11-20).

`time` is when the money moved (bank / dataset time). The chain adds its own block time separately.
Recipient type is open until the Kaggle data is cleaned; "unassigned" until then.
The salted hash of the canonical record is the `leaf` sent to the chain (merkle.leaf_hash).
"""
from __future__ import annotations

import datetime
import hashlib
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


GENESIS = "0x" + "00" * 32          # prev of the first record
FUTURE_SLACK_S = 300                 # bank time is minute precision; a message was seen 19 s before its bank time


def _text(value: str | None) -> str:
    """One byte form per visible text. Vietnamese accents can be stored precomposed or as separate marks;
    without NFC the same-looking name would hash differently. Case and accents are kept as given."""
    return " ".join(unicodedata.normalize("NFC", value or "").split())


def plain_name(value: str | None) -> str:
    """'Phạm Thanh Hùng' -> 'PHAM THANH HUNG'. Bank feeds send this form too, so one donor gets one spelling."""
    t = _text(value).replace("đ", "d").replace("Đ", "D")
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")
    return unicodedata.normalize("NFC", t).upper()


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
        "donor_name": plain_name(donor_name) or ANONYMOUS,   # full name, e.g. "PHAM THANH HUNG"
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


NAME_SALT_BYTES = 16


def name_hash(name: str, name_salt: bytes) -> str:
    """Salted hash of a donor name. Without name_salt nobody can test guesses like 'NGUYEN VAN A'."""
    if len(name_salt) < NAME_SALT_BYTES:
        raise ValueError("name_salt must be at least 16 bytes")
    return "0x" + hashlib.sha256(b"QTT-NAME\x00" + name_salt + name.encode("utf-8")).hexdigest()


def hide_name(rec: dict, name_salt: bytes | None) -> tuple[dict, str | None]:
    """Money in: replace donor_name with donor_name_hash. Returns (record to hash and publish, readable name
    to keep in the database). Money out has no name: returned unchanged with None."""
    if rec["direction"] != "in":
        return rec, None
    out = {k: v for k, v in rec.items() if k != "donor_name"}
    out["donor_name_hash"] = name_hash(rec["donor_name"], name_salt or b"")
    return out, rec["donor_name"]


def _hash32(name: str, value: str) -> str:
    v = (value or "").lower()
    if not (v.startswith("0x") and len(v) == 66 and all(c in "0123456789abcdef" for c in v[2:])):
        raise ValueError(f"{name} must be 0x + 64 hex")
    return v


def link(rec: dict, seq: int, prev: str, balance_before: int, source_hash: str) -> dict:
    """Add the chain-of-records fields. Measures 1-3:
    seq/prev: deleting, inserting or reordering any record breaks every link after it;
    balance: a wrong amount makes every later balance disagree with the real account;
    source_hash: ties the record to the exact message the bank feed signed (message kept in the database)."""
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 1:
        raise ValueError("seq must be an integer >= 1")
    if isinstance(balance_before, bool) or not isinstance(balance_before, int):
        raise ValueError("balance_before must be an integer")
    if seq == 1 and prev != GENESIS:
        raise ValueError("record 1 must link to GENESIS")
    delta = rec["amount"] if rec["direction"] == "in" else -rec["amount"]
    return {**rec, "seq": seq, "prev": _hash32("prev", prev), "balance": balance_before + delta,
            "source_hash": _hash32("source_hash", source_hash)}


def balance_before(rec: dict) -> int:
    """Inverse of link(): the balance the record started from."""
    return rec["balance"] - (rec["amount"] if rec["direction"] == "in" else -rec["amount"])


def check_not_future(rec: dict, now: datetime.datetime | None = None, slack_s: int = FUTURE_SLACK_S) -> None:
    """Bank time later than now is impossible; the contract does not check it, so we do."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if datetime.datetime.fromisoformat(rec["time"]) > now + datetime.timedelta(seconds=slack_s):
        raise ValueError(f"bank time {rec['time']} is in the future")
