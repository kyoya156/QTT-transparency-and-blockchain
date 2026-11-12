"""Full-snapshot sync: read the crawler, reconcile, record the run."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from sqlalchemy import delete, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db import session_scope
from app.models import Chunk, SyncRun
from app.sync.crawler_client import ChunkSource
from app.sync.reconcile import Diff, ChunkRecord, diff_chunks

logger = logging.getLogger(__name__)

_UPSERT_COLUMNS = (
    "src_id",
    "of",
    "content",
    "content_hash",
    "url",
    "title",
    "source_date",
    "crawled_at",
    "synced_at",
)


@dataclass(slots=True)
class SyncStats:
    fetched: int = 0
    inserted: int = 0
    updated: int = 0
    deleted: int = 0
    unchanged: int = 0
    dry_run: bool = False

    def as_dict(self) -> dict[str, int | bool]:
        return asdict(self)


def _row_values(record: ChunkRecord, synced_at: datetime) -> dict[str, object]:
    return {
        "src_id": record.src_id,
        "source_type": record.source_type,
        "source_id": record.source_id,
        "part": record.part,
        "of": record.of,
        "content": record.content,
        "content_hash": record.content_hash,
        "url": record.url,
        "title": record.title,
        "source_date": record.source_date,
        "crawled_at": record.crawled_at,
        "synced_at": synced_at,
    }


def _apply_diff(session: Session, diff: Diff, synced_at: datetime, stats: SyncStats) -> None:
    if diff.to_delete:
        session.execute(
            delete(Chunk).where(
                tuple_(Chunk.source_type, Chunk.source_id, Chunk.part).in_(diff.to_delete)
            )
        )
        stats.deleted = len(diff.to_delete)

    rows = [_row_values(record, synced_at) for record in diff.to_insert + diff.to_update]
    if rows:
        statement = pg_insert(Chunk).values(rows)
        statement = statement.on_conflict_do_update(
            constraint="uq_chunks_source_part",
            set_={
                **{column: statement.excluded[column] for column in _UPSERT_COLUMNS},
                # an updated chunk has a stale vector; embed_chunks refills it
                "embedding": None,
            },
        )
        session.execute(statement)
        stats.inserted = len(diff.to_insert)
        stats.updated = len(diff.to_update)


def _existing_hashes(session: Session) -> dict[tuple[str, str, int], str]:
    rows = session.execute(
        select(Chunk.source_type, Chunk.source_id, Chunk.part, Chunk.content_hash)
    ).all()
    return {(source_type, source_id, part): content_hash for source_type, source_id, part, content_hash in rows}


def run_sync(source: ChunkSource, *, dry_run: bool = False) -> SyncStats:
    """Mirror every chunk the crawler exposes. Re-running with the same data is a no-op."""
    started_at = datetime.now(timezone.utc)
    stats = SyncStats(dry_run=dry_run)

    records = list(source.iter_records())
    stats.fetched = len(records)

    with session_scope() as session:
        run = SyncRun(started_at=started_at, status="running", source=source.name)
        session.add(run)
        session.flush()

        try:
            diff = diff_chunks(_existing_hashes(session), records)
            stats.unchanged = diff.unchanged
            if dry_run:
                stats.inserted = len(diff.to_insert)
                stats.updated = len(diff.to_update)
                stats.deleted = len(diff.to_delete)
                logger.info(
                    "dry run: +%d ~%d -%d =%d",
                    stats.inserted,
                    stats.updated,
                    stats.deleted,
                    stats.unchanged,
                )
                return stats

            _apply_diff(session, diff, started_at, stats)
            run.finished_at = datetime.now(timezone.utc)
            run.status = "succeeded"
            run.fetched = stats.fetched
            run.inserted = stats.inserted
            run.updated = stats.updated
            run.deleted = stats.deleted
            run.unchanged = stats.unchanged
            session.flush()
        except Exception as exc:  # noqa: BLE001 - recorded, then re-raised
            session.rollback()
            logger.exception("sync failed")
            with session_scope() as failure:
                failure.add(
                    SyncRun(
                        started_at=started_at,
                        finished_at=datetime.now(timezone.utc),
                        status="failed",
                        source=source.name,
                        fetched=stats.fetched,
                        error=str(exc)[:2000],
                    )
                )
            raise

    logger.info(
        "synced %d chunks: +%d ~%d -%d =%d",
        stats.fetched,
        stats.inserted,
        stats.updated,
        stats.deleted,
        stats.unchanged,
    )
    return stats
