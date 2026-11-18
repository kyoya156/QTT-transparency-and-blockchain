# Project state (living file)

Last updated: 2026-11-18 by claude.ai session. Newest facts win. Keep this short; move old detail to the log.

## Update protocol (every agent, end of every session)
1. Update "Now", "Done", "Next" and "Decisions" so a cold reader is current.
2. Add one line at the top of the Log: `date | agent | what changed | files`.
3. Record anything you could not verify as UNVERIFIED, with the check that would settle it.
4. Commit this file with your work. Never put keys or secrets here.

## Now
Building the transparency path: bank webhook -> listener -> database -> contract events -> verify.
Branch: `transparency-contract` (includes `transparency-anchor`). Not yet merged to `main`.

## Branches
| Branch | State |
|---|---|
| `main` | 9bb5917: retrieval hardening merged, docs reframed to one internal assistant |
| `transparency-anchor` | Python prototype: salted Merkle batch, local hash-chained anchor, prove/verify CLI |
| `transparency-contract` | adds `chain/`: Solidity, tests, deploy and grant scripts, `.env` support |
| `m3-answer` | chatbot answer flow, fake-LLM tests only. Parked |
| `vh-branch` | inside `main` already; delete on GitHub when the other Hung agrees |

## Done
- `TransparencyLedger`: `recordIncome`, `recordExpense`, `anchorBatch(uint32 yyyymmdd, root, count)`, `verify`, pause; writes need `RECORDER_ROLE`; duplicate `refId` reverts. 9 hardhat tests pass.
- Deployed on Base Sepolia (84532): `0x5978Ca158E41c461d0C34bEC5fE0B0945EDC3E53`.
  - Deployer/admin `0x56F42f7639DC03b30554F1116eD007E59f4639C3`; listener `0xC16e7dFd7e4B18c1db0859D1Ada9416EF0c8BEe7`.
- Python Merkle prototype with local anchor and prove/verify CLI.
- Chatbot M3 written on its own branch (parked).

## Next (in order)
1. UNVERIFIED: listener holds `RECORDER_ROLE`. The deploy's grant failed on a bad `RECORDER_ADDRESS`. Run `npx hardhat run scripts/grant-recorder.js --network baseSepolia` from `chain/` (`.env`: `DEPLOYER_KEY`, `RECORDER_ADDRESS`, `CONTRACT_ADDRESS`). Expect `hasRole check: true`. Listener also needs about 0.0001 test ETH.
2. Python bridge `transparency/chain.py` (add `web3`): ABI copied into `transparency/abi.json`; `leaf` = `merkle.leaf_hash(record, salt)`; `refId` = HMAC-SHA256(secret, source tx id); check `entries(refId)` before sending; real Base Sepolia anchor behind the `LocalAnchor` interface. Env: `LISTENER_KEY`, `CONTRACT_ADDRESS`, `BASE_SEPOLIA_RPC`, `REFID_SECRET`.
3. Kaggle history loader: transactions into the database, daily root via `anchorBatch`. Need the file or its columns from the owner.
4. Webhook listener: verify signature, dedupe on transaction id, store record and salt (salts must persist), call the bridge.
5. Verify endpoint or page: record + salt -> rebuild leaf -> `verify()` -> block time.

## Decisions
- Each transaction recorded as its own event, plus one root per day for the starting history.
- The listener service is the trusted writer. Two-person approval (multisig) later.
- Old data dropped. Test data comes from a Kaggle transactions file.

## Open questions
- Webhook service: payOS, SePay or Casso. payOS docs do not say whether its webhook covers all bank activity or only payOS links. SePay reports money in and out only for some banks. Confirm bank and service with the client.
- Where `REFID_SECRET` lives; encryption of stored records at rest.

## Log (newest first)
- 2026-11-18 | claude.ai | split handoff into AGENTS.md + CLAUDE.md + this file | AGENTS.md, CLAUDE.md, docs/STATE.md
- 2026-11-17 | claude.ai | contract deployed to Base Sepolia; grant script, `.env` support, address validation | chain/scripts/*, chain/hardhat.config.js, chain/.env.example
- 2026-11-17 | claude.ai | contract, tests, deploy script | chain/*
- 2026-11-16 | claude.ai | Python transparency prototype; M3 answer flow; vh-branch merged into main | transparency/*, app/rag/*
