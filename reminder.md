# Reminders: who does what

Last updated: 2026-11-18. Task details live in `docs/STATE.md` ("Next").

## Hung (owner): blockchain, main line
- [x] Grant `RECORDER_ROLE` to the listener: from `chain/`, run `npx hardhat run scripts/grant-recorder.js --network baseSepolia`. Expect `hasRole check: true`.
- [x] Send the listener wallet about 0.0001 Base Sepolia test ETH.
- [x] Python bridge `transparency/chain.py` (code + fake-contract tests).
- [x] Deploy contract v2 (`0xC20ae8E6DEF7bF9eE347aa3Fa4213960bFA4fdf3`) and update `CONTRACT_ADDRESS` in `chain/.env`.
- [ ] Settle with the client whether donor names go on chain (needs donor consent).
- [x] Add `LISTENER_KEY` and `REFID_SECRET` to `chain/.env`; live test record + anchor passed.
- [x] Verify endpoint (`transparency/api.py`).
- [ ] Webhook listener.
- [ ] Decide where `REFID_SECRET` is stored.
- [x] Review and merge `transparency-contract` into `main`.

## The other Hung: blockchain, backup line
Builds a second blockchain version in parallel, so the team can still submit if one fails.
- [ ] Agree to delete `vh-branch` on GitHub (already inside `main`).
- [ ] Keep the backup on its own branch so the two lines do not overwrite each other.
- [ ] Use the same cleaned dataset from Dong, so either version can be demoed with the same data.
- [ ] Use the same record fields (`transparency/records.py`): in = amount + donor name + donor ID + bank time; out = amount + recipient ID + recipient type + bank time. Names stay off chain for now.

## Dong: dataset
- [ ] Download a transactions dataset from Kaggle (CSV or XLSX).
- [ ] Clean it: fix or drop bad rows, consistent date and amount formats, mark each row as income or expense.
- [ ] Cleaned file must give, per row: amount, bank time (with timezone), direction (in/out), donor ID + name for money in, recipient ID for money out. Recipient type can stay blank for now. Use codes for people, never children's real names.
- [ ] Share the cleaned file and a short list of columns (name, type, meaning). The loader (STATE.md step 3) and the dashboard both read from it.
- [ ] Keep the raw data out of git (`data/` is git-ignored). Note the Kaggle link and licence.

## Tuan: dashboard / frontend UI/UX
- [ ] Design and build the dashboard: income and expense views, transaction list. Skip test entries (`TEST-` donor/recipient IDs, day 19000101).
- [ ] Verify screen: user gives a record, the page shows whether it matches the chain and its block time.
- [ ] Wording: the chain shows a record existed unchanged at a block time. It does not prove the record is true.
- [ ] Use Dong's cleaned data for mock screens until the backend is ready.

## Everyone
- Never share or commit a private key. Keys go only in `chain/.env`.
- Run `pytest` and `cd chain && npx hardhat test` before each commit.
- Read `AGENTS.md` and `docs/STATE.md` before starting; update `docs/STATE.md` when you finish.
