"""Pure snapshot reconciliation: no database, no HTTP, easy to test.

The crawler has no created/updated column, so the chatbot does a full snapshot
sync and reconciles by (source_type, source_id, part): insert new, update when
the content hash changed, delete what the crawler no longer returns.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime

ChunkKey = tuple[str, str, int]


@dataclass(frozen=True, slots=True)
class ChunkRecord:
    source_type: str
    source_id: str
    part: int
    content: str
    content_hash: str
    of: int | None = None
    src_id: str | None = None
    url: str | None = None
    title: str | None = None
    source_date: date | None = None
    crawled_at: datetime | None = None

    @property
    def key(self) -> ChunkKey:
        return chunk_key(self.source_type, self.source_id, self.part)


def normalize_part(part: object) -> int:
    """Crawler may send part=null or "2"; the unique key needs a real int."""
    if part is None or part == "":
        return 1
    try:
        value = int(part)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid chunk part: {part!r}") from exc
    if value < 1:
        raise ValueError(f"invalid chunk part: {part!r}")
    return value


def chunk_key(source_type: str, source_id: object, part: object = 1) -> ChunkKey:
    return (source_type, str(source_id), normalize_part(part))


def hash_chunk(
    content: str,
    url: str | None = None,
    title: str | None = None,
    source_date: date | None = None,
) -> str:
    """Hash content plus the fields we show to sponsors, so metadata edits resync too."""
    digest = hashlib.sha256()
    for value in (
        content,
        url or "",
        title or "",
        source_date.isoformat() if source_date else "",
    ):
        digest.update(value.encode("utf-8"))
        digest.update(b"\x1f")
    return digest.hexdigest()


@dataclass(slots=True)
class Diff:
    to_insert: list[ChunkRecord] = field(default_factory=list)
    to_update: list[ChunkRecord] = field(default_factory=list)
    to_delete: list[ChunkKey] = field(default_factory=list)
    unchanged: int = 0


def diff_chunks(
    existing: Mapping[ChunkKey, str],
    incoming: Iterable[ChunkRecord],
) -> Diff:
    """Compare the crawler snapshot against what we already indexed.

    Duplicate keys in `incoming` collapse to the last occurrence (the crawler
    should not send them, but a bad batch must not crash a sync).
    """
    latest: dict[ChunkKey, ChunkRecord] = {}
    for record in incoming:
        latest[record.key] = record

    diff = Diff()
    for key, record in latest.items():
        current_hash = existing.get(key)
        if current_hash is None:
            diff.to_insert.append(record)
        elif current_hash != record.content_hash:
            diff.to_update.append(record)
        else:
            diff.unchanged += 1

    diff.to_delete = sorted(key for key in existing if key not in latest)
    return diff
