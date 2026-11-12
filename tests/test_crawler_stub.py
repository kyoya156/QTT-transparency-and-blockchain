"""The local stub must enforce the same boundary the real crawler endpoint will."""

from __future__ import annotations

from fastapi.testclient import TestClient

from mocks.crawler_stub import app

KEY = "dev-local-key"
client = TestClient(app)

ENDPOINT = "/api/public/chunks"


def test_missing_key_is_401() -> None:
    assert client.get(ENDPOINT).status_code == 401


def test_wrong_key_is_401() -> None:
    assert client.get(ENDPOINT, headers={"X-API-Key": "nope"}).status_code == 401


def test_message_source_type_is_403_not_an_empty_200() -> None:
    response = client.get(
        ENDPOINT,
        params=[("source_type", "message")],
        headers={"X-API-Key": KEY},
    )

    assert response.status_code == 403
    assert "not allowed" in response.json()["error"]


def test_pages_are_ordered_and_cursor_is_exclusive() -> None:
    first = client.get(
        ENDPOINT,
        params=[("source_type", "web"), ("source_type", "post"), ("limit", 3)],
        headers={"X-API-Key": KEY},
    ).json()

    assert [row["id"] for row in first["chunks"]] == [101, 102, 103]
    assert first["next_after_id"] == 103

    second = client.get(
        ENDPOINT,
        params=[
            ("source_type", "web"),
            ("source_type", "post"),
            ("limit", 3),
            ("after_id", first["next_after_id"]),
        ],
        headers={"X-API-Key": KEY},
    ).json()

    assert [row["id"] for row in second["chunks"]] == [104, 105, 201]


def test_source_type_filter_excludes_posts() -> None:
    body = client.get(
        ENDPOINT,
        params=[("source_type", "web"), ("limit", 100)],
        headers={"X-API-Key": KEY},
    ).json()

    assert body["chunks"]
    assert {row["source_type"] for row in body["chunks"]} == {"web"}
