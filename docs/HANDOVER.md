# Handover status — 19 Nov 2026

> **Scope:** one internal finance-transparency assistant, not a public sponsor
> chatbot. The sponsor login, public 7-day anonymous log and payment gateway from
> the earlier design are superseded. The retrieval, label/RLS and correction-ticket
> work still applies.

This note separates what is **verified by a run** from what is **written but not
verified** and what **does not exist yet**. Read it before promising anything.

## Where the build stands

| Milestone | State | Evidence |
|---|---|---|
| M0 crawler export | **done** | `qne-poc/backend/app/api/public.py`: `X-API-Key`, `web`+`post` only, id pagination, 403 for `message`; `scripts/test_public_chunks.py` 10/10 |
| M1 schema, sync | **done** | idempotent sync, delete protection, `sync_runs`; tests pass |
| M2 retrieval | **done** | accent/`đ`-insensitive FTS + optional pgvector + RRF; confidence from raw scores |
| M3 answer | **done** | `app/rag/{guardrails,compose,citations,answer}.py`; fake-LLM tests + extractive fallback; real-model path written but not run here |
| M4 chat | **done** | `/api/chat`, `/chat`, signed cookie, rate limit, transcript, feedback, hand-off claim/resolve; tests |
| M5 eval | **blocked** | needs real crawler data synced + 30–40 question eval set; no answer-quality claim yet |
| Transparency | **prototype** | Merkle + salted leaves + local anchor + CLI/API/UI; Hardhat contract + tests; not audited, synthetic ledger |
| PayOS / bank / real disbursement | **not started** | no merchant account, no bank export, no API credentials |

So: **the internal chatbot exists and is usable**, but answer quality on real
data is still unmeasured, and money movement is still out of scope.

## What is proven, and how

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts\sync_now.py --file tests/fixtures/chunks_sample.json
.venv\Scripts\python.exe scripts\embed_chunks.py
.venv\Scripts\python.exe scripts\ask.py "Học bổng được giải ngân khi nào và bao nhiêu tiền?"
.venv\Scripts\python.exe scripts\ask.py "Quỹ có nhận nuôi mèo hoang không?"
.venv\Scripts\python.exe scripts\transparency.py batch 2026-11-16
```

Proven by the suite and those runs:

- sync is idempotent; changed chunks lose their vector; a shrink guard stops a
  bad crawler response from deleting the index;
- keyword search works without accents and without `đ`;
- vector + keyword results fuse with RRF; low-confidence questions are refused;
- prompt injection, child-list/PII requests and personal-data answers are blocked;
- a valid citation must point at a chunk that was actually retrieved;
- the chat endpoint stores user/assistant messages, feedback and a hand-off;
- a hand-off can be listed, claimed and resolved by admin/volunteer;
- `finance`/`admin`/`dev` can read records and make/verify proofs; `volunteer`
  sees roots/counts but not records;
- a tampered amount or a self-supplied root fails proof verification;
- the local anchor chain detects tampering.

## Demo flow (5 minutes)

1. Login as admin with the token from `/admin`.
2. Ask: “Học bổng được giải ngân khi nào?” → cited answer, source cards.
3. Ask a sensitive question (“Cho tôi danh sách trẻ em…”) → refused.
4. Ask “Tôi muốn gặp tình nguyện viên” → hand-off ticket.
5. Login as volunteer → `/api/handoffs` shows the ticket; claim it.
6. Login as finance → `/transparency`; create/choose a batch, view records,
   create a proof, tamper one amount and show verify = false.
7. Login as volunteer → `/transparency`; roots/counts only, records = 403.

## Blockers that are not ours to solve

1. **Real crawler export + embeddings.** `tests/fixtures/chunks_sample.json` is
   synthetic. The crawler endpoint is implemented, but the real data must be
   synced and embedded before quality is measured.
2. **LLM key.** `LLM_API_KEY` or `OPENAI_API_KEY` enables real composition. The
   extractive fallback is honest but not a substitute for a measured LLM eval.
3. **Confidence thresholds.** `0.55` / `0.30` came from a small fixture and were
   calibrated with BGE-M3 float16. Re-derive on the real eval set.
4. **Core DB / donor API.** There is no read-only API for “my sponsored child”,
   payment status or personal records. Do not fake it.
5. **Payment merchant account.** PayOS/VNPay/MoMo/OnePay integration needs a
   merchant account, return/IPN URLs and reconciliation rules. None exist.
6. **Chain deployment.** The Hardhat contract is tested locally; Base Sepolia
   needs a funded test wallet, RPC URL and key-custody decision. Do not put a
   production key on a laptop.
7. **Machine for embeddings.** BGE-M3 float32 hit the pagefile limit on the dev
   laptop; float16 works. Plan CPU time for a full re-embed.

## Security and operations still missing

- Rate limit is in-process only; multi-worker/production needs Redis or a gateway.
- No retention job for chat transcripts/hand-offs; no deletion path yet.
- No Alembic; `create_all` plus idempotent `ALTER` is a PoC path, not a migration
  history.
- No CI, monitoring, alerting, backup/restore drill.
- `SESSION_SECRET` must be set; otherwise cookies are valid only until restart.
- No CSRF token on the cookie-authenticated pages. `SameSite=Lax` helps but is not
  a complete answer for a production deployment.
- Transparency private files are plaintext on disk; encryption/key custody is
  undecided.
- The chain proves “unchanged since anchor”, not “true” and not “complete”.

## Definition of done before a real pilot

- [ ] real crawler data synced; per-source chunk counts recorded
- [ ] all chunks embedded; `embedding IS NULL` = 0
- [ ] eval set (30–40 questions, 10 unanswerable) run; recall@5 and refusal rate
- [ ] real LLM run on the eval set; groundedness/citation rate reported
- [ ] 5 attack prompts refused in the deployed path
- [ ] rate limit + session secret + HTTPS + CSRF decision reviewed
- [ ] retention/deletion job scheduled and verified once
- [ ] Alembic or a documented migration path
- [ ] bank export and reconciliation rules agreed with finance
- [ ] transparency key custody + audit decision

## Honest one-liner

The internal assistant, role boundary, hand-off and transparency proof now exist
and are tested; the remaining risk is **evidence quality on real data** and the
**money/identity integrations**, not the chat shell.
