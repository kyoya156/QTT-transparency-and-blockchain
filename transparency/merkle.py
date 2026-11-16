"""Salted Merkle tree. Leaves and inner nodes use different prefixes so one cannot pass for the other."""
from __future__ import annotations

import hashlib
import json

LEAF = b"\x00"
NODE = b"\x01"


def canonical(record: dict) -> bytes:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def leaf_hash(record: dict, salt: bytes) -> bytes:
    return hashlib.sha256(LEAF + salt + canonical(record)).digest()


def _node(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(NODE + left + right).digest()


def _levels(leaves: list[bytes]) -> list[list[bytes]]:
    if not leaves:
        raise ValueError("cannot build a tree with no leaves")
    levels = [list(leaves)]
    while len(levels[-1]) > 1:
        cur, nxt = levels[-1], []
        for i in range(0, len(cur), 2):
            # An odd node moves up unchanged. Duplicating it would let two different batches share a root.
            nxt.append(_node(cur[i], cur[i + 1]) if i + 1 < len(cur) else cur[i])
        levels.append(nxt)
    return levels


def root(leaves: list[bytes]) -> bytes:
    return _levels(leaves)[-1][0]


def proof(leaves: list[bytes], index: int) -> list[tuple[str, str]]:
    """Sibling path for leaf `index` as (side, hex) pairs, side being where the sibling sits."""
    if not 0 <= index < len(leaves):
        raise IndexError(index)
    path, idx = [], index
    for level in _levels(leaves)[:-1]:
        sib = idx ^ 1
        if sib < len(level):
            path.append(("right" if sib > idx else "left", level[sib].hex()))
        idx //= 2
    return path


def verify(record: dict, salt: bytes, path: list[tuple[str, str]], expected_root: str) -> bool:
    h = leaf_hash(record, salt)
    for side, sib_hex in path:
        sib = bytes.fromhex(sib_hex)
        h = _node(sib, h) if side == "left" else _node(h, sib)
    return h.hex() == expected_root
