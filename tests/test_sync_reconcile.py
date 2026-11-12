from __future__ import annotations

from datetime import date

import pytest

from app.sync.reconcile import (
    ChunkRecord,
    chunk_key,
    diff_chunks,
    hash_chunk,
    normalize_part,
)


def make_record(source_id: str, content: str, *, part: int = 1, source_type: str = "web") -> ChunkRecord:
    return ChunkRecord(
        source_type=source_type,
        source_id=source_id,
        part=part,
        content=content,
        content_hash=hash_chunk(content),
    )


def test_normalize_part_defaults_and_rejects_garbage() -> None:
    assert normalize_part(None) == 1
    assert normalize_part("2") == 2
    assert chunk_key("web", 42) == ("web", "42", 1)
    with pytest.raises(ValueError):
        normalize_part("abc")
    with pytest.raises(ValueError):
        normalize_part(0)


def test_hash_changes_when_metadata_changes() -> None:
    base = hash_chunk("nội dung", "https://example.org/a", "Tiêu đề", date(2026, 10, 1))
    assert base == hash_chunk("nội dung", "https://example.org/a", "Tiêu đề", date(2026, 10, 1))
    assert base != hash_chunk("nội dung", "https://example.org/b", "Tiêu đề", date(2026, 10, 1))
    assert base != hash_chunk("nội dung", "https://example.org/a", "Tiêu đề khác", date(2026, 10, 1))


def test_diff_inserts_updates_deletes_and_keeps_unchanged() -> None:
    kept = make_record("page:a", "giữ nguyên")
    changed = make_record("page:b", "nội dung mới")
    added = make_record("page:c", "trang mới")

    existing = {
        kept.key: kept.content_hash,
        changed.key: hash_chunk("nội dung cũ"),
        chunk_key("web", "page:gone"): hash_chunk("trang đã bị xoá"),
    }

    diff = diff_chunks(existing, [kept, changed, added])

    assert [record.source_id for record in diff.to_insert] == ["page:c"]
    assert [record.source_id for record in diff.to_update] == ["page:b"]
    assert diff.to_delete == [chunk_key("web", "page:gone")]
    assert diff.unchanged == 1


def test_duplicate_keys_collapse_to_last_and_do_not_duplicate_work() -> None:
    first = make_record("page:a", "bản cũ")
    second = make_record("page:a", "bản mới")

    diff = diff_chunks({}, [first, second])

    assert len(diff.to_insert) == 1
    assert diff.to_insert[0].content == "bản mới"


def test_same_source_id_different_part_is_a_distinct_key() -> None:
    a1 = make_record("page:a", "phần một", part=1)
    a2 = make_record("page:a", "phần hai", part=2)

    diff = diff_chunks({a1.key: a1.content_hash}, [a1, a2])

    assert [record.part for record in diff.to_insert] == [2]
    assert diff.to_update == []
    assert diff.to_delete == []
