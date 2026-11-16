# M0: `GET /api/public/chunks` in the crawler repo

The crawler repo is not on this machine, so this is the contract plus a reference
implementation to drop in and adapt. `mocks/crawler_stub.py` implements the same
contract locally so the chatbot side can already be built and tested.

## Contract

```http
GET /api/public/chunks?source_type=web&source_type=post&after_id=0&limit=500
X-API-Key: <the chatbot's own key>
```

Rules:

1. **Server-side allowlist.** Only `web` and `post` may ever be returned, whatever
   the query says. Any other requested type is a `403`, never a filtered `200`:
   the caller must learn that the boundary exists.
2. **Separate key, separate router.** Never reuse the staff `/api/internal/*`
   key, and never let this router import staff-only queries.
3. **Read-only.** No writes from this endpoint.
4. **Stable ordering by `id` ascending.** `after_id` is strictly exclusive; the
   response carries `next_after_id` so the client never has to guess.
5. **No documents without a URL and a date** unless the crawler genuinely has
   none; the chatbot shows both, so missing values become "chưa xác định".

### Response

```json
{
  "chunks": [
    {
      "id": 101,
      "source_type": "web",
      "source_id": "page:gioi-thieu",
      "content": "...",
      "metadata": {
        "url": "https://...",
        "title": "Giới thiệu",
        "part": 1,
        "of": 2,
        "crawled_at": "2026-10-20T09:00:00Z"
      }
    }
  ],
  "next_after_id": 101,
  "limit": 500
}
```

`post` rows put `post_date` (YYYY-MM-DD) in `metadata`; `web` rows put
`crawled_at`. The client accepts either, flat or nested in `metadata`.

### Status codes

| Code | Meaning | The chatbot's reaction |
|---|---|---|
| 200 | page of chunks | index, follow `next_after_id` |
| 401 | missing/wrong `X-API-Key` | run fails, nothing is written |
| 403 | asked for a type outside `web|post` | run fails; contract bug |
| 5xx | crawler error | run fails, `sync_runs.error` records it |

## Reference implementation (FastAPI + SQLAlchemy)

Adapt table/column names to the crawler's schema; the shape is what matters.

```python
import os

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

PUBLIC_SOURCE_TYPES = frozenset({"web", "post"})
router = APIRouter(prefix="/api/public", tags=["public"])

CHUNKS_SQL = text(
    """
    SELECT
        id,
        source_type,
        source_id,
        content,
        COALESCE(metadata, '{}'::jsonb)
            || jsonb_strip_nulls(
                   jsonb_build_object(
                       'url', url,
                       'title', title,
                       'part', part,
                       'of', of,
                       'crawled_at', crawled_at,
                       'post_date', post_date
                   )
               ) AS metadata
    FROM document_chunks
    WHERE source_type = ANY(:source_types)
      AND id > :after_id
    ORDER BY id
    LIMIT :limit
    """
)


def require_chatbot_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = os.environ["CHATBOT_PUBLIC_CHUNKS_KEY"]
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="missing or invalid X-API-Key")


@router.get("/chunks", dependencies=[Depends(require_chatbot_key)])
def public_chunks(
    source_type: list[str] | None = Query(default=None),
    after_id: int = 0,
    limit: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    requested = {value.lower() for value in (source_type or PUBLIC_SOURCE_TYPES)}
    forbidden = requested - PUBLIC_SOURCE_TYPES
    if forbidden:
        raise HTTPException(
            status_code=403,
            detail=f"source_type not allowed: {sorted(forbidden)}",
        )

    rows = db.execute(
        CHUNKS_SQL,
        {
            "source_types": sorted(requested),
            "after_id": after_id,
            "limit": limit,
        },
    ).mappings().all()

    return {
        "chunks": [dict(row) for row in rows],
        "next_after_id": rows[-1]["id"] if rows else None,
        "limit": limit,
    }
```

Notes for the crawler side:

- Add `import secrets`; compare keys with `compare_digest`, not `==`.
- Store `CHATBOT_PUBLIC_CHUNKS_KEY` in `.env` / `.env.example` (blank value in the
  example file), never in git. Rotating it means updating the chatbot's
  `CRAWLER_API_KEY` too.
- Mount the router next to the existing app, e.g.
  `app.include_router(public_chunks_router)`.
- If `metadata` is already a JSONB column, use it directly; if the columns are
  named differently (`part_index`, `parts_total`, …), keep the contract keys and
  rename on the SQL side.

## Verify before handing over

```bash
curl -s -H "X-API-Key: $KEY" \
  'http://localhost:8000/api/public/chunks?source_type=web&source_type=post&limit=2'

curl -s -o /dev/null -w '%{http_code}\n' -H "X-API-Key: $KEY" \
  'http://localhost:8000/api/public/chunks?source_type=message'   # expect 403

curl -s -o /dev/null -w '%{http_code}\n' \
  'http://localhost:8000/api/public/chunks'                        # expect 401
```

Done (M0) when: `web`+`post` return rows, `message` returns **403**, a wrong key
returns **401**, and the same `curl` run twice returns identical `id` sets.

## Known gap worth fixing while you are in there

`document_chunks` has no created/updated timestamp, so the chatbot cannot sync
incrementally and does a full snapshot every night. Adding `updated_at` (touch on
re-crawl) would let both sides stop guessing and is the cheapest fix for the
"stale answer" risk in the plan.
