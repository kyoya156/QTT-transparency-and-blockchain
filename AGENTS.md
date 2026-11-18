# Agent guide (stable rules, read every session)

Any agent (Claude Code, claude.ai, others) working in this repo: read this file, then `docs/STATE.md`. Do the work. Before you stop, update `docs/STATE.md` (see "Update protocol" there).

## Project
COS40005 Project A, financial transparency. Blockchain is the main focus. The chatbot is parked until it works.
Owner: Hung (final decider on technical choices).

## Rules
- NDA: never write a client name or branding in code, docs or commits.
- Never ask for, print or commit a private key. Keys live only in `chain/.env` (git-ignored). Use throwaway test wallets.
- The chain proves a record existed unchanged at a block time. It does not prove the record is true. Never claim more.
- Replies short. After a change, list the files touched.
- Run `pytest` and `cd chain && npx hardhat test` before each commit.
- Windows + PowerShell on the owner's machine. Local projects live in `D:\local-projects`; keep `node_modules` out of OneDrive.

## Map
- `chain/`: Hardhat project, `TransparencyLedger.sol`, tests, `scripts/deploy.js`, `scripts/grant-recorder.js`.
- `transparency/`: Python Merkle, synthetic ledger, anchors, batch. CLI: `scripts/transparency.py`.
- `app/`, `docs/`: internal assistant (parked) and its docs.

## Gotchas
- Hardhat compiles with bundled solc-js (`chain/hardhat.config.js`); no compiler download.
- ethers `resolveName is not implemented` = an address argument was not a valid hex address (quotes, spaces, placeholder).
- Claude's cloud sandbox cannot reach Base Sepolia RPC or delete GitHub branches. On-chain steps run on the owner's machine.
- A stop hook may warn about unpushed commits with no remote branch. Cause was a single-branch fetch refspec, since fixed. Compare `git ls-remote --heads origin <branch>` with `git rev-parse HEAD` before believing it.
