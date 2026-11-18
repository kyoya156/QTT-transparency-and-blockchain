"""Bridge from Python to the TransparencyLedger contract on Base Sepolia.

Contract v3 stores only the salted hash of each record (client decision 2026-11-18: hash everything).
The readable record and its salt stay in our database, behind the app's department permissions.
It proves a record existed unchanged at a block time.
It does not prove the record is true.

    leaf  = merkle.leaf_hash(record, salt)          # 32 bytes, salt stays in our database
    refId = HMAC-SHA256(REFID_SECRET, source tx id)  # 32 bytes, hides the bank's id

Env (read from the process, then from chain/.env): LISTENER_KEY, CONTRACT_ADDRESS,
BASE_SEPOLIA_RPC (optional), REFID_SECRET.

    python -m transparency.chain status   # read-only check: role, balance, paused
"""
from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import os
import pathlib
from dataclasses import dataclass

ROOT = pathlib.Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / "chain" / ".env"
ABI = json.loads((pathlib.Path(__file__).with_name("abi.json")).read_text(encoding="utf-8"))
DEFAULT_RPC = "https://sepolia.base.org"
CHAIN_ID = 84532
ENV_KEYS = ("LISTENER_KEY", "CONTRACT_ADDRESS", "BASE_SEPOLIA_RPC", "REFID_SECRET")


# ---------- pure helpers ----------

def ref_id(secret: bytes, source_tx_id: str) -> bytes:
    if not secret:
        raise ValueError("REFID_SECRET is empty")
    return hmac.new(secret, source_tx_id.encode("utf-8"), hashlib.sha256).digest()


def day_number(day: str | datetime.date) -> int:
    """'2026-11-16' -> 20261116, the contract's day key."""
    d = day if isinstance(day, datetime.date) else datetime.date.fromisoformat(day)
    return d.year * 10000 + d.month * 100 + d.day


def unix_time(value: str) -> int:
    t = datetime.datetime.fromisoformat(value)
    if t.tzinfo is None:
        raise ValueError("time needs a timezone")
    return int(t.timestamp())


def _b32(value: bytes | str) -> bytes:
    b = bytes.fromhex(value.removeprefix("0x")) if isinstance(value, str) else bytes(value)
    if len(b) != 32:
        raise ValueError(f"expected 32 bytes, got {len(b)}")
    return b


def load_env(path: pathlib.Path = ENV_FILE) -> dict[str, str]:
    """Process env wins; chain/.env fills the gaps. Values are never printed."""
    env: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    env.update({k: os.environ[k] for k in ENV_KEYS if os.environ.get(k)})
    return env


# ---------- client ----------

@dataclass
class RecordResult:
    status: str          # "sent" | "exists"
    tx_hash: str | None
    recorded_at: int | None = None


class ConflictError(RuntimeError):
    """refId already on chain with a different leaf. Never overwrite; investigate."""


class LedgerClient:
    """Contract logic over a backend with call(name, *args) and send(name, *args) -> receipt dict."""

    def __init__(self, backend):
        self.backend = backend

    def entry(self, ref: bytes) -> dict | None:
        leaf, recorded_at = self.backend.call("entries", _b32(ref))
        if int(recorded_at) == 0:
            return None
        return {"leaf": bytes(leaf), "recorded_at": int(recorded_at)}

    def record(self, ref: bytes, leaf: bytes) -> RecordResult:
        """Send one leaf. Idempotent: a retry with the same leaf returns 'exists'. Nothing readable goes on chain."""
        ref, leaf = _b32(ref), _b32(leaf)
        existing = self.entry(ref)
        if existing:
            if existing["leaf"] != leaf:
                raise ConflictError(f"refId 0x{ref.hex()} already recorded with a different leaf")
            return RecordResult("exists", None, existing["recorded_at"])
        receipt = self.backend.send("record", ref, leaf)
        return RecordResult("sent", receipt["tx_hash"])

    def verify(self, ref: bytes, leaf: bytes) -> tuple[bool, int | None]:
        """(matches, block timestamp). The timestamp says when, not that the record is true."""
        e = self.entry(_b32(ref))
        if e is None or e["leaf"] != _b32(leaf):
            return False, None
        return True, e["recorded_at"]


class BaseSepoliaAnchor:
    """Same interface as LocalAnchor (publish/get/check_chain), backed by anchorBatch on chain."""

    def __init__(self, backend):
        self.backend = backend

    def publish(self, day: str, root_hex: str, count: int) -> dict:
        if self.get(day) is not None:
            raise ValueError(f"{day} is already anchored; anchors are write-once")
        receipt = self.backend.send("anchorBatch", day_number(day), _b32(root_hex), count)
        return {"day": day, "root": root_hex, "count": count, "tx_hash": receipt["tx_hash"],
                "block": receipt.get("block")}

    def get(self, day: str) -> dict | None:
        root, count, recorded_at = self.backend.call("batches", day_number(day))
        if int(recorded_at) == 0:
            return None
        return {"day": day, "root": bytes(root).hex(), "count": int(count), "recorded_at": int(recorded_at)}

    def check_chain(self) -> bool:
        return True  # the public chain does its own integrity check


# ---------- web3 backend ----------

class Web3Backend:
    def __init__(self, rpc: str, contract_address: str, key: str | None = None, timeout: int = 120):
        from web3 import Web3  # imported here so tests and the app do not need web3

        self.w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 30}))
        if not Web3.is_address(contract_address):
            raise ValueError("CONTRACT_ADDRESS is not a valid 0x address")
        self.contract = self.w3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=ABI)
        self.account = self.w3.eth.account.from_key(key) if key else None
        self.timeout = timeout

    def call(self, name: str, *args):
        return getattr(self.contract.functions, name)(*args).call()

    def send(self, name: str, *args) -> dict:
        if self.account is None:
            raise RuntimeError("LISTENER_KEY is not set; this backend is read-only")
        fn = getattr(self.contract.functions, name)(*args)
        tx = fn.build_transaction({
            "from": self.account.address,
            "nonce": self.w3.eth.get_transaction_count(self.account.address, "pending"),
            "chainId": CHAIN_ID,
        })
        signed = self.account.sign_transaction(tx)
        h = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        r = self.w3.eth.wait_for_transaction_receipt(h, timeout=self.timeout)
        if r["status"] != 1:
            raise RuntimeError(f"{name} reverted in tx 0x{bytes(h).hex()}")
        return {"tx_hash": "0x" + bytes(h).hex(), "block": r["blockNumber"]}


def from_env(env: dict[str, str] | None = None, write: bool = True) -> tuple[LedgerClient, BaseSepoliaAnchor, Web3Backend]:
    env = load_env() if env is None else env
    key = env.get("LISTENER_KEY") or None
    if write and not key:
        raise RuntimeError("LISTENER_KEY missing in chain/.env")
    backend = Web3Backend(env.get("BASE_SEPOLIA_RPC") or DEFAULT_RPC, env.get("CONTRACT_ADDRESS", ""), key if write else None)
    return LedgerClient(backend), BaseSepoliaAnchor(backend), backend


def _status() -> int:
    env = load_env()
    _, _, b = from_env(env, write=False)
    print("chain id:", b.w3.eth.chain_id)
    print("contract:", b.contract.address)
    print("paused:", b.call("paused"))
    if env.get("LISTENER_KEY"):
        addr = b.w3.eth.account.from_key(env["LISTENER_KEY"]).address
        role = b.call("RECORDER_ROLE")
        print("listener:", addr)
        print("has RECORDER_ROLE:", b.call("hasRole", role, addr))
        print("balance (ETH):", b.w3.from_wei(b.w3.eth.get_balance(addr), "ether"))
    else:
        print("LISTENER_KEY not set: add it to chain/.env to check the listener")
    print("REFID_SECRET set:", bool(env.get("REFID_SECRET")))
    return 0


if __name__ == "__main__":
    import sys

    if sys.argv[1:] != ["status"]:
        print("usage: python -m transparency.chain status")
        raise SystemExit(2)
    raise SystemExit(_status())
