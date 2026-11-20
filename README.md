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

## Trạng thái

| Phần | Trạng thái | Bằng chứng |
|---|---|---|
| M0 crawler export | **đã có endpoint** `/api/public/chunks`, chỉ `web` + `post`, API key, phân trang | `qne-poc/backend/app/api/public.py`, `scripts/test_public_chunks.py` |
| M1 schema + sync | **xong** | sync idempotent, xoá chunk crawler đã bỏ, chặn xoá quá 50% |
| M2 retrieval | **xong** | FTS không dấu + pgvector + RRF; confidence từ raw score |
| M3 answer | **xong** | guardrails, compose, citation check, hand-off; test với fake LLM và extractive fallback |
| M4 chat | **xong** | `/api/chat`, `/chat`, cookie ký, rate limit, transcript, feedback, hand-off claim/resolve |
| M5 eval | **chưa xong** | cần dữ liệu crawler thật + bộ 30–40 câu hỏi; xem `docs/HANDOVER.md` |
| Transparency | **prototype** | Merkle + local anchor + proof/verify CLI/API/UI; contract Hardhat; chưa audit |
| PayOS / ngân hàng thật | **chưa có** | không có merchant account/API; mọi thứ liên quan tiền thật vẫn là mock |

## Kiến trúc

```
QNE-knowledge-base (crawler)
  GET /api/public/chunks  (web + post only, X-API-Key)
        │
        ▼
QNE-public-chatbot (repo này)
  Postgres + pgvector  ──  /api/chat  ──  /chat (cookie ký)
        │                         │
        │                         ├─ citations + feedback
        │                         └─ hand-off ticket
        │
  transparency/  ──  Merkle batch  ──  local anchor  ──  chain/ (optional)
```

Crawler và chatbot giữ database riêng. Chatbot không bao giờ nhận credential
của crawler; nó chỉ gọi endpoint đọc công khai.

## Chạy

### 1. Crawler (qne-poc)

Trong `.env` của `qne-poc`:

```env
PUBLIC_API_KEY=<một chuỗi dài ngẫu nhiên>
```

Restart API. Endpoint chỉ trả `web` và `post`; `message`, `meal`, `comment`
luôn bị từ chối.

### 2. Chatbot

```powershell
copy .env.example .env
# điền DATABASE_URL, CRAWLER_URL, CRAWLER_API_KEY (trùng PUBLIC_API_KEY),
# SESSION_SECRET; LLM_API_KEY nếu có.
docker compose up -d --build
```

Nếu chạy local không Docker, dùng `.venv` và `DATABASE_URL_LOCAL`.

### 3. Kéo dữ liệu + embed

```powershell
# trong container
docker compose exec api python -m scripts.sync_now

# hoặc local
.venv\Scripts\python.exe scripts\sync_now.py
.venv\Scripts\python.exe scripts\embed_chunks.py   # cần requirements-embed.txt
```

`sync_now.py` gọi `/api/public/chunks`, ghi `chunks`, và lưu `sync_runs`.
Nếu crawler trả rỗng khi DB đang có dữ liệu, sync dừng trước khi xoá.

### 4. Đăng nhập

Mở `http://localhost:8100/`. Trang đăng nhập bằng token nội bộ. Token được đổi
thành cookie ký `HttpOnly`; JavaScript không giữ token. Tạo user/token ở
`/admin` (tab Users) bằng tài khoản admin.

Các trang:

- `/` hoặc `/chat` — trợ lý
- `/admin` — nhãn dữ liệu/công cụ, user, audit, correction tickets
- `/transparency` — batch, bản ghi, proof, verify

## Vai trò

| Role | Quyền |
|---|---|
| `admin` | tất cả; gán nhãn, tạo user, tạo batch |
| `dev` | đọc tất cả; sửa nội dung; không vào trang admin |
| `finance` | đọc dữ liệu tài chính, bản ghi, tạo/verify proof |
| `volunteer` | đọc dữ liệu mức thấp, nhận hand-off; không xem bản ghi tiền |

Dữ liệu chưa gắn nhãn chỉ `admin` và `dev` thấy. Chat retrieval chạy trong
`user_scope` (Postgres RLS + `app.full_read`/`app.depts`), không dựa vào việc
lọc ở frontend.

## LLM và chế độ trả lời

- Có `LLM_API_KEY` (hoặc `OPENAI_API_KEY`): gọi endpoint OpenAI-compatible
  (`LLM_BASE_URL`, `LLM_MODEL`). Prompt chỉ cho phép trả lời từ `<evidence>`,
  mỗi ý phải có `[id]`; câu trả lời không có citation hợp lệ sẽ bị chặn.
- Không có key: dùng `ExtractiveClient`, trích 2 câu đầu của tối đa 2 nguồn và
  giữ citation. UI ghi rõ “trích xuất nguồn”, không giả là AI.
- Không đủ confidence: trả “chưa tìm thấy”, tạo hand-off.

## Kiểm thử

```powershell
pip install -r requirements-dev.txt -r requirements-chain.txt
.venv\Scripts\python.exe -m pytest -q          # toàn bộ test Python
.venv\Scripts\python.exe scripts\ask.py "Học bổng được giải ngân khi nào?"
cd chain; npm install; npx hardhat test        # contract (cần Node)
```

Test Python dùng SQLite, không gọi mạng, không cần Postgres. Các test
transparency dùng thư mục tạm.

## Giới hạn phải nói thật

- Chưa có dữ liệu crawler thật trong CI; `tests/fixtures/chunks_sample.json`
  là dữ liệu tổng hợp. Chất lượng trả lời chưa được đo trên bộ eval thật.
- Ngưỡng `0.55` / `0.30` được hiệu chỉnh trên fixture nhỏ, chưa phải số liệu
  sản xuất.
- Rate limit là in-process, phù hợp demo một worker; production cần Redis hoặc
  gateway.
- Chưa có job xoá log/transcript theo thời hạn, chưa có Alembic; schema đang
  dùng `create_all` + `ALTER` idempotent.
- Transparency dùng ledger tổng hợp; chưa nối sao kê ngân hàng thật, chưa pin
  IPFS, contract chưa audit, chưa có key custody.
- PayOS/PayPal/ngân hàng chưa được tích hợp. Không được demo như tiền thật.

## Cấu trúc

```
app/
  api/chat.py            # M4 endpoint
  api/session.py         # token -> signed cookie
  api/transparency.py    # batch/proof/verify
  rag/answer.py          # guardrails -> retrieve -> compose -> citation
  rag/compose.py         # LLM + extractive fallback
  rag/guardrails.py      # injection, PII, hand-off rules
  rag/citations.py       # citation + PII check
  rag/retrieve.py        # FTS + vector + RRF
  static/chat.html       # chat UI
  static/transparency.html
transparency/            # Merkle, local anchor, batch/proof/verify
chain/                   # Hardhat contract, tests, deploy/grant scripts
scripts/                 # sync, embed, ask, transparency CLI
docs/                    # plan, decisions, handover, transparency
```

## Tài liệu
- [`AGENTS.md`](AGENTS.md) - working rules, repo map, gotchas
- [`docs/STATE.md`](docs/STATE.md) - current state, next steps
- [`reminder.md`](reminder.md) - who does what
- [`docs/PLAN.md`](docs/PLAN.md) — kế hoạch M0–M5
- [`docs/HANDOVER.md`](docs/HANDOVER.md) — trạng thái thật, blocker, definition of done
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — quyết định kỹ thuật
- [`docs/TRANSPARENCY.md`](docs/TRANSPARENCY.md) — Merkle/anchor, điều chứng minh được
- [`docs/ACCESS.md`](docs/ACCESS.md) — role/label
- [`docs/CORRECTION_TICKETS.md`](docs/CORRECTION_TICKETS.md) — ticket sửa dữ liệu
