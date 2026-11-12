"""Reading chunks from the crawler.

Two sources implement the same contract:
  * HttpChunkSource  - GET /api/public/chunks (live, paginated by after_id)
  * JsonFileSource   - a dumped JSON export from the crawler, for offline work

Privacy: `web` and `post` are the only types this client will ever accept. A
wider crawler response, a stray `message` row in an export, or a widened env
setting cannot get past `effective_allowlist()`.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import httpx

from app.config import get_settings
from app.sync.reconcile import ChunkRecord, hash_chunk, normalize_part

HARD_ALLOWED_SOURCE_TYPES: frozenset[str] = frozenset({"web", "post"})
CHUNKS_PATH = "/api/public/chunks"


class ChunkSourceError(RuntimeError):
    """The source could not be read (network, bad payload, missing file)."""


class InvalidChunk(ValueError):
    """A single chunk is unusable or not allowed to be indexed."""


def effective_allowlist() -> frozenset[str]:
    """Env may narrow the allowlist, never widen it."""
    return get_settings().configured_source_types & HARD_ALLOWED_SOURCE_TYPES or HARD_ALLOWED_SOURCE_TYPES


class ChunkSource(Protocol):
    name: str

    def iter_records(self) -> Iterator[ChunkRecord]: ...


def _parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _pick(payload: dict[str, Any], metadata: dict[str, Any], *names: str) -> Any:
    """Read a field from the flat payload first, then from `metadata`."""
    for name in names:
        value = payload.get(name)
        if value not in (None, ""):
            return value
    for name in names:
        value = metadata.get(name)
        if value not in (None, ""):
            return value
    return None


def normalize_chunk(payload: dict[str, Any]) -> ChunkRecord:
    """Turn one crawler row into a ChunkRecord, or raise InvalidChunk."""
    if not isinstance(payload, dict):
        raise InvalidChunk(f"chunk must be an object, got {type(payload).__name__}")

    metadata = payload.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise InvalidChunk("chunk metadata must be an object")

    source_type = str(_pick(payload, metadata, "source_type") or "").strip().lower()
    if source_type not in HARD_ALLOWED_SOURCE_TYPES:
        raise InvalidChunk(
            f"source_type {source_type!r} is not allowed; only {sorted(HARD_ALLOWED_SOURCE_TYPES)} may be indexed"
        )
    if source_type not in effective_allowlist():
        raise InvalidChunk(f"source_type {source_type!r} is disabled by SYNC_SOURCE_TYPES")

    source_id = _pick(payload, metadata, "source_id")
    if source_id in (None, ""):
        raise InvalidChunk("chunk is missing source_id")

    content = str(_pick(payload, metadata, "content") or "").strip()
    if not content:
        raise InvalidChunk(f"chunk {source_type}:{source_id} has empty content")

    url = _pick(payload, metadata, "url")
    title = _pick(payload, metadata, "title")
    source_date = _parse_date(
        _pick(payload, metadata, "source_date", "post_date", "published_at", "date")
    )
    crawled_at = _parse_datetime(_pick(payload, metadata, "crawled_at", "crawled"))
    src_id = _pick(payload, metadata, "id")

    return ChunkRecord(
        source_type=source_type,
        source_id=str(source_id),
        part=normalize_part(_pick(payload, metadata, "part")),
        of=(int(_pick(payload, metadata, "of")) if _pick(payload, metadata, "of") else None),
        content=content,
        content_hash=hash_chunk(content, str(url) if url else None, str(title) if title else None, source_date),
        src_id=str(src_id) if src_id is not None else None,
        url=str(url) if url else None,
        title=str(title) if title else None,
        source_date=source_date,
        crawled_at=crawled_at,
    )


def _extract_items(body: Any) -> list[dict[str, Any]]:
    if isinstance(body, list):
        return [item for item in body if isinstance(item, dict)]
    if isinstance(body, dict):
        for key in ("chunks", "data", "items", "results"):
            value = body.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise ChunkSourceError("unexpected chunks payload shape (expected a list or a dict with chunks/data/items/results)")


class JsonFileSource:
    """Reads a crawler export: a bare list, or {"chunks": [...]}."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self.name = f"file:{self._path}"

    def iter_records(self) -> Iterator[ChunkRecord]:
        if not self._path.exists():
            raise ChunkSourceError(
                f"chunk export not found: {self._path} (export it from the crawler, or set SYNC_FILE)"
            )
        try:
            body = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ChunkSourceError(f"{self._path} is not valid JSON: {exc}") from exc

        items = _extract_items(body)
        for index, item in enumerate(items):
            try:
                yield normalize_chunk(item)
            except InvalidChunk as exc:
                raise InvalidChunk(f"{self._path} item {index}: {exc}") from exc


class HttpChunkSource:
    """Live crawler endpoint, paginated by after_id."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        page_size: int | None = None,
        timeout_s: float | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        self._base_url = (base_url or settings.crawler_base_url).rstrip("/")
        self._api_key = api_key if api_key is not None else settings.crawler_api_key
        self._page_size = page_size or settings.crawler_page_size
        self._timeout_s = timeout_s or settings.crawler_timeout_s
        self._transport = transport
        self.name = f"http:{self._base_url}{CHUNKS_PATH}"

    def _params(self, after_id: int) -> list[tuple[str, str | int]]:
        params: list[tuple[str, str | int]] = [
            ("source_type", source_type) for source_type in sorted(effective_allowlist())
        ]
        params.append(("after_id", after_id))
        params.append(("limit", self._page_size))
        return params

    def iter_records(self) -> Iterator[ChunkRecord]:
        if not self._api_key:
            raise ChunkSourceError("CRAWLER_API_KEY is empty; the endpoint requires it")

        cursor = 0
        with httpx.Client(
            base_url=self._base_url,
            headers={"X-API-Key": self._api_key},
            timeout=self._timeout_s,
            transport=self._transport,
        ) as client:
            while True:
                try:
                    response = client.get(CHUNKS_PATH, params=self._params(cursor))
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raise ChunkSourceError(
                        f"crawler returned {exc.response.status_code} for {CHUNKS_PATH}: {exc.response.text[:300]}"
                    ) from exc
                except httpx.HTTPError as exc:
                    raise ChunkSourceError(f"cannot reach crawler at {self._base_url}: {exc}") from exc

                body = response.json()
                items = _extract_items(body)
                if not items:
                    return

                for item in items:
                    try:
                        yield normalize_chunk(item)
                    except InvalidChunk as exc:
                        raise InvalidChunk(f"crawler item id={item.get('id')!r}: {exc}") from exc

                next_cursor = body.get("next_after_id") if isinstance(body, dict) else None
                if next_cursor in (None, ""):
                    ids = [item.get("id") for item in items]
                    if not all(isinstance(value, int) for value in ids):
                        return
                    next_cursor = max(ids)
                next_cursor = int(next_cursor)
                if next_cursor <= cursor:
                    return  # guard against a server that repeats the same page
                cursor = next_cursor
                if len(items) < self._page_size:
                    return
