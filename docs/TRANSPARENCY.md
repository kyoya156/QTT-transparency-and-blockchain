# Transparency layer (prototype)

Daily batch of ledger records -> salted Merkle root -> write-once anchor. Run locally:

    python scripts/transparency.py batch 2026-11-16
    python scripts/transparency.py prove 2026-11-16 2026-11-16-003 > proof.json
    python scripts/transparency.py verify proof.json

## What it proves
A record (with its salt and sibling path) was part of the batch whose root was anchored on that day, unchanged.
Verification checks against the **anchored** root, never the root inside the proof.

## What it does not prove
- That the record is true. A wrong bank row still gets a valid proof. The source export must be trusted separately.
- That nothing was left out of a batch. Counts are anchored, but completeness depends on the bank export.

## Design choices
- Per-record random salt, so a published leaf hash cannot be guessed from a small set of amounts.
- Public file holds only root, count and leaf hashes. Records and salts stay in the private file.
- Leaf and node hashes use different prefixes; an odd node is promoted, not duplicated.
- `LocalAnchor` is a hash-chained append-only file standing in for a public chain. Same day cannot be anchored twice.

## Not done yet
- Real chain: `BaseSepoliaAnchor` is a stub. Needs a funded test wallet, RPC URL and key custody decision.
- IPFS pinning of the public file.
- Real bank export in place of `ledger.synthetic_day`.
- Verify page and wiring into the dashboard; role rules for who may request a proof.
- Private file encryption at rest.
