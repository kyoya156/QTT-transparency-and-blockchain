"""LocalAnchor: a hash-chained append-only file that stands in for the chain in development.

The on-chain anchor with the same interface is `transparency.chain.BaseSepoliaAnchor`.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import pathlib


class LocalAnchor:
    def __init__(self, path: str | pathlib.Path):
        self.path = pathlib.Path(path)

    def _blocks(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    @staticmethod
    def _hash(block: dict) -> str:
        body = {k: block[k] for k in ("height", "prev", "day", "root", "count", "ts")}
        return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()

    def publish(self, day: str, root_hex: str, count: int) -> dict:
        blocks = self._blocks()
        if any(b["day"] == day for b in blocks):
            raise ValueError(f"{day} is already anchored; anchors are write-once")
        block = {
            "height": len(blocks),
            "prev": blocks[-1]["hash"] if blocks else "0" * 64,
            "day": day, "root": root_hex, "count": count,
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        block["hash"] = self._hash(block)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(block) + "\n")
        return block

    def get(self, day: str) -> dict | None:
        return next((b for b in self._blocks() if b["day"] == day), None)

    def check_chain(self) -> bool:
        prev = "0" * 64
        for i, b in enumerate(self._blocks()):
            if b["height"] != i or b["prev"] != prev or b["hash"] != self._hash(b):
                return False
            prev = b["hash"]
        return True

