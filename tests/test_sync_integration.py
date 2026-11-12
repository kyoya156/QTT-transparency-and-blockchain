"""Integration checks against a live Postgres with pgvector.

    docker compose up -d db
    .venv/Scripts/python.exe -m pytest -m integration -q

Skipped by default only in the sense that they are marked; run them explicitly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import delete, text

from app.db import init_schema, session_scope
from app.models import Chunk
from app.sync.crawler_client import JsonFileSource
from app.sync.sync_chunks import run_sync

pytestmark = pytest.mark.integration

FIXTURE = Path(__file__).parent / "fixtures" / "chunks_sample.json"


@pytest.fixture(scope="module", autouse=True)
def schema() -> None:
    init_schema()


@pytest.fixture(autouse=True)
def empty_chunks() -> None:
    # the sync job mirrors the whole crawler, so each test starts from nothing
    with session_scope() as session:
        session.execute(delete(Chunk))
    yield
    with session_scope() as session:
        session.execute(delete(Chunk))


def _export(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "chunks.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _fixture_payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _count() -> int:
    with session_scope() as session:
        return session.execute(text("SELECT count(*) FROM chunks")).scalar_one()


def test_first_sync_inserts_and_rerun_is_a_no_op() -> None:
    first = run_sync(JsonFileSource(FIXTURE))
    assert (first.inserted, first.updated, first.deleted, first.unchanged) == (7, 0, 0, 0)
    assert _count() == 7

    second = run_sync(JsonFileSource(FIXTURE))
    assert (second.inserted, second.updated, second.deleted, second.unchanged) == (0, 0, 0, 7)
    assert _count() == 7


def test_changed_content_updates_in_place(tmp_path: Path) -> None:
    run_sync(JsonFileSource(FIXTURE))

    payload = _fixture_payload()
    payload["chunks"][0]["content"] = "Nội dung đã được ban biên tập sửa lại."
    stats = run_sync(JsonFileSource(_export(tmp_path, payload)))

    assert (stats.inserted, stats.updated, stats.deleted, stats.unchanged) == (0, 1, 0, 6)
    assert _count() == 7
    edited = payload["chunks"][0]
    with session_scope() as session:
        content = session.execute(
            text("SELECT content FROM chunks WHERE source_id = :sid AND part = :part"),
            {"sid": edited["source_id"], "part": edited["metadata"]["part"]},
        ).scalar_one()
    assert content.startswith("Nội dung đã được ban biên tập")


def test_missing_chunks_are_deleted(tmp_path: Path) -> None:
    run_sync(JsonFileSource(FIXTURE))

    payload = _fixture_payload()
    payload["chunks"] = [chunk for chunk in payload["chunks"] if chunk["source_type"] == "web"]
    stats = run_sync(JsonFileSource(_export(tmp_path, payload)))

    assert stats.deleted == 2
    assert _count() == len(payload["chunks"])


def test_dry_run_writes_nothing_but_reports_the_diff(tmp_path: Path) -> None:
    run_sync(JsonFileSource(FIXTURE))

    payload = _fixture_payload()
    payload["chunks"] = payload["chunks"][:2]
    stats = run_sync(JsonFileSource(_export(tmp_path, payload)), dry_run=True)

    assert stats.deleted == 5
    assert _count() == 7


def test_fts_matches_without_accents() -> None:
    run_sync(JsonFileSource(FIXTURE))

    with session_scope() as session:
        unaccented = session.execute(
            text("SELECT source_id FROM chunks WHERE tsv @@ plainto_tsquery('simple', :q)"),
            {"q": "quy trinh nhan nuoi"},
        ).scalars().all()
        # "đ" must fold to "d" too, not just the tone marks
        diacritics_folded = session.execute(
            text("SELECT source_id FROM chunks WHERE tsv @@ plainto_tsquery('simple', :q)"),
            {"q": "hoc bong"},
        ).scalars().all()

    assert "page:quy-trinh-nhan-nuoi" in unaccented
    assert "page:hoc-bong" in diacritics_folded


def test_tsv_is_a_stored_generated_column_and_is_indexed() -> None:
    with session_scope() as session:
        generated = session.execute(
            text(
                "SELECT is_generated FROM information_schema.columns "
                "WHERE table_name = 'chunks' AND column_name = 'tsv'"
            )
        ).scalar_one()
        indexes = session.execute(
            text("SELECT indexname FROM pg_indexes WHERE tablename = 'chunks'")
        ).scalars().all()

    assert generated == "ALWAYS"
    assert "ix_chunks_tsv" in indexes
    assert "ix_chunks_embedding_hnsw" in indexes
