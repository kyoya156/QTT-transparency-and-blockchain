# TransparencyLedger (chain/)

One contract, three write functions, all restricted to `RECORDER_ROLE` (the listener service):

| Function | Event | Purpose |
|---|---|---|
| `recordIncome(refId, leaf, (amount, txTime, currency, donorId, donorName))` | `Income` | money in |
| `recordExpense(refId, leaf, (amount, txTime, currency, recipientId, recipientType))` | `Expense` | money out |
| `anchorBatch(day, root, count)` | `BatchAnchored` | Merkle root of the starting history, once per day |

- `refId` is an HMAC of the bank's transaction id, so webhook retries are rejected on-chain (`AlreadyRecorded`).
- `leaf` is the salted hash of the full record, built off-chain.
- Public in plain text (v2): amount, currency, bank time, donor ID, recipient ID and type. `donorName` is sent empty until the client approves names on chain. Everything on chain is permanent; use codes for people, never children's names.
- Admin can grant or revoke recorders and `pause()` writes if the recorder key leaks.

## Run
    npm install
    npx hardhat test
    npx hardhat run scripts/deploy.js                 # local, in-process

## Base Sepolia
    DEPLOYER_KEY=0x<test wallet key> RECORDER_ADDRESS=0x<listener address> \
      npx hardhat run scripts/deploy.js --network baseSepolia
Copy `chain/.env.example` to `chain/.env`, fill `DEPLOYER_KEY` and `RECORDER_ADDRESS`, then run the deploy with `--network baseSepolia`; the environment-variable form below also works.
Needs a test wallet funded with free Base Sepolia ETH. Never commit a key; use a throwaway wallet for tests.

`hardhat.config.js` compiles with the bundled solc-js, so no compiler download is needed.

## Limits
It proves a record existed unchanged at a block time. It does not prove the bank feed was true or complete.
