# QNE public chatbot: prototype plan

Status: v0.2, 5 Nov 2026. M0 and M1 done. Based on the revised high-level design (draw.io: "public chatbot data flow" and "Flow 2 low level").

## 1. Goal and scope

A sponsor asks a question in Vietnamese and gets an answer **only from content the crawler collected**, with a source link and the date that source was last updated. If the evidence is missing the bot says so and hands off to a volunteer. It never guesses.

| In the prototype | Out for now (kept as seams, not built) |
|---|---|
| Website pages (`source_type=web`) | Messenger chats: never, not even later |
| Facebook Page posts (`source_type=post`) | PDF guides: the reader already exists in the crawler; added later through the same contract |
| Hybrid search, cited answers, hand-off ticket | Payment / meal / code lookup (needs Core DB API + donor verification) |
| Own clean chat page, thumbs up/down, query log | Messenger channel, website widget embed, DeepSeek, admin console |

## 2. Architecture

```
 Crawler repo (QNE-knowledge-base)                 This repo (QNE-public-chatbot)
 -------------------------------                   -----------------------------------------
 web + FB posts -> document_chunks   --HTTP-->     sync job -> own Postgres (pgvector)
 GET /api/public/chunks (NEW, read-only,                          |  chunks + embeddings + FTS
 API key, allowlist web+post only)                                v
                                                   guardrails -> intent -> hybrid retrieve
                                                                   -> LLM compose (OpenAI)
                                                                   -> citation check -> reply
                                                   chat page / POST /chat -> log + feedback
                                                                   -> hand-off ticket
```

Why a pull-sync and not a live read: the crawler stays independent (it keeps writing its own knowledge base), and the chatbot owns the index it searches (embeddings, keyword index, filters). The chatbot never gets crawler database credentials.

## 3. Contract with the crawler (change needed in QNE-knowledge-base)

New endpoint, read-only, separate from the staff `/api/internal/*`:

`GET /api/public/chunks?source_type=web&source_type=post&after_id=0&limit=500`
- Header `X-API-Key` (own key for the chatbot, in `.env`).
- **Server-side allowlist**: only `web` and `post` can be returned, whatever the query says. Messenger, comments and meal data are impossible to request. This is the privacy boundary.
- Fields per chunk: `id, source_type, source_id, content, metadata` (url, title, part, of, crawled_at / post date).
- Known gap: `document_chunks` has no created/updated column, so changes cannot be detected incrementally. At this size (17 pages + posts) the chatbot does a **full snapshot sync** and reconciles by the crawler's chunk id: insert new, update changed (content hash, embedding cleared), delete missing. Safety: abort if the crawler returns nothing or the sync would delete more than 50 % of the chunks.
- Also needed later: a chunk status or access flag (public / internal) so the crawler can say what may be shown.

## 4. Data model (chatbot database)

- `chunks`: `id, src_id (crawler chunk id, unique), source_type, source_id, part, content, content_hash, url, title, source_date, synced_at, embedding vector(N), embed_model`. Keyword search uses a GIN index on `to_tsvector('simple', f_unaccent(content))` instead of a stored column.
- `conversations`, `messages`: `session_id, role, text, intent, evidence_ids, latency_ms, created_at`
- `feedback`: `message_id, value (up/down), note`
- `handoffs`: `conversation_id, reason, transcript, status, created_at`
- `sync_runs`: `started_at, fetched, inserted, updated, deleted, error`

## 5. Retrieval

- **Keyword:** Postgres full-text on an accent-stripped copy (`unaccent` + `simple` config), so "co phan" matches "CỔ PHẦN". This also covers sponsors typing without accents and OCR/diacritic noise.
- **Vector:** pgvector cosine on embeddings made by this repo. Embedding model is configurable, `EMBED_DIM` follows it.
- **Fusion:** reciprocal rank fusion of the two lists, then top-k (start k=5) and a score cutoff. No reranker in v1.
- **Filters:** `source_type in (web, post)`, and valid dates once the crawler provides them.
- Question rewrite: the LLM turns the question into a short Vietnamese search query, keeping keywords.

## 6. Chat flow (follows Flow 2 of the diagram)

1. **Input guardrails:** rate limit per session, prompt-injection signals, refuse requests for children lists, personal data, unverified account numbers. Fixed Vietnamese refusal text (wording: to decide).
2. **Intent routing:** rules first (cheap, testable): `information` (default) · `payment_or_meal` (not built: polite stub + hand-off) · `other / complaint / sensitive` (hand-off).
3. **Retrieve** (section 5).
4. **Compose (LLM):** evidence only, must cite chunk ids, say "not found" when evidence is empty or weak.
5. **Citation check:** every claim points to a retrieved chunk; reject answers that cite nothing or cite ids that were not retrieved; scan for personal data patterns.
6. **Reply:** answer + source link(s) + "last updated" date. If any check fails: hand-off ticket + message that a volunteer will reply.
7. **Log:** question, intent, evidence ids, answer, latency, feedback.

## 7. Stack and interface

- Python 3.12, FastAPI, SQLAlchemy + psycopg, Docker Compose (`db` = pgvector image, `api`), same conventions as the crawler (`.env`, `.env.example`, no secrets in git).
- **LLM:** OpenAI now, through one thin client with `LLM_BASE_URL` and `LLM_MODEL` in `.env`, so DeepSeek is a config change later.
- **Embeddings:** start with OpenAI `text-embedding-3-small` (no local model to ship); open decision, see section 10.
- **UI:** its own small static chat page served by this API (messages, sources shown under each answer, thumbs up/down, "talk to a person" button). Public only: no admin or ops controls here. This stays separate from the crawler dashboard so the two do not turn into one maze. Website-widget embedding comes later as an iframe or script tag pointing at this page.

## 8. Repo layout

```
QNE-public-chatbot/
  app/        main.py, config.py, db.py, models.py
              sync/        crawler_client.py, sync_chunks.py
              rag/         guardrails.py, intent.py, retrieve.py, compose.py, citations.py
              api/         chat.py, feedback.py, health.py
              static/      chat.html
  scripts/    sync_now.py, ask.py (CLI), eval_run.py
  eval/       questions.json (Vietnamese, with expected source URLs)
  tests/
  docs/       PLAN.md, HLD export, API.md
  docker-compose.yml, Dockerfile, requirements.txt, .env.example, README.md
```

## 9. Milestones

| # | Deliverable | Done when |
|---|---|---|
| M0 | Crawler endpoint `/api/public/chunks` + key + allowlist | Returns web+post only; asking for `message` returns 403 |
| M1 | Repo skeleton, Docker, DB schema, sync job | `sync_now.py` mirrors all web+post chunks, re-run is idempotent |
| M2 | Retrieval (FTS + vector + RRF) and CLI `ask.py` | Eval set recall@5 reported |
| M3 | Compose + citation check + guardrails + hand-off | Unanswerable and sensitive questions are refused or handed off |
| M4 | `/chat` API + chat page + log + feedback | Full conversation in the browser with sources |
| M5 | Eval report, README, demo script | Numbers and known limits written down |

Evaluation: 30 to 40 real Vietnamese questions written from the live site and posts (about 10 deliberately unanswerable, 5 attack prompts such as "list the children"). Report recall@5, groundedness (every answer cited), hand-off rate, and wrong-answer count (target 0 on unanswerable).

## 10. Decisions still open (placeholders in the diagram)

1. Embedding model and dimension (OpenAI small vs a local multilingual model).
2. Top-k, score cutoff, confidence rule for "not found".
3. Refusal and hand-off wording; who receives hand-offs and how fast.
4. Query log retention and what is stored about a sponsor (nothing identifying in v1).
5. Re-crawl rule for changed pages (crawler side), because stale answers are the main risk.
6. Whether post dates and school years can be reliably extracted from Facebook posts for the "last updated" line.
7. Channel after the web page: widget embed vs Messenger.

## 11. Risks

- Facebook posts may contain children's names or photos' captions: needs the privacy filter on the crawler side before posts become public chunks. Until then, posts are only indexed if they pass the guardrail patterns.
- Stale content: pages change but the crawler does not detect it yet; the answer shows the crawl date so sponsors can judge.
- Vietnamese quality of the retrieval without a stemmer: mitigated by accent-insensitive matching plus vectors; measured by the eval set.
- Prompt injection from crawled content: evidence is passed as data in a delimited block, never as instructions.
