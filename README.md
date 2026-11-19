# QTT financial transparency

COS40005 Project A. Donations in and spending out are recorded on a public test chain (Base Sepolia) so anyone can check that a record existed unchanged at a given block time. The chain does not prove a record is true.

Start here: [`AGENTS.md`](AGENTS.md) (rules), [`docs/STATE.md`](docs/STATE.md) (current state, next steps), [`reminder.md`](reminder.md) (who does what).

## Layout

| Path | What |
|---|---|
| `chain/` | Hardhat project: `TransparencyLedger.sol`, tests, deploy and grant scripts. See [`chain/README.md`](chain/README.md). |
| `transparency/` | Python: record shape, salted Merkle batches, local anchor, bridge to the contract (`chain.py`). See [`docs/TRANSPARENCY.md`](docs/TRANSPARENCY.md). |
| `transparency/api.py` | Public verify endpoint: record + salt -> match + block time (`uvicorn transparency.api:app --port 8100`). |
| `scripts/transparency.py` | Local batch / prove / verify CLI. |
| `transparency/listener.py`, `sepay.py`, `sepay_receiver.py`, `scripts/sepay_simulate.py` | Bank feed: SePay webhook -> record -> chain (setup below). |
| `app/`, `mocks/`, other `scripts/` | Internal AI assistant (parked), plus the permission-gated records API `app/api/ledger.py` used by the chain work. |
| `docs/` | `STATE.md` (live state), `explainer.html` + `architecture.drawio` (how the ledger works), `TRANSPARENCY.md`; assistant: `ACCESS.md`, `CORRECTION_TICKETS.md`, `CRAWLER_ENDPOINT.md`, `DECISIONS.md`. |

## Bank feed: SePay -> listener -> chain

A bank account linked to SePay sends every money in and out to our listener, which saves the record + salt and stamps its hash on Base Sepolia. Tested 2026-11-19 with an MB account (direct bank link, in and out both arrive within ~15 s; MB sends no balance).

**1. Keys in `chain/.env`** (never commit, never paste in chat). Already needed: `CONTRACT_ADDRESS`, `LISTENER_KEY`, `REFID_SECRET`. Add the SePay webhook secret:
```powershell
$k = python -c "import secrets;print(secrets.token_hex(32))"
Add-Content -Encoding utf8 chain\.env "SEPAY_WEBHOOK_SECRET=$k"
$k | Set-Clipboard   # paste into SePay in step 4
```
Leave `SEPAY_API_KEY` empty (HMAC is used). `LISTENER_ID_PREFIX` defaults to `TEST-` so test stamps are easy to filter.

**2. Start a service** (window 1). The listener stamps on chain; the test receiver only logs to `transparency_data/sepay-webhooks.jsonl`. Both use port 8200, run one:
```powershell
uvicorn transparency.listener:app --port 8200          # real: database + chain
uvicorn transparency.sepay_receiver:app --port 8200    # log only
```
Listener database: `LISTENER_DB_URL`, else `DATABASE_URL`, else `transparency_data/ledger.db` (git-ignored).

**3. Tunnel** (window 2), so SePay can reach your machine. Install once: `winget install Cloudflare.cloudflared`.
```powershell
New-Item -ItemType File -Force "$env:TEMP\cf-empty.yml" | Out-Null
cloudflared tunnel --config "$env:TEMP\cf-empty.yml" --url http://localhost:8200
```
The empty config avoids an old `~/.cloudflared/config.yml` from another project breaking the quick tunnel ("Rule #1 is matching the hostname ''"). Copy the printed `https://….trycloudflare.com` URL. It changes every restart; update SePay when it does. Keep the window open.

**4. SePay** (free account): link the bank account, then create a webhook:
- URL: `https://….trycloudflare.com/webhook/sepay`
- Events: All (in and out); account: the linked one; content type: JSON
- Security: HMAC-SHA256, paste the secret from step 1. SePay shows only the last 4 characters afterwards; to change it, edit the webhook and set a new one.

**5. Check** (window 3):
```powershell
python scripts/sepay_simulate.py in 2000 --url https://….trycloudflare.com/webhook/sepay
```
Expect `200 {"success":true}`; the listener prints `stamped TEST-SEPAY-9…: sent 0x…` (a permanent test entry on Base Sepolia). `401` means `.env` and SePay/simulator secrets differ, or the service was started before the secret was saved (restart it). Then send a small real transfer in and out of the bank account.

Bank memo codes, donor/recipient ids and the record fields are temporary until the team decides (`reminder.md`).

## Tests

```
pip install -r requirements-dev.txt -r requirements-chain.txt
python -m pytest
cd chain && npm install && npx hardhat test
```

Python tests use fakes and SQLite; no network. On-chain steps need `chain/.env` (git-ignored, never commit keys).

## Parked assistant

Runs with Docker Compose (`copy .env.example .env`, then `docker compose up -d --build`; api on port 8100, db on 5434). Design notes in `docs/DECISIONS.md`, `docs/ACCESS.md`. The public verify endpoint (`uvicorn transparency.api:app --port 8100`) uses the same port; run one or change the port.
