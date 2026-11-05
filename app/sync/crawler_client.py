"""Keo chunk cong khai tu crawler qua /api/public/chunks (phan trang theo id)."""
import httpx

from ..config import settings

# Chi nhan 2 loai nay, du server tra gi (phong thu 2 lop: server cung da loc).
ALLOWED_TYPES = ("web", "post")


class CrawlerError(RuntimeError):
    pass


def fetch_all(base_url: str | None = None, api_key: str | None = None, page_size: int | None = None,
              timeout: float | None = None, transport: httpx.BaseTransport | None = None) -> list[dict]:
    """Tra ve toan bo chunk web+post. Loi bat ky o giua chung -> CrawlerError (khong tra ket qua dang do)."""
    base = (base_url or settings.crawler_url).rstrip("/")
    key = api_key if api_key is not None else settings.crawler_api_key
    if not key:
        raise CrawlerError("CRAWLER_API_KEY chua dat trong .env")
    size = page_size or settings.sync_page_size
    items: list[dict] = []
    after = 0
    try:
        with httpx.Client(timeout=timeout or settings.sync_timeout, transport=transport) as client:
            while True:
                r = client.get(f"{base}/api/public/chunks", headers={"X-API-Key": key},
                               params=[("source_type", t) for t in ALLOWED_TYPES]
                               + [("after_id", after), ("limit", size)])
                if r.status_code == 401:
                    raise CrawlerError("crawler tu choi khoa API (401): kiem tra CRAWLER_API_KEY")
                if r.status_code == 503:
                    raise CrawlerError("crawler chua bat API cong khai: dat PUBLIC_API_KEY ben crawler")
                if r.status_code != 200:
                    raise CrawlerError(f"crawler tra {r.status_code}: {r.text[:200]}")
                data = r.json()
                items.extend(data.get("items", []))
                after = data.get("next_after_id")
                if after is None:
                    return items
    except httpx.HTTPError as e:
        raise CrawlerError(f"khong goi duoc crawler ({base}): {e}") from e
