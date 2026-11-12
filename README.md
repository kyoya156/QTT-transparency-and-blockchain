# QNE public chatbot

A sponsor asks a question in Vietnamese and gets an answer **only from content the
crawler collected**, with a source link and the date that source was last updated.
If the evidence is missing, the bot says so and hands off to a volunteer. It never
guesses.

Plan and scope: [`docs/PLAN.md`](docs/PLAN.md). Decisions and open questions:
[`docs/DECISIONS.md`](docs/DECISIONS.md). Crawler-side contract:
[`docs/CRAWLER_ENDPOINT.md`](docs/CRAWLER_ENDPOINT.md).

## Status

| Milestone | State |
|---|---|
| M0 crawler endpoint `/api/public/chunks` | contract + reference router written; **needs merging into QNE-knowledge-base** |
| M1 skeleton, Docker, DB schema, sync job | **done, verified** |
| M2 retrieval (FTS + vector + RRF), `ask.py` | **done, verified** |
| M3 compose + citation check + guardrails + hand-off | not started |
| M4 `/chat` API + chat page + log + feedback | not started |
| M5 eval report, README, demo script | eval harness needs the real export |

## Quickstart

```bash
cp .env.example .env          # edit CRAWLER_API_KEY etc.

docker compose up -d --wait db # Postgres 17 + pgvector on localhost:5434

uv venv .venv
uv pip install --python .venv/Scripts/python.exe -r requirements-dev.txt
uv pip install --python .venv/Scripts/python.exe -r requirements-embed.txt   # torch, ~2 GB

.venv/Scripts/python.exe scripts/sync_now.py --init --file data/chunks.json
.venv/Scripts/python.exe scripts/embed_chunks.py

.venv/Scripts/python.exe -m uvicorn app.main:app --port 8080 --reload
curl http://localhost:8080/healthz
```

On macOS/Linux use `.venv/bin/python`. The database is published on **5434**
because an existing PoC Postgres owns 5433.

To try it without any real data yet:

```bash
.venv/Scripts/python.exe scripts/sync_now.py --init --file tests/fixtures/chunks_sample.json
.venv/Scripts/python.exe scripts/embed_chunks.py
.venv/Scripts/python.exe scripts/ask.py "Học bổng mỗi tháng bao nhiêu?"
```

## Syncing content

Two sources implement the same contract:

```bash
# offline: a JSON export from the crawler (a list, or {"chunks": [...]})
scripts/sync_now.py --file data/chunks.json

# live: GET /api/public/chunks, paginated by after_id, header X-API-Key
scripts/sync_now.py --source http --dry-run
scripts/sync_now.py --source http --embed      # sync then embed in one go
```

The sync is a **full snapshot**: it inserts new chunks, updates the ones whose
hash changed, deletes the ones the crawler no longer returns, and leaves the rest
alone. Running it twice with the same data is a no-op. Every run is recorded in
`sync_runs` and surfaced by `/healthz`.

The hash covers content **and** url/title/source_date, so fixing a page title or
publishing date also triggers a re-sync — but **not** `crawled_at`, which changes
on every crawl; hashing it would mark everything modified every night.

`web` and `post` are the only source types the client will accept. That floor is
hard-coded: `SYNC_SOURCE_TYPES` can narrow it, never widen it, and a stray
`message` row inside an export fails the whole sync instead of being indexed.

## Working without the crawler repo

`mocks/crawler_stub.py` serves the real contract from a JSON file, including the
401 and 403 behaviour:

```bash
.venv/Scripts/python.exe -m uvicorn mocks.crawler_stub:app --port 8001
# in another shell:
CRAWLER_BASE_URL=http://localhost:8001 scripts/sync_now.py --source http --dry-run
```

The router to merge into `QNE-knowledge-base` is in `docs/CRAWLER_ENDPOINT.md`.

## Retrieval

`app/rag/retrieve.py` runs both searches and fuses them:

- **Keyword:** Postgres full-text on a stored generated `tsv` built from an
  `IMMUTABLE` wrapper around `unaccent` (Postgres' `unaccent` is `STABLE` and
  cannot be indexed directly). The wrapper also folds `đ` to `d`, so `co phan`
  matches `CỔ PHẦN` and `hoc bong` matches `HỌC BỔNG`. The question's words are
  **OR**-ed, not AND-ed: `plainto_tsquery` requires every word, so a normal
  question like "học bổng được giải ngân khi nào" matched nothing and the
  keyword side silently died on real input.
- **Vector:** pgvector cosine over `AITeamVN/Vietnamese_Embedding_v2`
  (1024 dims, fine-tuned from BGE-M3 for Vietnamese, Apache-2.0, CPU, free).
  Vectors are L2-normalised, so cosine is a dot product.
- **Fusion:** reciprocal rank fusion with `RRF_K`, taking `RETRIEVAL_POOL` from
  each list before cutting to `RETRIEVAL_K`.
- **Confidence:** computed from the *raw* signals, never from the RRF score,
  which only encodes ranks and cannot answer "is there enough evidence to answer
  at all". This is the hook M3 uses to say "không tìm thấy" and hand off.
  Vector similarity is the real signal: measured on the fixture, a real question
  scored 0.612 while a nonsense one scored 0.461 (hence the 0.55 cutoff), and
  `ts_rank` inverted them (0.0345 vs 0.0369) because `simple` has no IDF and the
  words are OR-ed. A keyword-only result therefore needs 0.30+ ts_rank before it
  may claim confidence, which normal questions will not reach — by design.

```bash
scripts/ask.py "học bổng bao nhiêu một tháng"        # full hybrid search
scripts/ask.py "hoc bong" --no-embed --json           # keyword only, no torch
```

## Schema

`chunks` holds the index this repo owns: content, `content_hash`, url/title,
`source_date`, `crawled_at`, `embedding vector(1024)` and the generated `tsv`.
`display_date` is a property, not a column: it is `source_date`, else the crawl
date, and it is what the answer labels "cập nhật lần cuối".

Also created now, filled later: `conversations`, `messages`, `feedback`,
`handoffs`, `sync_runs`.

`messages.evidence` is a JSON snapshot of the citations (`chunk_id, url, title,
source_date, crawled_at, display_date`) rather than a list of ids: a re-sync
deletes chunks, and an old answer must still show the source it was based on.

Schema changes use `Base.metadata.create_all` for now (an existing table is not
altered). Re-run `scripts/sync_now.py --init` after adding tables; column changes
need a manual `ALTER` or a fresh volume during the prototype.

## Tests

```bash
.venv/Scripts/python.exe -m pytest -q                  # 39 tests, offline + integration
.venv/Scripts/python.exe -m pytest -m integration -q    # needs the db container
```

Proven by the suite: idempotent re-run, in-place update on edited content,
deletion of dropped content, dry run writing nothing, embedding invalidated on
content change, accent-insensitive matching, vector ranking, RRF fusion surfacing
both lists' top hits, unanswerable questions producing no evidence, and the
crawler contract's 401/403 boundary.

## Layout

```
app/            main.py, config.py, db.py, models.py
app/sync/       reconcile.py (pure diff), crawler_client.py, sync_chunks.py, embed_chunks.py
app/rag/        embeddings.py (providers), retrieve.py (FTS + vector + RRF)
app/api/        health.py
mocks/          crawler_stub.py (stand-in for the crawler endpoint)
scripts/        sync_now.py, embed_chunks.py, ask.py
tests/          unit + integration, fixtures/chunks_sample.json (synthetic)
docs/           PLAN.md, DECISIONS.md, CRAWLER_ENDPOINT.md
```

## Configuration

See `.env.example`. `EMBED_DIM` must match the model: changing it requires
recreating the `chunks.embedding` column and re-embedding everything.
`EMBED_PROVIDER=none` disables the vector side, leaving keyword-only search.
