"""Fill `chunks.embedding` for rows that need it.

Sync clears the embedding of any chunk whose content changed, so this job is the
only thing that (re)computes vectors. It is idempotent: it only looks at NULL
embeddings unless `force` is set.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from sqlalchemy import select

from app.config import get_settings
from app.db import session_scope
from app.models import Chunk
from app.rag.embeddings import Embedder, get_embedder

logger = logging.getLogger(__name__)


def embed_text(chunk: Chunk) -> str:
    """Title is part of the vector: it carries the page's topic as a strong prior."""
    if chunk.title:
        return f"{chunk.title}\n{chunk.content}"
    return chunk.content


def embed_chunks(
    *,
    embedder: Embedder | None = None,
    force: bool = False,
    batch_size: int | None = None,
) -> int:
    """Embed every chunk missing a vector (or all of them when forced). Returns the count."""
    embedder = embedder or get_embedder()
    size = batch_size or get_settings().embed_batch_size

    with session_scope() as session:
        statement = select(Chunk.id).order_by(Chunk.source_type, Chunk.source_id, Chunk.part)
        if not force:
            statement = statement.where(Chunk.embedding.is_(None))
        ids: list[Sequence[object]] = list(session.execute(statement).scalars())

    if not ids:
        logger.info("no chunks need embedding")
        return 0

    logger.info("embedding %d chunks with %s", len(ids), embedder.name)
    total = 0
    for start in range(0, len(ids), size):
        batch = ids[start : start + size]
        with session_scope() as session:
            chunks = (
                session.execute(select(Chunk).where(Chunk.id.in_(batch))).scalars().all()
            )
            if not chunks:
                continue
            vectors = embedder.embed_documents([embed_text(chunk) for chunk in chunks])
            for chunk, vector in zip(chunks, vectors, strict=True):
                chunk.embedding = vector
            total += len(chunks)
        logger.info("embedded %d/%d", total, len(ids))

    return total
