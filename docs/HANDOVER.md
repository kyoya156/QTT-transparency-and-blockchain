# Handover status — 11 Nov 2026

Read this before promising anything to the organisers. It separates what is
**verified by a run** from what is **written but never executed**, and from what
does **not exist yet**.

## Where the build actually stands

| Milestone | State | Evidence |
|---|---|---|
| M0 crawler endpoint | **not live**; contract + runnable stub | `docs/CRAWLER_ENDPOINT.md`, `mocks/crawler_stub.py`; 401/403/pagination covered by tests |
| M1 skeleton, Docker, schema, sync | **done** | sync inserts 7 chunks, re-run reports `+0 ~0 -0 =7`; `/healthz` returns the last run |
| M2 retrieval + `ask.py` | **done** | real model, 7 chunks embedded; a real question returns `page:hoc-bong` first at 0.612 cosine and is marked confident; a nonsense question is refused |
| M3 compose + citations + guardrails + hand-off | **not started** | no LLM call, no prompt, no citation check, no hand-off ticket creation |
| M4 `/chat` + chat page + log + feedback | **not started** | no API route, no page, no cookie session, no rate limit |
| M5 eval report, demo script | **blocked** | needs the real crawler export (the 7 chunks are synthetic placeholders) |

So: **the answer engine works; the chatbot does not exist yet.** There is no
endpoint a sponsor can talk to and no page to look at.

## What is proven, and how

```bash
.venv/Scripts/python.exe -m pytest -q               # whole suite
.venv/Scripts/python.exe scripts/sync_now.py --file tests/fixtures/chunks_sample.json
.venv/Scripts/python.exe scripts/embed_chunks.py    # needs requirements-embed.txt
.venv/Scripts/python.exe scripts/ask.py "Học bổng được giải ngân khi nào và bao nhiêu tiền?"
.venv/Scripts/python.exe scripts/ask.py "Quỹ có nhận nuôi mèo hoang không?"
```

Proven by those runs and the suite:

- sync is idempotent, updates in place, deletes what the crawler dropped, and a
  dry run writes nothing; a changed chunk loses its vector so it gets re-embedded;
- accent- and `đ`-insensitive keyword search (`co phan` finds `CỔ PHẦN`);
- vector ranking and RRF fusion (both lists' top hits survive);
- a question with no evidence is reported as not confident;
- the crawler contract's key check and `web|post` allowlist, including 403 for
  `message`;
- `/healthz` reports database state and the last sync run.

## Open risk: the confidence thresholds are calibrated on 7 synthetic chunks

The rule is "answer only if the best chunk's cosine ≥ 0.55". On the fixture a
real question scored 0.612 and a nonsense one 0.461, which is why 0.55 was
chosen — but that is two data points. **This number must be re-derived on the
real export with the eval set (30-40 questions, 10 unanswerable) before launch.**
Until then, treat the refusal behaviour as "plausible", not "measured".

## Blockers that are not ours to solve

1. **Real crawler export.** `tests/fixtures/chunks_sample.json` is synthetic;
   its URLs are `example.org`. Nothing about answer quality is known until the
   real 17 pages + posts are indexed.
2. **Merge the M0 router** into `QNE-knowledge-base`, give the chatbot its own
   key, and confirm `message` returns 403 there (the stub does, the real repo is
   not on this machine).
3. **LLM key** (`LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`) for M3. Without it,
   the bot cannot compose an answer — retrieval alone is not a chatbot.
4. **Auth/NE API** for the sponsor login (phone/email + ACN/NE code) and for
   "my sponsored child". Core DB's read-only API does not exist yet; it is
   mocked conceptually only.
5. **Payment merchant account** (VNPay/MoMo/OnePay) plus return and IPN URLs.
   No gateway can be integrated without it, and none should be faked.
6. **Machine for embeddings.** BGE-M3 in float32 dies here with
   `OSError: The paging file is too small` (14 GB RAM, ~1.3 GB free); it works
   at `EMBED_DTYPE=float16`. A server with 8 GB+ free does not need that. Plan
   CPU time for a full re-embed: the model loads in ~20 s and embeds roughly
   10-30 chunks/s at this size.

## What is missing before this can face a sponsor

Security and operations, all absent today:

- no rate limiting, no session cookie, no abuse handling (a public endpoint that
  calls an LLM is a cost and spam target from day one);
- no auth, no per-sponsor data isolation (nothing to isolate yet, but the schema
  change is not free);
- no retention job for the 7-day anonymous log, and no deletion path for
  hand-off transcripts;
- no migrations: schema changes use `create_all`, which never alters an existing
  table. The first real deployment needs Alembic or a documented `ALTER` path;
- no CI, no monitoring/alerting, no backup/restore drill for the Postgres volume;
- no admin/ops view for hand-off tickets (an endpoint is planned, not built);
- the crawler has no `updated_at`, so staleness is only visible through the date
  shown under each answer.

## Definition of done for a demo handover

- [ ] real export synced; chunk count and per-source counts recorded
- [ ] every chunk embedded; `SELECT count(*) FROM chunks WHERE embedding IS NULL` = 0
- [ ] eval set written, recall@5 and refusal rate reported on it
- [ ] `LLM_API_KEY` set, M3 compose + citation check wired, 5 attack prompts refused
- [ ] `/chat` behind a session cookie and a rate limit, page usable on a phone
- [ ] hand-off creates a ticket a volunteer can list and claim
- [ ] 7-day log purge scheduled and verified once
- [ ] Alembic (or a documented migration path) in place before the first real deploy

## Honest one-liner

The retrieval core is solid and tested; the privacy boundary is enforced in code
rather than promised; but this is roughly **40% of the product**, and the half
that a sponsor would actually touch — answer composition, chat page, login,
hand-off — has not been written.
