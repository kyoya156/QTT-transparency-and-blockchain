from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from app.models import Chunk
from app.rag.retrieve import RetrievalResult, RetrievedChunk, _vector_literal


def make_chunk(**overrides) -> Chunk:
    values = {
        "id": uuid4(),
        "source_type": "web",
        "source_id": "page:hoc-bong",
        "part": 1,
        "content": "Học bổng được giải ngân hai lần mỗi năm học.",
        "content_hash": "deadbeef",
        "url": "https://example.org/hoc-bong",
        "title": "Học bổng và mức hỗ trợ",
        "source_date": date(2026, 10, 18),
    }
    values.update(overrides)
    return Chunk(**values)


def test_vector_literal_is_pgvector_text_format() -> None:
    assert _vector_literal([1.0, 0.5, -0.25]) == "[1.0000000,0.5000000,-0.2500000]"


def test_citation_carries_the_source_snapshot() -> None:
    item = RetrievedChunk(chunk=make_chunk())

    citation = item.citation

    assert citation["url"] == "https://example.org/hoc-bong"
    assert citation["title"] == "Học bổng và mức hỗ trợ"
    assert citation["source_date"] == "2026-10-18"
    assert citation["display_date"] == "2026-10-18"
    assert citation["source_id"] == "page:hoc-bong"
    assert citation["chunk_id"]


def test_display_date_falls_back_to_the_crawl_date() -> None:
    chunk = make_chunk(
        source_date=None,
        crawled_at=datetime(2026, 10, 20, 9, 0, tzinfo=timezone.utc),
    )

    assert chunk.display_date == date(2026, 10, 20)
    assert RetrievedChunk(chunk=chunk).citation["source_date"] is None


def test_display_date_is_empty_when_the_crawler_knows_nothing() -> None:
    chunk = make_chunk(source_date=None, crawled_at=None)

    assert chunk.display_date is None
    assert RetrievedChunk(chunk=chunk).citation["display_date"] is None


def test_empty_result_is_never_confident() -> None:
    assert RetrievalResult(query="bất kỳ", chunks=[]).is_confident is False


def test_confidence_follows_the_raw_signals_not_the_fused_rank() -> None:
    strong = RetrievalResult(
        query="học bổng",
        chunks=[RetrievedChunk(chunk=make_chunk(), rrf_score=0.016)],
        best_similarity=0.82,
        best_ts_rank=0.0,
    )
    weak = RetrievalResult(
        query="học bổng",
        chunks=[RetrievedChunk(chunk=make_chunk(), rrf_score=0.016)],
        best_similarity=0.12,
        best_ts_rank=0.001,
    )

    assert strong.is_confident is True
    assert weak.is_confident is False


def test_keyword_only_needs_a_much_higher_bar() -> None:
    """A nonsense question scored 0.0369 ts_rank on the fixture, so a common-word
    match at that level is not evidence."""
    common_words = RetrievalResult(
        query="quy co nhan nuoi meo hoang khong",
        chunks=[RetrievedChunk(chunk=make_chunk(), rrf_score=0.016)],
        best_similarity=None,
        best_ts_rank=0.0369,
    )
    keyword_only = RetrievalResult(
        query="hoc bong giai ngan",
        chunks=[RetrievedChunk(chunk=make_chunk(), rrf_score=0.016)],
        best_similarity=None,
        best_ts_rank=0.24,
    )

    assert common_words.is_confident is False
    assert keyword_only.is_confident is False  # below the 0.30 keyword-only bar


def test_keyword_only_can_answer_when_the_match_is_strong() -> None:
    strong = RetrievalResult(
        query="hoc bong giai ngan hai lan moi nam",
        chunks=[RetrievedChunk(chunk=make_chunk(), rrf_score=0.016)],
        best_similarity=None,
        best_ts_rank=0.42,
    )

    assert strong.is_confident is True
