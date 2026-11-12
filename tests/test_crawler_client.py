from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.sync.crawler_client import (
    HttpChunkSource,
    InvalidChunk,
    JsonFileSource,
    normalize_chunk,
)

FIXTURE = Path(__file__).parent / "fixtures" / "chunks_sample.json"


def test_json_export_is_read_with_metadata_and_dates() -> None:
    records = list(JsonFileSource(FIXTURE).iter_records())

    assert len(records) == 7
    web = next(record for record in records if record.source_type == "web")
    assert web.part == 1
    assert web.of == 2
    assert web.url.startswith("https://example.org/")
    assert web.crawled_at is not None and web.crawled_at.tzinfo is not None

    post = next(record for record in records if record.source_type == "post")
    assert post.source_date is not None
    assert post.source_date.isoformat() == "2026-09-05"


def test_flat_fields_win_and_part_defaults_to_one() -> None:
    record = normalize_chunk(
        {
            "id": 7,
            "source_type": "WEB",
            "source_id": "page:x",
            "content": "  nội dung  ",
            "url": "https://example.org/x",
            "metadata": {"title": "Tiêu đề", "part": None},
        }
    )

    assert record.source_type == "web"
    assert record.content == "nội dung"
    assert record.part == 1
    assert record.title == "Tiêu đề"


@pytest.mark.parametrize("source_type", ["message", "comment", "meal", ""])
def test_only_web_and_post_are_indexable(source_type: str) -> None:
    with pytest.raises(InvalidChunk):
        normalize_chunk(
            {"source_type": source_type, "source_id": "x:1", "content": "nội dung"}
        )


def test_empty_content_is_rejected() -> None:
    with pytest.raises(InvalidChunk):
        normalize_chunk({"source_type": "web", "source_id": "page:x", "content": "   "})


def test_http_source_paginates_and_sends_the_api_key() -> None:
    seen_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        cursor = int(request.url.params["after_id"])
        if cursor == 0:
            return httpx.Response(
                200,
                json={
                    "chunks": [
                        {"id": 1, "source_type": "web", "source_id": "page:a", "content": "một", "metadata": {"part": 1}},
                        {"id": 2, "source_type": "web", "source_id": "page:b", "content": "hai", "metadata": {"part": 1}},
                    ],
                    "next_after_id": 2,
                },
            )
        return httpx.Response(
            200,
            json={
                "chunks": [
                    {"id": 3, "source_type": "post", "source_id": "post:c", "content": "ba", "metadata": {"part": 1}}
                ],
                "next_after_id": 3,
            },
        )

    source = HttpChunkSource(
        base_url="http://crawler.test",
        api_key="test-key",
        page_size=2,
        transport=httpx.MockTransport(handler),
    )
    records = list(source.iter_records())

    assert [record.source_id for record in records] == ["page:a", "page:b", "post:c"]
    assert len(seen_requests) == 2
    assert all(request.headers["X-API-Key"] == "test-key" for request in seen_requests)
    assert seen_requests[0].url.params.get_list("source_type") == ["post", "web"]


def test_http_source_refuses_to_run_without_a_key() -> None:
    source = HttpChunkSource(base_url="http://crawler.test", api_key="", transport=httpx.MockTransport(lambda r: httpx.Response(200)))

    with pytest.raises(Exception):
        list(source.iter_records())


def test_json_export_accepts_a_bare_list(tmp_path: Path) -> None:
    path = tmp_path / "chunks.json"
    path.write_text(
        json.dumps([{"source_type": "post", "source_id": "post:1", "content": "nội dung"}]),
        encoding="utf-8",
    )

    records = list(JsonFileSource(path).iter_records())

    assert len(records) == 1
    assert records[0].part == 1
