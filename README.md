# QTT financial transparency

COS40005 Project A. Donations in and spending out are recorded on a public test chain (Base Sepolia) so anyone can check that a record existed unchanged at a given block time. The chain does not prove a record is true.

Start here: [`AGENTS.md`](AGENTS.md) (rules), [`docs/STATE.md`](docs/STATE.md) (current state, next steps), [`reminder.md`](reminder.md) (who does what).

## Layout

| Path | What |
|---|---|
| `chain/` | Hardhat project: `TransparencyLedger.sol`, tests, deploy and grant scripts. See [`chain/README.md`](chain/README.md). |
| `transparency/` | Python: record shape, salted Merkle batches, local anchor, bridge to the contract (`chain.py`). See [`docs/TRANSPARENCY.md`](docs/TRANSPARENCY.md). |
| `scripts/transparency.py` | Local batch / prove / verify CLI. |
| `app/`, `mocks/`, other `scripts/`, `docs/PLAN.md` etc. | Internal AI assistant. **Parked** until the chain work is done. |

## Tests

```
pip install -r requirements-dev.txt -r requirements-chain.txt
python -m pytest
cd chain && npm install && npx hardhat test
```

Python tests use fakes and SQLite; no network. On-chain steps need `chain/.env` (git-ignored, never commit keys).

## Parked assistant

Runs with Docker Compose (`copy .env.example .env`, then `docker compose up -d --build`; api on port 8100, db on 5434). History and design in `docs/PLAN.md`, `docs/DECISIONS.md`, `docs/HANDOVER.md`.
