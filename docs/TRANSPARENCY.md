# Transparency layer (Python)

How the pieces fit, for developers. Plain-language version for the team: `docs/explainer.html`. Live state: `docs/STATE.md`.

## Flows
- **Live (built, testnet):** SePay webhook -> `listener.py` (check signature, build record, new salt, save record + salt, reply, stamp `record(refId, leaf)`, save tx hash). Setup: root `README.md`, "Bank feed".
- **History (waiting for Dong's file):** cleaned file -> records -> one salted Merkle root per day -> `anchorBatch(day, root, count)`.
- **Check (built):** `api.py` `POST /verify` with record + salt -> match + block time. Logged-in users: `GET /api/ledger/records/{id}?check_chain=true` (`app/api/ledger.py`).

## Modules
| File | Job |
|---|---|
| `records.py` | record shape (in / out), NFC-normalised text, timezone required |
| `merkle.py` | canonical JSON, salted leaf hash, daily root and proofs |
| `chain.py` | `ref_id` (HMAC), `LedgerClient` (record / verify, idempotent), `BaseSepoliaAnchor`, web3 backend |
| `sepay.py` | SePay webhook auth (HMAC or API key) and parsing |
| `listener.py` | webhook -> database -> chain; record rules are TEMPORARY until the team decides |
| `sepay_receiver.py` | log-only test receiver |
| `api.py` | public verify endpoint |
| `anchor.py`, `batch.py`, `ledger.py` | local prototype: hash-chained file anchor, daily batch, synthetic ledger (`scripts/transparency.py`) |

## What it proves
A record (with its salt) existed unchanged at the block time of its stamp, or was part of the day whose root was anchored.

## What it does not prove
- That the record is true. A wrong bank row still gets a valid stamp.
- That nothing was left out. Completeness depends on the bank feed; the planned nightly check and bank statement import compare against it.

## Design choices
- Per-record random salt, so a leaf cannot be guessed from a small set of amounts.
- Leaf and node hashes use different prefixes; an odd node is promoted, not duplicated.
- Record + salt are saved before the chain write; the stamp uses the in-memory leaf, never a re-read from the database.

## Not done yet
History loader, nightly check, bank statement import, donor receipts, insert-only `ledger_records`, encryption of stored records at rest. See `docs/STATE.md` "Next".
