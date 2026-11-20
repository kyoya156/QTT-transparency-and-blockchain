# Reminders: who does what

Last updated: 2026-11-19. Task details live in `docs/STATE.md` ("Next"). How the ledger works: `docs/explainer.html`.

## For team discussion (2026-11-18)

### Already decided
- **Who decides:** the "client" is a teacher advising us. The team decides; we ask the teacher when something is unclear.
- **No third-party audits.** Integrity comes only from things we build. Data feeds (payOS, SePay, Casso) are fine as sources.
- **Hash only on chain** (contract v3, live). Readable records stay in our database, readable only by departments the admin allows (`bank_transaction` for money in, `disbursement` for money out), every read logged.
- **Full donor names**, e.g. `Phạm Thanh Hùng`, or `Anonymous`. Kept exactly as the source gives them (bank feeds often send `PHAM THANH HUNG`); Unicode is normalised so the same visible name always hashes the same.
- **History first, then live:** history is stamped as one Merkle root per day; each new transaction is stamped on its own within seconds of the payOS notification (not daily).
- **What the chain gives us:** a record that is edited or deleted in our database after stamping no longer matches the chain, so it can be detected. It does not stop the edit, and it does not prove the record is true.

### Known gaps
- **The short window before stamping:** the record passes through our server before the chain. A change made there would be stamped as if correct.
- **Money out:** payOS only reports money coming in. SePay watching the bank account covers MB (tested 2026-11-19); other banks depend on the feed or the statement import.
- **Nobody is alerted today:** a mismatch is only found if someone runs a check.

### Proposed technical measures (to agree on)
Must be decided **before** importing the history, because they change what goes into each fingerprint and fingerprints on chain are permanent:
1. [x] **Sequence number + link to the previous record** in every record. Deleting, inserting or reordering any record breaks every link after it. **Built 2026-11-20** (`docs/MEASURES.md`).
agreed to option 1
2. [x] **Running balance** in every record. A wrong amount makes all later balances disagree with the real account. Needs the opening balance and rows in time order. **Test 2026-11-19: MB via SePay sends no balance**, so we would compute it ourselves from an opening balance (weaker than the bank stating it; the bank statement import can check it). **Built 2026-11-20** (`docs/MEASURES.md`).
agreed to option 2 but show donor ID, amount, date, and running balance , full name(no diacrytic = plain text) and HASH original message (from 3.) 
in simpler term on record on blockchain (donorID + amount + date + running balance + hash of full name + hash of original message)
How it reaches the chain (agreed 2026-11-19, "option A"): the chain keeps **one fingerprint of the whole record** (contract v3 unchanged). The readable fields are shown on the dashboard together with the record's salt, so anyone can recompute the fingerprint and compare it with the chain. Public fields are not hashed on their own, but they are inside the fingerprint, so any edit is detected. Rejected "option B" (public fields stored on chain directly): needs contract v4, nothing could ever be removed or corrected out of view, history day roots would not work.
3. [x] **Fingerprint of the original Sepay message** in live records, with the message stored, after checking Sepay's signature. Shows the record came from Sepay, not typing. **Built 2026-11-20** (`docs/MEASURES.md`).
agreed save a database version and another hashed version on the record on chain

4. [x] **Database refuses edits and deletes** on `ledger_records` (insert only). Corrections are new records pointing to the old one. **Built 2026-11-20** (`docs/MEASURES.md`).
agreed to option 4, but if the record ever needs to be corrected how about the record on chain?
Answer: the chain entry stays forever; a correction is a new record pointing to the old one (details + proposal in `docs/MEASURES.md`, measure 4). Shape to agree before building.
5. [x] **Listener stamps straight from the message:** check signature, build record, fingerprint in memory, stamp within seconds. Never re-read from the database before stamping. Alert if a stamp is late compared to bank time. **Built 2026-11-20** (`docs/MEASURES.md`).
agreed to option 5 (2026-11-19). Detailed explanation, examples and open sub-choices: `docs/MEASURES.md`, measure 5.
6. [x] **Nightly automatic check:** re-hash every row and compare with the chain; every chain entry has a row; no gaps in sequence/links; balances add up; late stamps flagged. Results to the audit log and an alert. **Built 2026-11-20** (`docs/MEASURES.md`).
agreed to option 6
8. [ ] **Donor receipts:** link or QR with the donor's record + salt, so donors can check their own donation. The receipt is the version sent from `ledger_records`: that row's `record_json` (exact hashed bytes) + `salt` + `ref_id` + `chain_tx`. **Paused (2026-11-19)**, see "Paused topics".i dont quite understand 

Suggested order: 1-3 now (before Dong's data), then 4, 6, 5, 8.

### Questions to settle
- [ ] **Bank feed: SePay as the first source?** Live test 2026-11-19 on Hung's MB account (SePay free plan, direct bank link): money in and out both arrived within ~15 s. MB money out is covered, no staff entry needed. Plan: one adapter per source (SePay first, Casso if needed) + bank statement import (CSV/Excel) as the fallback for any bank. Vietcombank personal only via SMS (not tested).
- [ ] **Memo codes for donors and recipients?** The bank sends no sender/recipient fields, only free memo text. Proposal: SePay extracts a code from the memo by prefix. Money out: staff write the recipient code, e.g. `CHI R023`; no code = `unassigned`. Money in: a donation QR pre-fills a donor code; no code = `Anonymous`. We do not guess names from memo text.
- [ ] **Running balance (measure 2):** compute it ourselves from an opening balance, or drop it? (The bank feed does not provide it.)
- [ ] **Per-day row count on chain:** keep (shows how many history rows a day had) or drop?
- [ ] **Publish monthly totals** (total in, total out, closing balance; no personal data) on the dashboard?
- [ ] **Where `REFID_SECRET` lives** long term, and backups for the database and salts (losing a salt means that record can never be checked again).
- [ ] **Donor consent wording** for storing full names (Vietnam Decree 13/2023), with the `Anonymous` option.

### Paused topics (come back later)
- **Donor traces back to their own transaction** (paused 2026-11-19). Today a donor cannot: checking needs record + salt (ours only) and refId needs `REFID_SECRET`. Options discussed:
  1. Donation code in the memo (QR pre-fills it) + receipt lookup by code + amount: returns record, salt, refId, chain tx link; donor can check on Basescan without trusting us. Leaning towards this.
  2. Lookup by the donor's bank reference + amount + time. UNVERIFIED that the sender's reference equals SePay `referenceCode` for inter-bank transfers (test with one transfer from another bank).
  3. Public daily list built from SePay fields. Codes-only rows (`code` + stamp time + chain link, no amount) fit "hash everything"; showing amount/time needs client OK. Never publish memo text (`content`): inter-bank memos hold sender name + account.
  Depends on: memo codes decision above, measure 3 (stored original message), measure 8. Does not show where the money was spent (money in is not linked to money out yet).

## Hung (owner): blockchain, main line
- [x] Grant `RECORDER_ROLE` to the listener: from `chain/`, run `npx hardhat run scripts/grant-recorder.js --network baseSepolia`. Expect `hasRole check: true`.
- [x] Send the listener wallet about 0.0001 Base Sepolia test ETH.
- [x] Python bridge `transparency/chain.py` (code + fake-contract tests).
- [x] Deploy contract v2 (`0xC20ae8E6DEF7bF9eE347aa3Fa4213960bFA4fdf3`) and update `CONTRACT_ADDRESS` in `chain/.env`.
- [x] Settle with the client what goes on chain: hash everything (2026-11-18). Readable data only via the app's department permissions.
- [x] Deploy contract v3 (`0x444cbfb6224B5a9cB8bE25c2BAa4AC646a446244`); smoke test passed.
- [ ] Share `docs/explainer.html` with the team (how the ledger works).
- [ ] Lead the team discussion above; record the outcomes in `docs/STATE.md` "Decisions".
- [x] Add `LISTENER_KEY` and `REFID_SECRET` to `chain/.env`; live test record + anchor passed.
- [x] Verify endpoint (`transparency/api.py`).
- [x] SePay test receiver + live test on MB (in and out).
- [x] Webhook listener with measures 1-6; live test passed 2026-11-20 (2 simulated + 1 real transfer, nightly check ok).
- [ ] Decide where `REFID_SECRET` is stored.

### Still missing on the blockchain side (2026-11-20)
Besides the team decisions (memo codes, correction shape) and Dong's data:

Needed before a real demo:
1. [ ] **Backups of the database and salts.** A lost salt means that record can never be checked again. Nightly copy of the database to a second place.
2. [ ] **Where `REFID_SECRET` lives.** Lost or changed = no existing record can be found on chain again.
3. [ ] **Stable home for the listener.** Today: your PC + quick tunnel, URL changes on restart (SePay must be updated each time). Named Cloudflare tunnel or a small server.
4. [ ] **Low-balance alert for the listener wallet** (~0.0003 test ETH). Empty = stamping stops quietly; rows wait unstamped.
5. [ ] **History loader** (daily roots + a proof per row). Can start from a guessed format, adjust when Dong's file arrives.

Makes the claims stronger:
6. [ ] **Verify the contract source on Basescan**, so anyone can read the code and see it is hash only.
7. [ ] **Nightly check, second half:** every chain entry has a matching row; run it automatically (Windows Task Scheduler).
8. [ ] **Data for Tuan's dashboard:** agree the public fields, add an endpoint.

Later / optional:
9. [ ] Donor receipts (measure 8, paused).
10. [ ] Two-person wallet (multisig) as contract admin; today one wallet.
11. [ ] Merge `verify-endpoint` into `main`.

Note for the report: all of this runs on Base Sepolia, a test network.
-Someone checks a record Three possible answers: match (unchanged since the block time), found but no match (the record or salt was altered), or not found (never stamped).
need example cases

## Viet Hung: blockchain, backup line
Builds a second blockchain version in parallel, so the team can still submit if one fails.
- [ ] Keep the backup on its own branch so the two lines do not overwrite each other.
- [ ] Use the same cleaned dataset from Dong, so either version can be demoed with the same data.
- [ ] Use the same record fields (`transparency/records.py`): in = amount + donor full name (or Anonymous) + donor ID + bank time; out = amount + recipient ID + recipient type + bank time. Only hashes go on chain, nothing readable. If the team adopts measures 1-3 above, the record gains sequence, previous link, balance and payOS message hash.

## Dong: dataset
- [ ] Clean it: fix or drop bad rows, consistent date and amount formats, mark each row as income or expense.
- [ ] Cleaned file must give, per row: amount, bank time (with timezone), direction (in/out), donor ID + full name for money in (keep names exactly as in the source, accents and case included; blank = Anonymous), recipient ID for money out. Recipient type can stay blank for now. Use codes for recipients, never children's real names.
- [ ] If the team adopts the running balance (measure 2): rows sorted by bank time, plus the opening balance before the first row if the dataset has one.
- [ ] Share the cleaned file and a short list of columns (name, type, meaning). The loader (STATE.md step 3) and the dashboard both read from it.
- [ ] Keep the raw data out of git (`data/` is git-ignored). Note the Kaggle link and licence.

## Tuan: dashboard / frontend UI/UX
- [ ] Design and build the dashboard: income and expense views, transaction list. Data comes from `GET /api/ledger/records` (login token; what each department sees follows the admin's labels), not from the chain: the chain holds only hashes. Skip test entries (`TEST-` IDs, day 19000101).
- [ ] Verify screen: user gives a record + salt (`POST /verify`), or a logged-in user opens `GET /api/ledger/records/{id}?check_chain=true`; show match and block time.
- [ ] Wording: the chain shows a record existed unchanged at a block time. It does not prove the record is true.
- [ ] Use Dong's cleaned data for mock screens until the backend is ready.

## Everyone
- Never share or commit a private key. Keys go only in `chain/.env`.
- Run `pytest` and `cd chain && npx hardhat test` before each commit.
- Read `AGENTS.md` and `docs/STATE.md` before starting; update `docs/STATE.md` when you finish.
