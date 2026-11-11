"""Hybrid retrieval: accent-insensitive full-text + pgvector cosine, fused with RRF.

Two deliberate choices worth knowing before tuning:

* `confidence` is computed from the *raw* signals (best cosine similarity, best
  ts_rank), never from the RRF score. RRF scores only encode ranks, so they cannot
  answer "is there enough evidence to answer at all" - that is the decision that
  makes the bot say "không tìm thấy" instead of guessing.
* The fusion pool is wider than k: both lists are taken to `pool` depth, then the
  top-k is cut after fusion, so a chunk ranked 8th in both lists can still win.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, func, literal, literal_column, select, type_coerce
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import session_scope
from app.models import EMBED_DIM, Chunk
from app.rag.embeddings import Embedder, get_embedder
from app.sync.crawler_client import effective_allowlist

# 'simple'::regconfig must be a SQL literal, not a bind parameter: PostgreSQL
# cannot pick the plainto_tsquery(regconfig, text) overload for an untyped param.
_SIMPLE_CONFIG = literal_column("'simple'::regconfig")


def _vector_literal(vector: list[float]) -> str:
    """pgvector's text form; keeps psycopg from needing a registered adapter."""
    return "[" + ",".join(f"{value:.7f}" for value in vector) + "]"


def _tsquery(query_text: str):
    return func.plainto_tsquery(_SIMPLE_CONFIG, func.immutable_unaccent(query_text))


def _fts_rows(session: Session, query_text: str, source_types: list[str], limit: int) -> list[Any]:
    tsquery = _tsquery(query_text)
    rank = func.ts_rank(Chunk.tsv, tsquery)
    statement = (
        select(Chunk, rank.label("fts_rank"))
        .where(Chunk.tsv.op("@@")(tsquery), Chunk.source_type.in_(source_types))
        .order_by(rank.desc())
        .limit(limit)
    )
    return list(session.execute(statement).all())


def _vector_rows(
    session: Session, query_vector: list[float], source_types: list[str], limit: int
) -> list[Any]:
    # type_coerce matters: without it SQLAlchemy infers the Vector type for the
    # distance expression and hands a float to pgvector's text parser.
    distance = type_coerce(
        Chunk.embedding.op("<=>")(
            literal(_vector_literal(query_vector)).cast(Vector(EMBED_DIM))
        ),
        Float,
    )
    statement = (
        select(Chunk, distance.label("distance"))
        .where(Chunk.embedding.is_not(None), Chunk.source_type.in_(source_types))
        .order_by(distance.asc())
        .limit(limit)
    )
    return list(session.execute(statement).all())


@dataclass(slots=True)
class RetrievedChunk:
    chunk: Chunk
    fts_rank: float | None = None
    vector_similarity: float | None = None
    rrf_score: float = 0.0

    @property
    def citation(self) -> dict[str, Any]:
        """Snapshot stored with the answer; ids alone break on the next re-sync."""
        chunk = self.chunk
        display = chunk.display_date
        return {
            "chunk_id": str(chunk.id),
            "source_type": chunk.source_type,
            "source_id": chunk.source_id,
            "part": chunk.part,
            "url": chunk.url,
            "title": chunk.title,
            "source_date": chunk.source_date.isoformat() if chunk.source_date else None,
            "crawled_at": chunk.crawled_at.isoformat() if chunk.crawled_at else None,
            "display_date": display.isoformat() if display else None,
        }


@dataclass(slots=True)
class RetrievalResult:
    query: str
    chunks: list[RetrievedChunk]
    best_similarity: float | None = None
    best_ts_rank: float | None = None
    used_vector: bool = False

    @property
    def is_confident(self) -> bool:
        """Enough evidence to answer, using raw scores and configurable thresholds."""
        if not self.chunks:
            return False
        settings = get_settings()
        if (
            self.best_similarity is not None
            and self.best_similarity >= settings.retrieval_min_similarity
        ):
            return True
        return (
            self.best_ts_rank is not None
            and self.best_ts_rank >= settings.retrieval_min_ts_rank
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "is_confident": self.is_confident,
            "used_vector": self.used_vector,
            "best_similarity": self.best_similarity,
            "best_ts_rank": self.best_ts_rank,
            "chunks": [
                {
                    **item.citation,
                    "rrf_score": round(item.rrf_score, 6),
                    "fts_rank": item.fts_rank,
                    "vector_similarity": item.vector_similarity,
                    "content": item.chunk.content,
                }
                for item in self.chunks
            ],
        }


def retrieve(
    query: str,
    *,
    session: Session | None = None,
    k: int | None = None,
    pool: int | None = None,
    source_types: list[str] | None = None,
    query_embedding: list[float] | None = None,
    embedder: Embedder | None = None,
    use_vector: bool = True,
) -> RetrievalResult:
    """Return the top-k chunks with their citations and an evidence verdict."""
    settings = get_settings()
    query = (query or "").strip()
    if not query:
        return RetrievalResult(query="", chunks=[])

    k = k or settings.retrieval_k
    pool_size = max(pool or settings.retrieval_pool, k)
    types = source_types or sorted(effective_allowlist())

    if use_vector and query_embedding is None:
        embedder = embedder or get_embedder()
        query_embedding = embedder.embed_query(query)

    def _search(session: Session) -> RetrievalResult:
        merged: dict[UUID, RetrievedChunk] = {}
        scores: dict[UUID, float] = {}

        for position, (chunk, fts_rank) in enumerate(
            _fts_rows(session, query, types, pool_size), start=1
        ):
            item = merged.setdefault(chunk.id, RetrievedChunk(chunk=chunk))
            item.fts_rank = float(fts_rank) if fts_rank is not None else None
            scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (settings.rrf_k + position)

        if query_embedding is not None:
            for position, (chunk, distance) in enumerate(
                _vector_rows(session, query_embedding, types, pool_size), start=1
            ):
                item = merged.setdefault(chunk.id, RetrievedChunk(chunk=chunk))
                item.vector_similarity = 1.0 - float(distance) if distance is not None else None
                scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (
                    settings.rrf_k + position
                )

        for chunk_id, score in scores.items():
            merged[chunk_id].rrf_score = score

        ranked = sorted(merged.values(), key=lambda item: item.rrf_score, reverse=True)[:k]
        similarities = [
            item.vector_similarity
            for item in merged.values()
            if item.vector_similarity is not None
        ]
        ranks = [item.fts_rank for item in merged.values() if item.fts_rank is not None]

        return RetrievalResult(
            query=query,
            chunks=ranked,
            best_similarity=max(similarities) if similarities else None,
            best_ts_rank=max(ranks) if ranks else None,
            used_vector=query_embedding is not None,
        )

    if session is not None:
        return _search(session)
    with session_scope() as scoped:
        return _search(scoped)
