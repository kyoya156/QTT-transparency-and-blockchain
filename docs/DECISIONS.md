# Decisions

> **Direction change (Nov 2026):** the project is now financial transparency with
> ONE internal AI assistant (roles: admin, dev, finance, volunteer; unlabelled data
> is admin and dev only). The sponsor login, payment gateway and public 7-day
> anonymous log described below belong to the earlier public-chatbot design and are
> **superseded**. The embedding and retrieval decisions still apply.

Answers given on 6 Nov 2026, plus the engineering choices made while building M1.
Anything still marked **OPEN** blocks later milestones.

## Settled

- **Embeddings: local, free, Vietnamese-tuned** — `AITeamVN/Vietnamese_Embedding_v2`,
  1024 dims, fine-tuned from BGE-M3, Apache-2.0, CPU inference, no API key.
  Scores above base BGE-M3 on the Vietnamese benchmark (VN-MTEB). Kept behind
  `EMBED_MODEL`/`EMBED_DIM` so a swap is a config change plus a re-embed.
  torch stays out of `requirements.txt`; it lives in `requirements-embed.txt`.
- **LLM: owner already has a key.** Set `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`
  in `.env`. Key values never go into git, the repo, or this chat.
- **Database: Docker Compose, `pgvector/pgvector:pg17`, host port 5434.** Port
  5433 is already taken by the `qne-poc-db-1` container from the PoC; that
  container is left untouched.
- **Build order: M1 -> M5 as written in PLAN.md.**
- **Content for sync/eval: a JSON export from the crawler.** Until that export
  lands, `tests/fixtures/chunks_sample.json` (synthetic, clearly labelled) stands
  in so the pipeline can be tested.
- **Session/abuse: anonymous session cookie + in-memory rate limit** (M4).
- **Hand-off: stored in `handoffs` + an endpoint to list tickets.** Telegram/email
  notification is deliberately deferred; it must not be a hard dependency of the
  prototype.
- **Vietnamese copy: drafted by the agent, kept in one config file, reviewed by
  the owner.** No wording hard-coded inside logic.
- **Sync is a full snapshot** (the crawler's `document_chunks` has no
  created/updated column). Reconcile key `(source_type, source_id, part)`;
  `content_hash` covers content + url + title + source_date so metadata edits
  also re-sync; keys absent from the snapshot are deleted.
- **Privacy floor in code, not only in env**: `HARD_ALLOWED_SOURCE_TYPES =
  {web, post}`. `SYNC_SOURCE_TYPES` may narrow it, never widen it. A `message`
  row in an export fails the run instead of being indexed.
- **Citations stored as a snapshot** (`messages.evidence` JSONB), not as chunk
  ids: re-sync deletes chunks, and an answer must keep showing the source and
  date it was built on.

## New scope raised by the owner (not in PLAN.md v0.1)

Verbatim intent: chat history is saved only when the sponsor is logged in;
plain public questions about the fund and how it works are not stored;
questions that lead to actually creating a sponsorship are stored; once that
succeeds the user must sign in to see the next steps (payment and bank
transfer); after signing in, a sponsor (ACN) can see the information about the
child they sponsor (NE).

This is a different product from "public chatbot only": it needs accounts, a
sponsorship record, and a payment step. PLAN.md puts payment/donor verification
out of scope because it "needs Core DB API + donor verification".

**OPEN — blocking M4/M5 design:**

1. **Where is the crawler repo?** Needed for M0 (`GET /api/public/chunks`).
   It is outside this workspace, so it needs an explicit path from the owner.
2. **Login mechanism.** Own email+password, Google, Zalo/Facebook? A local
   account table is the least integration work; social login needs provider
   credentials.
3. **Source of NE / sponsorship data.** Which system knows that ACN X sponsors
   NE Y? If it is the Core DB, this repo needs a read-only API for it — the same
   pull contract as the crawler, not direct credentials.
4. **Payment step.** Bank transfer with a VietQR code and manual confirmation,
   or a gateway (VNPay/MoMo/OnePay)? Gateways need a merchant account and
   callback endpoint; manual transfer needs an admin confirmation flow.
5. **Retention.** The owner's rule implies two classes of data: nothing stored
   for anonymous informational questions, full history for logged-in sponsors.
   That changes `conversations` (nullable `user_id`) and needs a retention
   period for hand-off transcripts, which contain whatever the sponsor typed.

M1-M3 stay useful regardless: they are the answer engine and they do not depend
on accounts or payments.

## Second round of answers (6 Nov, later)

- **The crawler repo is not on this machine.** M0 therefore ships as
  `docs/CRAWLER_ENDPOINT.md` (contract + reference FastAPI router to merge) plus
  `mocks/crawler_stub.py`, a runnable stand-in that enforces the same 401/403
  boundary. The chatbot side is already tested against that contract, so merging
  the router is the only remaining step.
- **Login: phone or email + ACN/NE code.** The sponsor enters a phone number or
  email together with their ACN (sponsor) or NE (child) code; the system looks it
  up and signs them in. No password.
  Consequence to decide before M4: a short numeric code plus a known phone
  number is brute-forceable. Non-negotiable mitigations: rate limit + lockout per
  identifier and per IP, constant-time comparison, one generic error message so
  the endpoint cannot be used to enumerate valid codes, and codes of at least
  8 high-entropy characters - or an OTP step on top. **OPEN.**
- **NE/sponsorship data: Core DB read-only API planned, not built.** Mock it now
  behind the same pull-contract pattern as the crawler (own key, allowlist, no
  direct credentials), then swap the base URL.
- **Payment: a real gateway (VNPay/MoMo/OnePay), not manual transfer.** No
  Vietnamese gateway is self-serve: it needs a merchant contract, so no
  integration is written yet and none should be faked. The build will add a
  `payment_intents` table and one `PaymentProvider` seam. The organisers must
  supply: merchant account, terminal/partner code, hash secret, sandbox base URL,
  and the return + IPN callback URLs. Until then the payment step must render as
  "chưa kích hoạt", not as a fake success.
- **Anonymous questions: minimal telemetry for 7 days.** No session id, no IP;
  only question, intent, whether evidence was found, and the answer verdict.
  Auto-deleted after 7 days. Full history only for logged-in sponsors.
  **OPEN:** retention for hand-off transcripts, which contain whatever the
  sponsor typed.

## Engineering notes from the 11 Nov verification run

Found while running the pipeline end to end with the real model, and fixed:

- **FTS must OR the question's terms.** `plainto_tsquery` ANDs every word, so
  "học bổng được giải ngân khi nào" returned zero rows and the keyword half was
  dead on real input without any error. Now built with `to_tsquery`, letters and
  digits only (no operator can be injected), OR-ed.
- **Confidence comes from vector similarity only.** With OR-ed terms and the
  `simple` config (no IDF), `ts_rank` rated a nonsense question *higher* than a
  real one (0.0369 vs 0.0345). Cosine separated them: 0.461 vs 0.612. Default
  cutoff raised 0.45 -> 0.55 so the nonsense question is refused; keyword-only
  runs must clear 0.30 ts_rank and in practice will not be called confident.
- **The local model needs float16 on this machine.** Loading BGE-M3 in float32
  dies with `OSError: The paging file is too small` (14 GB RAM, ~1.3 GB free).
  `EMBED_DTYPE=float16` loads it at ~1.2 GB and embeds all 7 fixture chunks.
  On a server with 8 GB+ free this is unnecessary; keep float32 there.
- **CLIs must force UTF-8 stdout.** Windows consoles default to cp1252 and
  crashed printing any Vietnamese character; all three scripts reconfigure
  stdout/stderr now.
- **A page with no own date shows the crawl date, labelled as such.** The crawl
  date is deliberately outside the content hash, otherwise every nightly crawl
  would look like a change and re-embed the whole index.
