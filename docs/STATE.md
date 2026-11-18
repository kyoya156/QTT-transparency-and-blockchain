# Project state (living file)

Last updated: 2026-11-18 by Claude Code session. Newest facts win. Keep this short; move old detail to the log.

## Update protocol (every agent, end of every session)
1. Update "Now", "Done", "Next" and "Decisions" so a cold reader is current.
2. Add one line at the top of the Log: `date | agent | what changed | files`.
3. Record anything you could not verify as UNVERIFIED, with the check that would settle it.
4. Commit this file with your work. Never put keys or secrets here.

## Now
Client decision (2026-11-18): hash everything on chain; readable records only through the app's department permissions. Contract v3 (hash only) written and tested on `verify-endpoint`, NOT deployed yet. Until it is, the Python side (ABI v3) cannot talk to the live v2 contract: the live verify endpoint is broken until v3 is deployed.
Team docs for everyone: `reminder.md` (who does what), this file, `AGENTS.md`. All on `main`.

## Branches
| Branch | State |
|---|---|
| `main` | a1288ff: contract v2, Python bridge, record fields, hygiene pass. Start new work from here |
| `verify-endpoint` | from `main`; verify endpoint done, awaiting review/merge |
| `m3-answer` | chatbot answer flow, fake-LLM tests only. Parked |
| `vh-branch` | inside `main`; already deleted on GitHub (found gone 2026-11-18) |

## Done
- `TransparencyLedger` v3 (hash only, on `verify-endpoint`): `record(refId, leaf)`, `anchorBatch(uint32 yyyymmdd, root, count)`, `verify`, pause; `entries(refId)` = (leaf, recordedAt) only; writes need `RECORDER_ROLE`; duplicate `refId` reverts. 9 hardhat tests pass, one checks no readable fields exist.
- Contract v2 LIVE on Base Sepolia (84532): `0xC20ae8E6DEF7bF9eE347aa3Fa4213960bFA4fdf3` (2026-11-18), to be retired by v3. It holds only the smoke-test entry in plain text (amount 1, `TEST-DONOR`); that stays public forever, test data only. Listener has `RECORDER_ROLE` there; balance 0.0003 ETH. Record in `chain/deployments/baseSepolia.json`.
- Readable records `app/api/ledger.py` (in the AI app, needs bearer token): table `ledger_records` (canonical record JSON, salt, refId, leaf, chain tx / anchor day). `GET /api/ledger/records[?direction=in|out]`, `GET /api/ledger/records/{id}[?check_chain=true]`. Money in needs table label `bank_transaction`, money out `disbursement` (`access.can_read_table`, default: finance; admin/dev all). Refused single reads answer 404 like missing ids. Every read/refusal in `audit_log` (`ledger_read` / `ledger_denied`). `store()` helper for the loader and listener. Checks are in app code; no Postgres RLS on `ledger_records` yet. 7 tests.
- v1 (hash only) is retired. UNVERIFIED which v1 address was the final one: STATE said `0x5978Ca158E41c461d0C34bEC5fE0B0945EDC3E53`, `chain/deployments/baseSepolia-v1.json` says `0x692b8CFFC6C18e4b5075034245BAD5ABA54bCcEF`. Irrelevant unless someone reads v1.
  - Deployer/admin `0x56F42f7639DC03b30554F1116eD007E59f4639C3`; listener `0xC16e7dFd7e4B18c1db0859D1Ada9416EF0c8BEe7`.
- Python Merkle prototype with local anchor and prove/verify CLI.
- Listener funded (owner, 2026-11-18). `LISTENER_KEY` and `REFID_SECRET` in `chain/.env` (owner). Never change `REFID_SECRET` now.
- Live smoke test on v2 (2026-11-18): income record `TEST-SMOKE-0001` (amount 1, donor `TEST-DONOR`) tx `0x5e7380930844a50995c7154e4800fd9d9ef5e42f42422c4db3686306151911d9`; retry returned `exists`; verify true; tampered record false. Test anchor on fake day 1900-01-01 tx `0x3c87c73f506eb9de98e87ec08e1b030446eb0e2a58677d79890168fcf8f1b0c2`. Record + salt in `transparency_data/smoke-test.json` (git-ignored). Both are permanent test entries; ignore them in the dashboard (`TEST-` prefix, day 19000101).
- Python bridge `transparency/chain.py`: `ref_id` (HMAC), `LedgerClient.record(ref, leaf)/verify` (v3: hash only; checks `entries` first, retry = `exists`, other leaf = `ConflictError`), `BaseSepoliaAnchor` (same interface as `LocalAnchor`), `Web3Backend`. ABI in `transparency/abi.json` (re-copy after any contract change). `web3` in `requirements-chain.txt`. 9 tests with a fake contract; read-only status call against the live contract works.
- Verify endpoint `transparency/api.py` (standalone FastAPI, read-only, no LISTENER_KEY): `uvicorn transparency.api:app --port 8100`; `POST /verify {"record": {...}, "salt": "hex"}` -> `match`, `found` (found + no match = record or salt changed), `block_time`, `note` (returns nothing the caller did not send). Open `/docs` for a test page. CORS via `VERIFY_CORS_ORIGINS`. 9 tests (fake contract). Live check on v2 smoke record passed before the v3 change; re-check after v3 deploy.
- Architecture diagram `docs/architecture.drawio` (drawn for v2; needs redraw for v3). The file also has later edits in the working tree that were not made by Claude; left uncommitted.
- Chatbot M3 written on its own branch (parked).

## Next (in order)
0. Owner: deploy v3 (`cd chain; npx hardhat run scripts/deploy.js --network baseSepolia` with `RECORDER_ADDRESS` = listener), update `CONTRACT_ADDRESS` in `chain/.env`, keep v2 record as `baseSepolia-v2.json`, re-run smoke test (new record + salt goes in `ledger_records`).
1. Kaggle history loader: transactions into the database, daily root via `anchorBatch`. Waiting on Dong's cleaned file and column list.
2. Webhook listener: verify signature, dedupe on transaction id, store record and salt (salts must persist), call the bridge.
3. Small hardening: reject bank time later than now (+ a few minutes) in `records.py`; the contract does not check it. Real case: smoke record bank time 05:00Z is after its block time 03:45Z.
4. Merge `verify-endpoint` into `main` once the owner has reviewed it.

## Decisions
- Record shape (owner, 2026-11-18), in `transparency/records.py`: money in = amount + currency + donor_name (`Anonymous` allowed) + donor_id + bank time; money out = amount + currency + recipient_id + recipient_type (`unassigned` until Dong's cleaned data decides) + bank time. Bank time is separate from block time.
- Public vs hashed on chain (client, 2026-11-18, replaces the v2 choice): hash everything. On chain only refId (HMAC), leaf, block time, and per day root + count. Readable records only via the AI app's department permissions (table labels `bank_transaction` / `disbursement`), with audit. Public verify (`transparency/api.py`) stays open: it only confirms data the caller already has.
- UNVERIFIED with client: whether the per-day `count` on chain is acceptable (it shows how many transactions a history day had). Drop it in v3 before deploy if not.
- Team: Hung (owner) main blockchain line; the other Hung a parallel backup blockchain line; Dong downloads and cleans the Kaggle dataset; Tuan builds the dashboard/frontend. See `reminder.md`.
- Each transaction recorded as its own event, plus one root per day for the starting history.
- The listener service is the trusted writer. Two-person approval (multisig) later.
- Old data dropped. Test data comes from a Kaggle transactions file.

## Open questions
- Webhook service: payOS, SePay or Casso. payOS docs do not say whether its webhook covers all bank activity or only payOS links. SePay reports money in and out only for some banks. Confirm bank and service with the client.
- Where `REFID_SECRET` lives; encryption of stored records at rest.

## Log (newest first)
- 2026-11-18 | Claude Code | client: hash all. Contract v3 hash-only + tests, ABI, bridge, verify endpoint trimmed, permission-gated readable records in the app (ledger_records, /api/ledger) + tests. v3 not deployed | chain/contracts/TransparencyLedger.sol, chain/test/TransparencyLedger.test.js, transparency/abi.json, transparency/chain.py, transparency/api.py, app/models.py, app/api/ledger.py, app/main.py, tests/test_chain_bridge.py, tests/test_verify_api.py, tests/test_ledger_api.py, docs/STATE.md
- 2026-11-18 | Claude Code | architecture diagram (draw.io, built = solid, planned = dashed); official jgraph drawio skill installed at user level (~/.claude/skills/drawio) | docs/architecture.drawio, docs/STATE.md
- 2026-11-18 | Claude Code | verify endpoint + tests, live read-only check on smoke record | transparency/api.py, tests/test_verify_api.py, docs/STATE.md
- 2026-11-18 | Claude Code | cleanup fast-forwarded into main and verify-endpoint, pushed; transparency-contract/anchor already gone on remote; cleanup branch deleted | docs/STATE.md
- 2026-11-18 | Claude Code | hygiene: removed dead `BaseSepoliaAnchor` stub from anchor.py (real one is in chain.py), strict zip in batch, root README rewritten for the transparency project, stale doc sections fixed, stray root package-lock.json removed, gitignore node_modules/.ruff_cache, local merged branch deleted | transparency/anchor.py, transparency/batch.py, README.md, chain/README.md, docs/TRANSPARENCY.md, reminder.md, .gitignore, docs/STATE.md
- 2026-11-18 | Claude Code | merged transparency-contract into main (fast-forward, f3a6cf8); new branch verify-endpoint | docs/STATE.md
- 2026-11-18 | Claude Code | live smoke test on v2: record, retry, verify, tamper, anchor all as expected | docs/STATE.md, reminder.md
- 2026-11-18 | Claude Code | deployed contract v2 to Base Sepolia 0xC20a…fdf3, listener role granted, .env updated, v1 record kept as baseSepolia-v1.json | chain/deployments/*, chain/.env (local), docs/STATE.md, reminder.md
- 2026-11-18 | Claude Code | contract v2 (public non-sensitive fields + leaf), hardhat tests, bridge + ABI updated to v2 | chain/contracts/TransparencyLedger.sol, chain/test/TransparencyLedger.test.js, transparency/chain.py, transparency/abi.json, tests/test_chain_bridge.py, docs/STATE.md, reminder.md
- 2026-11-18 | Claude Code | record shape (in/out fields) + tests; logged public-vs-hash decision as open | transparency/records.py, tests/test_records.py, docs/STATE.md
- 2026-11-18 | Claude Code | Python bridge + tests, ABI copy, env example keys, requirements-chain.txt | transparency/chain.py, transparency/abi.json, tests/test_chain_bridge.py, chain/.env.example, requirements-chain.txt
- 2026-11-18 | Claude Code | RECORDER_ROLE granted to listener (owner ran grant-recorder.js); fixed CONTRACT_ADDRESS in chain/.env | docs/STATE.md, reminder.md
- 2026-11-18 | Claude Code | hardhat tests pass on owner machine (9); added reminder.md with proposed per-person tasks | reminder.md, docs/STATE.md
- 2026-11-18 | claude.ai | split handoff into AGENTS.md + CLAUDE.md + this file | AGENTS.md, CLAUDE.md, docs/STATE.md
- 2026-11-17 | claude.ai | contract deployed to Base Sepolia; grant script, `.env` support, address validation | chain/scripts/*, chain/hardhat.config.js, chain/.env.example
- 2026-11-17 | claude.ai | contract, tests, deploy script | chain/*
- 2026-11-16 | claude.ai | Python transparency prototype; M3 answer flow; vh-branch merged into main | transparency/*, app/rag/*
