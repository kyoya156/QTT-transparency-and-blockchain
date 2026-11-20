# Integrity measures: detailed notes

Short list and team decisions: `reminder.md`, "Proposed technical measures". This file keeps the longer explanation for each measure so anyone can pick it up later.

Ground rule for all of them: the chain proves a record existed unchanged at a block time. It does not prove the record is true.

---

## Measure 5: the listener stamps straight from the message

Status: **agreed** (team, 2026-11-19). Not built yet beyond the normal path (see "Where the code stands").

### The idea in one sentence
When the bank tells us about a transfer, we stamp its fingerprint on chain right away, using the signed message we just received, before anyone has a chance to change the record in our database.

### Why: the unprotected gap
Every record spends a short time in our database before its fingerprint is on chain. In that gap it has no protection. If someone edits it then, the chain protects the edited version as if it were real, and every later check says "match".

Measure 5 keeps that gap to seconds and raises an alert when it runs long.

### Example 1: normal case (what we want)
Lan donates 500,000 VND.

| Time | What happens |
|---|---|
| 14:03:00 | Bank records the transfer (bank time) |
| 14:03:13 | SePay sends us the message: "500,000 VND in, memo QTT7F3K2", signed |
| 14:03:13 | Listener checks SePay's signature: it really came from SePay, unchanged |
| 14:03:13 | Listener builds the record and computes the fingerprint (leaf) in memory, from that message |
| 14:03:13 | Saves record + salt in `ledger_records` (salt must be saved before stamping, or the stamp could never be checked) |
| 14:03:20 | Stamps the fingerprint computed at 14:03:13 on chain |

Unprotected for 7 seconds. If someone changes the database row at 14:03:15, the chain still holds the fingerprint of the real 500,000, and the nightly check (measure 6) finds that the row no longer matches.

### Example 2: what measure 5 prevents
If the listener saved the record and then read it back from the database to stamp it:

| Time | What happens |
|---|---|
| 14:03:13 | Saves "500,000 VND" in the database |
| 14:03:15 | Someone with database access changes it to "50,000 VND" |
| 14:03:20 | Listener reads the row back, gets "50,000", stamps that |

The chain now "proves" 50,000 and every check agrees. The wrong value is locked in. Hence the rule: stamp what was computed from the message, not what is in the database.

### Example 3: late stamp alert
Stamping can be slow: chain down, listener out of gas, server restarted.

| Bank time | Stamped | Gap | Result |
|---|---|---|---|
| 14:03 | 14:03:20 | 20 s | Normal |
| 14:03 | 16:45 | 2 h 42 min | Alert: "stamped late, check against the bank statement" |

A late stamp does not mean the record is wrong. It means the unprotected gap was long, so a person compares it with the bank statement.

### The rule, made precise
Measures 1 (link to previous record) and 2 (running balance) need the previous record's link and balance, which come from the database. So the rule is:

> Never re-read **this** record from the database before stamping. Build it from the signed SePay message (plus the previous record's link and balance), compute the fingerprint in memory, and stamp that value.

Records must be numbered one at a time (a lock or database sequence). Otherwise two webhooks arriving together could both link to the same previous record and the chain of links would fork.

### Sub-choices (built as proposed 2026-11-20; team can still change them)

| Point | Options | Proposal |
|---|---|---|
| SePay resends a message whose record is still unstamped | a) stamp the stored fingerprint (current code) b) rebuild the record from the resent signed message + stored salt; stamp only if it matches the stored fingerprint, otherwise alarm | **b**: the retry becomes a tamper check |
| Unstamped records at startup (chain was down) | a) stamp from the database, flagged "check against bank statement" b) skip and wait for SePay to resend c) rebuild from the stored signed original (needs measure 3) | **c** once measure 3 is built, **a** until then |
| Late threshold | 5 / 10 / 30 min after bank time | **10 min**: bank time is minute precision and a message was seen 19 s *before* its bank time |
| Where the alert goes | log only / `audit_log` / dashboard flag | **`audit_log` + a flag on the record**; the nightly check (6) also lists late stamps |

### How it fits the other measures
- **1 and 2 (links, balance):** computed in memory together with the record, inside the same numbered step.
- **3 (original message):** the stored signed original lets late or retried stamps be rebuilt from SePay's own words instead of from our database.
- **4 (insert-only database):** makes the Example 2 edit impossible through normal means; measure 5 still protects against someone with direct database control.
- **6 (nightly check):** catches any row that no longer matches its fingerprint, and reports late stamps.

### Where the code stands (`transparency/listener.py`, 2026-11-20)
| Part | State |
|---|---|
| Normal path: fingerprint computed in memory, stamped in the background within seconds | Done |
| Resend of an unstamped record | Done (b): rebuilt from the resent signed message; mismatch = no stamp + `ledger_tamper` in `audit_log` |
| `stamp_pending` at startup | Done (c): stored original's HMAC re-checked, record rebuilt; mismatch = no stamp + alarm |
| Late-stamp alert | Done: > 10 min after bank time sets `stamp_late` + `ledger_late_stamp` audit row |
| Numbering one at a time | Lock in the listener + unique `seq` column (retry on clash) |

Tests (`tests/test_listener.py`): resend unchanged stamps; resend after a database edit refuses + alarm; startup retry refuses an edited original; late flag; future bank time refused. UNVERIFIED: whether SePay's resend body is byte-identical to the first (if not, an honest resend raises a false tamper alarm; check on the first real resend). Not tested: two truly parallel webhooks (the lock covers one process; several workers rely on the unique `seq`).

---

## Measures 1-3: what each record now holds (built 2026-11-20)

`transparency/records.py` `link()`. Every record, money in or out:

| Field | Measure | Meaning |
|---|---|---|
| `seq` | 1 | 1, 2, 3 ... one counter for in and out |
| `prev` | 1 | leaf of record `seq - 1`; record 1 has `GENESIS` (0x00...00) |
| `balance` | 2 | running balance after this record: `OPENING_BALANCE` (chain/.env, 0 for tests) +in -out |
| `source_hash` | 3 | sha256 of the exact signed SePay message; the message and its signature headers are kept in `ledger_records.source_raw` / `source_auth` (never shown by the records API: the memo holds sender name + account) |
| `donor_name` | — | plain text, no diacritics, upper case: `Phạm Thanh Hùng` -> `PHAM THANH HUNG` (owner, 2026-11-20). Readable only through department permissions |

The chain still holds one fingerprint per record (option A, contract v3 unchanged).

Note for option A: a public dashboard can show amount / date / balance, but anyone recomputing the fingerprint needs every field including `donor_name` and the salt. So public re-checking works only for people given the full record (department readers, or the donor with their receipt, measure 8).

## Measure 4: insert-only database (built 2026-11-20)

`transparency/guard.py`, installed by the listener and by `app.migrations.init_db`. Database triggers (SQLite and Postgres) refuse UPDATE, DELETE and TRUNCATE on `ledger_records`. One exception: the stamp columns (`chain_tx`, `stamped_at`, `stamp_late`) may be filled once, while `chain_tx` is empty, with nothing else changing. Postgres trigger is UNVERIFIED (no Postgres in tests); check with one UPDATE on the real database.

**Owner's question: if a record needs correcting, what about the chain?** The chain entry stays forever; nothing on chain can be edited or removed. A correction is a **new** record (next `seq`, its own fingerprint on chain) that names the record it corrects and carries the adjusting amount, so the running balance stays right. The dashboard shows the old record as "corrected by #N". Both are visible, so nobody can quietly change history. Not built yet: needs a `corrects` field and a reason; agree the shape first.

## Measure 6: nightly check (built 2026-11-20)

`python -m transparency.nightly` (read-only on chain). Checks every row: canonical JSON, record + salt = leaf, refId, seq without gaps, prev links, balances follow, stored original = `source_hash`, stamped leaf equals the chain's. Lists late stamps and rows unstamped after 10 min. Writes one `ledger_check` row to `audit_log`; exit 1 on any problem. Not yet: "every chain entry has a row" (needs reading `Recorded` events) and scheduling it (Windows Task Scheduler or cron). Tests in `tests/test_integrity.py`.

### What it does not protect against
Someone who changes the listener program itself (or the server it runs on) can build a wrong record before any fingerprint exists. Measure 5 shrinks the risk window; it does not remove it. The bank statement remains the final cross-check.
