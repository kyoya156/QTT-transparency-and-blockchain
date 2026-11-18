# Handoff to Claude Code (written 18 Nov 2026)

Read this first, then continue from "Next tasks". Branch: `transparency-contract` (includes `transparency-anchor`).

## Project and rules
- COS40005 Project A, financial transparency. Chatbot is parked until the blockchain part works. Blockchain is the main focus now.
- NDA: never write a client name or branding in code, docs or commits.
- Owner: Hung (final decider on technical choices). Keep replies short. After changes, list the files touched.
- Windows + PowerShell. Local projects live in `D:\local-projects`. Keep `node_modules` out of OneDrive.
- Never ask for, print or commit a private key. Keys live only in `chain/.env` (git-ignored).
- The chain proves a record existed unchanged at a block time. It does not prove the record is true. Do not claim more in docs or UI.

## Branches
| Branch | State |
|---|---|
| `main` | 9bb5917, retrieval hardening merged, docs reframed to one internal assistant |
| `transparency-anchor` | Python prototype: salted Merkle batch, local hash-chained anchor, prove/verify CLI (`transparency/`, `scripts/transparency.py`) |
| `transparency-contract` | adds `chain/` (Hardhat, Solidity, tests, deploy scripts, .env support) |
| `m3-answer` | chatbot answer flow (guardrails, compose, citations, hand-off), tested with a fake LLM only. Parked |
| `vh-branch` | already inside `main`; delete on GitHub when the other Hung agrees (deletes fail from Claude's cloud sandbox) |

## Done
- `chain/contracts/TransparencyLedger.sol`: `recordIncome(refId, leaf)`, `recordExpense(refId, leaf)`, `anchorBatch(uint32 day yyyymmdd, root, count)`, `verify(refId, leaf)`, pause. Writes need `RECORDER_ROLE`; duplicate `refId` reverts `AlreadyRecorded`. `npx hardhat test`: 9 passing.
- Deployed on Base Sepolia (chain id 84532): `0x5978Ca158E41c461d0C34bEC5fE0B0945EDC3E53`.
  - Deployer/admin: `0x56F42f7639DC03b30554F1116eD007E59f4639C3`
  - Listener (recorder): `0xC16e7dFd7e4B18c1db0859D1Ada9416EF0c8BEe7`
- The deploy's role grant failed (bad `RECORDER_ADDRESS` string in the user's `.env`). Scripts were fixed. **Status of the grant is unverified.**

## Next tasks, in order
1. **Verify or run the grant.** `.env` needs `DEPLOYER_KEY`, `RECORDER_ADDRESS`, `CONTRACT_ADDRESS`. Run `npx hardhat run scripts/grant-recorder.js --network baseSepolia` from `chain/`. Expect `hasRole check: true`. The listener wallet also needs about 0.0001 test ETH.
2. **Python bridge** (`transparency/chain.py`, add `web3` to requirements):
   - Copy the ABI from `chain/artifacts/...` into the repo (artifacts are git-ignored), e.g. `transparency/abi.json`.
   - `leaf` = `transparency.merkle.leaf_hash(record, salt)`. `refId` = HMAC-SHA256(secret, source transaction id), 32 bytes.
   - Check `entries(refId)` before sending, so retries are safe. Handle nonce and gas.
   - Env: `LISTENER_KEY`, `CONTRACT_ADDRESS`, `BASE_SEPOLIA_RPC`, `REFID_SECRET`.
   - Implement a real anchor in `transparency/anchor.py` (the current `BaseSepoliaAnchor` is a stub) behind the same interface as `LocalAnchor`.
3. **Kaggle history loader**: read the transactions into the database, push each day's Merkle root with `anchorBatch`. Ask the user for the file or its columns first.
4. **Webhook listener**: verify the service's signature, dedupe on transaction id, store the record and its salt (salts must persist, they are needed for every later proof), then call the bridge. Add a transaction model and persist salts.
5. **Verify endpoint or page**: given a record and salt, rebuild the leaf, call `verify()`, report the block time.
6. Update `docs/TRANSPARENCY.md` and this file.

## Decisions already made
- Record each transaction as its own event (not only daily roots), plus one root per day for the starting history.
- The listener service is the trusted writer. A two-person approval (multisig) comes later.
- Old data is dropped. Test data is a Kaggle transactions file the user's teammate found.

## Open
- Which webhook service: payOS, SePay or Casso. payOS docs do not say whether its webhook covers all bank activity or only payOS links. SePay reports money in and out only for some banks. Confirm bank and service with the client before building the signature check.
- Secret handling for `REFID_SECRET`, private-file encryption at rest.

## Gotchas
- Hardhat compiles with bundled solc-js (`chain/hardhat.config.js`), no compiler download.
- ethers error `HardhatEthersProvider.resolveName is not implemented` means an address argument was not a valid hex address (quotes, spaces, placeholder). Scripts now validate and print the bad value.
- Claude's cloud sandbox cannot reach Base Sepolia RPC or delete GitHub branches. Run on-chain steps on the user's machine.
- A stop hook may warn about "unpushed commits and no remote branch". The cause was a single-branch fetch refspec, since fixed. If it returns, compare `git ls-remote --heads origin <branch>` with `git rev-parse HEAD`.
- Run `pytest` and `npx hardhat test` before each commit.
