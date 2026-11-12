"""Retrieval against a live Postgres, with hand-made vectors so no model is needed.

    docker compose up -d db
    .venv/Scripts/python.exe -m pytest -m integration -q
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import delete, text

from app.db import init_schema, session_scope
from app.models import EMBED_DIM, Chunk
from app.rag.retrieve import _vector_literal, retrieve
from app.sync.crawler_client import JsonFileSource
from app.sync.sync_chunks import run_sync

pytestmark = pytest.mark.integration

FIXTURE = Path(__file__).parent / "fixtures" / "chunks_sample.json"


@pytest.fixture(scope="module", autouse=True)
def schema() -> None:
    init_schema()


@pytest.fixture(autouse=True)
def seeded() -> None:
    with session_scope() as session:
        session.execute(delete(Chunk))
    run_sync(JsonFileSource(FIXTURE))
    yield
    with session_scope() as session:
        session.execute(delete(Chunk))


def unit_vector(index: int) -> list[float]:
    vector = [0.0] * EMBED_DIM
    vector[index] = 1.0
    return vector


def set_vector(source_id: str, part: int, vector: list[float]) -> None:
    with session_scope() as session:
        session.execute(
            text("UPDATE chunks SET embedding = CAST(:vec AS vector) WHERE source_id = :sid AND part = :part"),
            {"vec": _vector_literal(vector), "sid": source_id, "part": part},
        )


def test_vector_search_returns_the_closest_chunk_first() -> None:
    set_vector("page:hoc-bong", 1, unit_vector(0))
    set_vector("page:lien-he", 1, unit_vector(1))

    result = retrieve("mức hỗ trợ hằng tháng", query_embedding=unit_vector(0), k=2)

    assert result.used_vector is True
    assert result.chunks[0].chunk.source_id == "page:hoc-bong"
    assert result.chunks[0].vector_similarity == pytest.approx(1.0, abs=1e-6)
    assert result.is_confident is True


def test_keyword_search_works_without_any_embedding() -> None:
    result = retrieve("học bổng", use_vector=False, k=3)

    assert result.used_vector is False
    assert result.chunks[0].chunk.source_id == "page:hoc-bong"
    assert result.best_ts_rank is not None and result.best_ts_rank > 0


def test_fusion_surfaces_both_lists_top_hits() -> None:
    set_vector("page:hoc-bong", 1, unit_vector(0))
    set_vector("page:lien-he", 1, unit_vector(1))

    # keyword side points at lien-he, vector side points at hoc-bong
    result = retrieve("lien he", query_embedding=unit_vector(0), k=2)

    returned = {item.chunk.source_id for item in result.chunks}
    assert returned == {"page:hoc-bong", "page:lien-he"}
    assert all(item.rrf_score > 0 for item in result.chunks)


def test_unanswerable_query_is_not_confident_and_returns_nothing() -> None:
    result = retrieve("zzzz qqqq xxxx", use_vector=False)

    assert result.chunks == []
    assert result.is_confident is False


def test_chunks_without_embeddings_are_skipped_by_the_vector_side() -> None:
    result = retrieve("zzzz qqqq xxxx", query_embedding=unit_vector(0), k=3)

    assert result.chunks == []
    assert result.best_similarity is None


def test_citation_snapshot_is_stored_ready_for_messages() -> None:
    result = retrieve("học bổng", use_vector=False, k=1)
    citation = result.chunks[0].citation

    assert citation["url"] == "https://example.org/hoc-bong"
    # this page has no own update date, so the crawl date is what the sponsor sees
    assert citation["source_date"] is None
    assert citation["display_date"] == "2026-10-18"
    assert citation["crawled_at"].startswith("2026-10-18")
    assert citation["chunk_id"] == str(result.chunks[0].chunk.id)
