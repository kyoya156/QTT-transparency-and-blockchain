# QNE public chatbot

Chatbot for sponsors of Quỹ Nuôi Em. It answers **only from content the crawler collected** (website pages and Facebook Page posts), cites its sources and hands off to a volunteer when it does not know. Plan: [`docs/PLAN.md`](docs/PLAN.md).

Status: **M1** (skeleton, schema, sync from the crawler). Search, answers and the chat page come in M2 to M4.

## How it fits with the crawler

```
QNE-knowledge-base (crawler)  --GET /api/public/chunks-->  this repo (own Postgres + pgvector)
```

The crawler stays independent. This repo pulls a copy of the public chunks (web + Page posts only; the crawler enforces that) and owns its own index. It never gets crawler database credentials.

## Run

1. In the **crawler** repo `.env`, set `PUBLIC_API_KEY=<a long random key>` and restart its API (`docker compose restart api`). The crawler must be on branch `feat/public-chunks` or later.
2. Here: `copy .env.example .env`, set `POSTGRES_PASSWORD` (also inside both DB URLs) and `CRAWLER_API_KEY` (same value as the crawler's `PUBLIC_API_KEY`).
3. `docker compose up -d --build`
4. Pull the content: `docker compose exec api python -m scripts.sync_now`
5. Check: `http://localhost:8100/health` shows chunk counts per source type and the last sync.

Ports: api 8100, db 5434 (the crawler uses 8000 and 5433). Docker Desktop reaches the crawler at `host.docker.internal:8000`.

## Sync rules

- Key = the crawler's chunk id. New → insert, changed text → update and clear the embedding (re-embedded later), gone from the crawler → delete.
- Safety: the sync aborts without deleting anything if the crawler returns nothing while the database has data, or if it would delete more than 50 % of the chunks. `--allow-empty` overrides it.
- Anything that is not `web` or `post` is rejected on this side as well.

## Tests

```
pip install -r requirements.txt
python -m pytest -q tests        # 12 tests, SQLite stand-in, no network
```
