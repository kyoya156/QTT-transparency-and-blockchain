# TransparencyLedger (chain/)

Contract v3, **hash only**. Nothing readable goes on chain; readable records stay in our database (`ledger_records`, behind department permissions).

| Function | Who | Purpose |
|---|---|---|
| `record(refId, leaf)` | `RECORDER_ROLE` (listener) | one live transaction; event `Recorded` |
| `anchorBatch(day, root, count)` | `RECORDER_ROLE` | Merkle root of one history day (`day` = yyyymmdd); event `BatchAnchored` |
| `verify(refId, leaf)`, `entries(refId)`, `batches(day)` | anyone (free reads) | `entries` = (leaf, block time) |
| `pause()` / `unpause()`, grant/revoke roles | admin | stop writes if the listener key leaks |

- `refId` = HMAC(`REFID_SECRET`, source transaction id), so bank ids are not public. A second write for the same `refId` reverts (`AlreadyRecorded`); the Python bridge checks `entries` first and returns `exists` on webhook retries.
- `leaf` = salted hash of the full record (`transparency/merkle.py`). The salt stays off chain; losing it means that record can never be checked.
- Everything on chain is permanent. The per-day `count` shows how many history rows a day had. Team decision (2026-11-21): count off for now. `anchorBatch` reverts on `count == 0`, so the loader must either anchor one root for the whole history (count = total rows) or wait for a v4 contract.

## Run
    npm install
    npx hardhat test
    npx hardhat run scripts/deploy.js                 # local, in-process

## Base Sepolia
Live: `deployments/baseSepolia.json` (v3 `0x444cbfb6224B5a9cB8bE25c2BAa4AC646a446244`). Retired: `baseSepolia-v2.json` (plain-text fields, holds one test entry), `baseSepolia-v1.json`.

Copy `chain/.env.example` to `chain/.env`, fill `DEPLOYER_KEY` and `RECORDER_ADDRESS`, then:

    npx hardhat run scripts/deploy.js --network baseSepolia
    npx hardhat run scripts/grant-recorder.js --network baseSepolia   # only if the deploy did not grant it

Needs a throwaway test wallet funded with free Base Sepolia ETH. Never commit a key. After any contract change, re-copy the ABI to `transparency/abi.json`.

`hardhat.config.js` compiles with the bundled solc-js, so no compiler download is needed.

## Limits
It proves a record existed unchanged at a block time. It does not prove the bank feed was true or complete.
