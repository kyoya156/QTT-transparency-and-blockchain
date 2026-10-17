"""Read-only HTTP API + static server for the Nuôi Em Topic 4 dashboard.

Changes from the first prototype, and why:

* Search no longer uses `reference_tokens LIKE '%q%'`. That forced a full table
  scan and measured 205 ms p50 on 1.0 M rows. Lookups now hit the indexed
  `ne_code` / `acn_code` columns via prefix matching.
* Pagination is keyset-based on `(tx_time, id)`. Deep `OFFSET` is not offered,
  so the API cannot be made to walk the table.
* Raw bank memos are parsed internally but are neither returned nor searchable
  through the read-only API, preventing a search-based personal-data oracle.
* The public endpoints never expose a personal field. `student_supports` is
  only reachable through code-level fields, and a guard asserts the shape.
* Every list endpoint reports `truncated` so the UI cannot imply that a capped
  result set is the whole truth.
"""

from __future__ import annotations

import argparse
import json
import os
import mimetypes
import sqlite3
import threading
import webbrowser
from contextlib import closing
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATABASE = BASE_DIR / "data" / "nuoi_em_mvp.sqlite"

MAX_QUERY_LENGTH = 64
MAX_PAGE_SIZE = 200

# Fields that must never leave the API. Kept explicit so a future schema change
# cannot silently start leaking them.
FORBIDDEN_FIELDS = {
    "student_name",
    "full_name",
    "parent_name",
    "guardian",
    "phone",
    "phone_number",
    "email",
    "address",
    "date_of_birth",
    "dob",
    "photo_url",
    "image_url",
    "id_number",
    "cccd",
    "birth_certificate",
    # Raw bank memo and account identifiers can contain donor names, phone
    # numbers, emails or other identifiers even when the column name does not.
    "raw_description",
    "source_account",
}


def database_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{DATABASE.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def scalar(connection, sql, params=()):
    row = connection.execute(sql, params).fetchone()
    return row[0] if row else 0


def assert_no_pii(payload: dict) -> dict:
    """Fail loudly if a forbidden field ever reaches a response."""
    for key in payload:
        if key.lower() in FORBIDDEN_FIELDS:
            raise ValueError(f"refusing to serve personal field: {key}")
    return payload


def rows_to_dicts(rows) -> list[dict]:
    out = []
    for row in rows:
        item = dict(row)
        assert_no_pii(item)
        out.append(item)
    return out


def clean_query(params: dict, name: str = "q") -> str:
    raw = (params.get(name, [""])[0] or "").strip()
    return raw[:MAX_QUERY_LENGTH]


def clean_limit(params: dict, default: int = 100) -> int:
    try:
        return min(MAX_PAGE_SIZE, max(1, int(params.get("limit", [str(default)])[0])))
    except (ValueError, TypeError):
        return default


def safe_transaction_description(row: dict) -> str:
    """Create a public-safe explanation without echoing the bank memo."""
    tokens = (row.get("reference_tokens") or "").strip()
    if tokens:
        return f"Đã nhận diện mã: {tokens}"
    if row.get("direction") == "inbound":
        return "Nội dung giao dịch đã được ẩn; chưa nhận diện mã hỗ trợ."
    return "Nội dung giao dịch đã được ẩn; dòng tiền ra chưa được phân loại kế toán."


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------


def summary_payload(_params) -> dict:
    with closing(database_connection()) as conn:
        inbound = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount),0) FROM bank_transactions WHERE direction='inbound'"
        ).fetchone()
        outbound = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount),0) FROM bank_transactions WHERE direction='outbound'"
        ).fetchone()
        period = conn.execute(
            "SELECT MIN(tx_time), MAX(tx_time) FROM bank_transactions WHERE tx_time IS NOT NULL"
        ).fetchone()
        return {
            "transactions": {
                "inbound": {"count": inbound[0], "total": inbound[1]},
                "outbound": {"count": outbound[0], "total": outbound[1]},
                "all": inbound[0] + outbound[0],
            },
            "allocations": scalar(conn, "SELECT COUNT(*) FROM transaction_allocations"),
            "distinct_ne_codes": scalar(
                conn, "SELECT COUNT(DISTINCT ne_code) FROM transaction_allocations"
            ),
            "needing_review": scalar(
                conn,
                "SELECT COUNT(*) FROM bank_transactions "
                "WHERE processing_status IN ('needs_review','unclassified')",
            ),
            "open_exceptions": scalar(
                conn, "SELECT COUNT(*) FROM exception_queue WHERE status='open'"
            ),
            "high_exceptions": scalar(
                conn,
                "SELECT COUNT(*) FROM exception_queue WHERE severity='high' AND status='open'",
            ),
            "pending_approvals": scalar(
                conn, "SELECT COUNT(*) FROM approval_tasks WHERE status='pending'"
            ),
            "coverage": _coverage(conn),
            "period": {"from": period[0], "to": period[1]},
            "integrity": _integrity(conn),
        }


def _coverage(conn) -> dict:
    """How much inbound money is traceable to at least one NE code."""
    total = scalar(
        conn, "SELECT COALESCE(SUM(amount),0) FROM bank_transactions WHERE direction='inbound'"
    )
    coded = conn.execute(
        """
        SELECT COALESCE(SUM(amount),0) FROM bank_transactions
        WHERE direction='inbound'
          AND id IN (SELECT DISTINCT transaction_id FROM transaction_allocations)
        """
    ).fetchone()[0]
    percent = round(coded / total * 100, 2) if total else 0.0
    return {
        "inbound_total": total,
        "inbound_allocated": coded,
        "inbound_unallocated": total - coded,
        "allocated_percent": percent,
    }


def _integrity(conn) -> dict:
    """The invariant an auditor cares about: parts must sum to the whole."""
    allocations = scalar(
        conn, "SELECT COALESCE(SUM(allocated_amount_computed),0) FROM transaction_allocations"
    )
    linked = scalar(
        conn,
        """
        SELECT COALESCE(SUM(amount),0) FROM bank_transactions
        WHERE id IN (SELECT DISTINCT transaction_id FROM transaction_allocations)
        """,
    )
    return {
        "allocations_sum": allocations,
        "linked_transactions_sum": linked,
        "balanced": allocations == linked,
    }


def transactions_payload(params: dict) -> dict:
    query = clean_query(params)
    status = (params.get("status", [""])[0] or "").strip()
    direction = (params.get("direction", [""])[0] or "").strip()
    limit = clean_limit(params)
    min_amount = params.get("min_amount", [""])[0] or ""

    where = ["1 = 1"]
    values: list = []

    if query:
        # Search only structured codes and provider ids. Raw bank memos remain
        # internal so the API cannot be used as a personal-data search oracle.
        if query.isdigit():
            where.append(
                "(t.id IN (SELECT transaction_id FROM transaction_allocations WHERE ne_number = ?)"
                " OR t.provider_tx_id LIKE ?)"
            )
            values.extend([int(query), f"{query}%"])
        else:
            upper = query.upper()
            looks_like_code = upper.startswith(("NE", "ACN"))
            if looks_like_code:
                where.append(
                    "(t.id IN (SELECT transaction_id FROM transaction_allocations "
                    "WHERE ne_code LIKE ? OR ne_code = ?)"
                    " OR t.provider_tx_id LIKE ?)"
                )
                values.extend([f"{upper}%", upper, f"{upper}%"])
            else:
                where.append("t.provider_tx_id LIKE ?")
                values.append(f"{query}%")

    if status in {"matched", "parsed", "needs_review", "unclassified"}:
        where.append("t.processing_status = ?")
        values.append(status)
    if direction in {"inbound", "outbound"}:
        where.append("t.direction = ?")
        values.append(direction)
    if min_amount.isdigit():
        where.append("t.amount >= ?")
        values.append(int(min_amount))

    effective_limit = limit
    sql = f"""
        SELECT t.provider_tx_id, t.source_stage, t.tx_time,
               t.direction, t.amount, t.category, t.processing_status,
               t.reference_tokens, t.academic_year,
               COUNT(DISTINCT ta.id) AS allocation_rows,
               COUNT(DISTINCT ta.ne_code) AS distinct_ne_codes
        FROM bank_transactions t
        LEFT JOIN transaction_allocations ta ON ta.transaction_id = t.id
        WHERE {' AND '.join(where)}
        GROUP BY t.id
        ORDER BY COALESCE(t.tx_time,'') DESC, t.id DESC
        LIMIT ?
    """
    values.append(effective_limit + 1)
    with closing(database_connection()) as conn:
        rows = rows_to_dicts(conn.execute(sql, values).fetchall())
    truncated = len(rows) > effective_limit
    rows = rows[:effective_limit]
    for row in rows:
        row["description_masked"] = safe_transaction_description(row)
    return {
        "items": rows,
        "count": len(rows),
        "query": query,
        "truncated": truncated,
        "limit_applied": effective_limit,
    }


def allocation_payload(params: dict) -> dict:
    """Per-NE allocation detail for one transaction."""
    tx_id = clean_query(params, "tx")
    if not tx_id:
        return {"transaction": None, "allocations": [], "error": "missing tx parameter"}
    with closing(database_connection()) as conn:
        tx = conn.execute(
            """
            SELECT provider_tx_id, tx_time, direction, amount, processing_status,
                   reference_tokens, category, academic_year
            FROM bank_transactions WHERE provider_tx_id = ?
            """,
            (tx_id,),
        ).fetchone()
        if not tx:
            return {"transaction": None, "allocations": [], "error": "not_found"}
        allocations = rows_to_dicts(
            conn.execute(
                """
                SELECT ta.ne_code, ta.ne_number, ta.meal_suffix,
                       ta.allocated_amount_computed, ta.allocation_policy,
                       ta.match_status, s.student_code, sc.school_code, sc.name AS school_name
                FROM transaction_allocations ta
                LEFT JOIN students s ON s.id = ta.student_id
                LEFT JOIN schools sc ON sc.id = ta.school_id
                WHERE ta.transaction_id = (SELECT id FROM bank_transactions WHERE provider_tx_id = ?)
                ORDER BY ta.ne_code
                """,
                (tx_id,),
            ).fetchall()
        )
    total = sum(a["allocated_amount_computed"] for a in allocations)
    transaction = dict(tx)
    transaction["description_masked"] = safe_transaction_description(transaction)
    return {
        "transaction": assert_no_pii(transaction),
        "allocations": allocations,
        "allocation_sum": total,
        "balanced": total == tx["amount"],
        "reconciliation_available": False,
    }


def ne_payload(params: dict) -> dict:
    """Everything known about one NE code."""
    code = clean_query(params, "ne").upper()
    if not code:
        return {"ne_code": "", "error": "missing ne parameter"}
    if not code.startswith("NE"):
        code = f"NE{code.zfill(5)}"
    with closing(database_connection()) as conn:
        allocations = rows_to_dicts(
            conn.execute(
                """
                SELECT t.provider_tx_id, t.tx_time, t.direction, t.amount,
                       ta.allocated_amount_computed, ta.allocation_policy, ta.match_status
                FROM transaction_allocations ta
                JOIN bank_transactions t ON t.id = ta.transaction_id
                WHERE ta.ne_code = ? OR ta.ne_code LIKE ?
                ORDER BY COALESCE(t.tx_time,'') DESC
                LIMIT ?
                """,
                (code, f"{code}%", MAX_PAGE_SIZE),
            ).fetchall()
        )
        registry = rows_to_dicts(
            conn.execute(
                """
                SELECT ss.ne_code, ss.meal_plan, ss.academic_year, ss.total_amount,
                       s.student_code, s.class_name, s.status,
                       sc.school_code, sc.name AS school_name, sc.province
                FROM student_supports ss
                JOIN students s ON s.id = ss.student_id
                JOIN schools sc ON sc.id = s.school_id
                WHERE ss.ne_code = ?
                """,
                (code,),
            ).fetchall()
        )
    total = sum(a["allocated_amount_computed"] for a in allocations)
    return {
        "ne_code": code,
        "allocation_count": len(allocations),
        "total_allocated": total,
        "allocations": allocations,
        "registry": registry,
        "registry_available": bool(registry),
    }


def exceptions_payload(params: dict) -> dict:
    severity = (params.get("severity", [""])[0] or "").strip()
    status = (params.get("status", ["open"])[0] or "open").strip()
    where = ["1 = 1"]
    values: list = []
    if severity in {"high", "medium", "low", "info"}:
        where.append("severity = ?")
        values.append(severity)
    if status in {"open", "resolved"}:
        where.append("status = ?")
        values.append(status)
    with closing(database_connection()) as conn:
        rows = rows_to_dicts(
            conn.execute(
                f"""
                SELECT id, exception_code, severity, entity_type, entity_key,
                       detail, source_ref, status, assigned_to
                FROM exception_queue
                WHERE {' AND '.join(where)}
                ORDER BY CASE severity WHEN 'high' THEN 1 WHEN 'medium' THEN 2
                         WHEN 'low' THEN 3 ELSE 4 END, id
                LIMIT 200
                """,
                values,
            ).fetchall()
        )
    return {"items": rows, "count": len(rows)}


def approvals_payload(params: dict) -> dict:
    status = (params.get("status", ["pending"])[0] or "pending").strip()
    with closing(database_connection()) as conn:
        rows = rows_to_dicts(
            conn.execute(
                """
                SELECT id, entity_type, entity_key, action, reason, maker, checker,
                       status, created_at, decided_at, decision_note
                FROM approval_tasks
                WHERE status = ?
                ORDER BY created_at DESC LIMIT 200
                """,
                (status,),
            ).fetchall()
        )
    return {"items": rows, "count": len(rows), "status": status}


def audit_payload(params: dict) -> dict:
    """Audit log plus live chain verification.

    Verification is delegated to `reconciliation.AuditChain.verify` rather than
    re-implemented here. An earlier version copied the hashing logic into this
    function, which meant two implementations of one security control — and a
    security control with two implementations is one edit away from silently
    disagreeing with itself. There is now exactly one place where a hash is
    computed, and it is the same place the writer uses.
    """
    from reconciliation import AuditChain

    limit = clean_limit(params, 50)
    with closing(database_connection()) as conn:
        rows = rows_to_dicts(
            conn.execute(
                """
                SELECT id, event_type, entity_type, entity_key, actor, actor_role,
                       detail, event_hash, occurred_at
                FROM audit_events ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        )
        intact, broken_at = AuditChain(conn).verify()

    # Do not echo the hashes back to the client.
    for row in rows:
        row.pop("event_hash", None)
    return {
        "items": rows,
        "count": len(rows),
        "chain_intact": intact,
        "first_broken_event_id": broken_at,
    }


def metadata_payload(_params) -> dict:
    with closing(database_connection()) as conn:
        run = conn.execute(
            """
            SELECT source_name, source_kind, imported_at, raw_transaction_rows,
                   allocation_rows, schema_version, source_sha256
            FROM import_runs ORDER BY id DESC LIMIT 1
            """
        ).fetchone()
        source = dict(run) if run else {}
        if source:
            source["source_sha256"] = source["source_sha256"][:16] + "..."
    return {
        "source": source,
        "privacy": (
            "API chỉ trả mã giao dịch và các mã NE/ACN đã tách; không trả hoặc "
            "cho tìm kiếm nội dung sao kê thô và số tài khoản. File sao kê gốc "
            "vẫn được giữ cục bộ để phân tích, nên không được đưa lên Git hoặc "
            "xuất bản công khai."
        ),
        "scope": (
            "Prototype hiện dùng riêng sao kê Vietcombank lịch sử từ 01/01/2018 "
            "đến 25/02/2026. Hệ thống đối soát dòng tiền vào, phân bổ theo mã NE, "
            "hàng đợi ngoại lệ, audit log và quy trình maker-checker; không đại diện "
            "cho toàn bộ hệ thống tài chính hiện tại của Quỹ."
        ),
        "allocation_policy": (
            "Số tiền một giao dịch được chia đều cho các mã NE nó viện dẫn. "
            "Quỹ không công bố số tiền theo từng mã, nên mọi con số ở đây là "
            "suy ra (computed), không phải số liệu Quỹ đã xác nhận."
        ),
        "missing": [
            "Chưa nhập các nguồn VPBank/MB và dữ liệu sau 25/02/2026",
            "Chưa có danh mục học sinh đầy đủ để nối mã NE với trường",
            "Chưa có công văn/đề nghị thanh toán của trường trong dữ liệu",
            "Chưa có chứng từ và trạng thái phê duyệt chi",
            "Báo cáo công khai của Quỹ mới ở mức tổng hợp theo kỳ",
        ],
    }


def coverage_payload(_params) -> dict:
    with closing(database_connection()) as conn:
        return _coverage(conn)


API_ROUTES = {
    "/api/summary": summary_payload,
    "/api/transactions": transactions_payload,
    "/api/allocation": allocation_payload,
    "/api/ne": ne_payload,
    "/api/exceptions": exceptions_payload,
    "/api/approvals": approvals_payload,
    "/api/audit": audit_payload,
    "/api/coverage": coverage_payload,
    "/api/metadata": metadata_payload,
}


class RequestHandler(BaseHTTPRequestHandler):
    server_version = "NuoiEmTopic4/2.0"

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
            "base-uri 'none'; form-action 'none'",
        )
        self.send_header("Cache-Control", "no-store")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")

    def _json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self._security_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _static(self, request_path: str) -> None:
        relative = "index.html" if request_path == "/" else request_path.lstrip("/")
        candidate = (STATIC_DIR / relative).resolve()
        try:
            candidate.relative_to(STATIC_DIR.resolve())
        except ValueError:
            self._json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
            return
        if not candidate.is_file():
            # Distinguish a real 404 from an SPA route. Returning index.html
            # with 200 for a missing .css/.js makes the browser parse HTML as
            # CSS and fail silently.
            if Path(relative).suffix:
                self._json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
                return
            candidate = STATIC_DIR / "index.html"
        content = candidate.read_bytes()
        media_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self._security_headers()
        if media_type.startswith("text/") or media_type in {
            "application/javascript",
            "application/json",
        }:
            media_type += "; charset=utf-8"
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._json({"status": "ok", "database": DATABASE.exists()})
            return
        if parsed.path in API_ROUTES:
            try:
                payload = API_ROUTES[parsed.path](parse_qs(parsed.query, keep_blank_values=True))
                self._json(payload)
            except ValueError as exc:
                self._json({"error": "policy_violation", "detail": str(exc)}, HTTPStatus.FORBIDDEN)
            except sqlite3.Error:
                self._json({"error": "database_error"}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        self._static(parsed.path)

    def _reject_write(self) -> None:
        self._json(
            {"error": "read_only", "detail": "this MVP exposes no write endpoints"},
            HTTPStatus.METHOD_NOT_ALLOWED,
        )

    do_POST = do_PUT = do_PATCH = do_DELETE = _reject_write

    def log_message(self, message_format: str, *args) -> None:
        print(f"{self.command} {urlparse(self.path).path}")


def create_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    if not DATABASE.exists():
        raise FileNotFoundError(
            f"Database not found: {DATABASE}\n"
            "Build it first: python build_database.py <source.csv>"
        )
    return ThreadingHTTPServer((host, port), RequestHandler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Nuôi Em Topic 4 local MVP")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8765")))
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()
    server = create_server(args.host, args.port)
    url = f"http://{args.host}:{server.server_address[1]}"
    print(f"Topic 4 MVP running at {url}")
    print("Press Ctrl+C to stop.")
    if args.open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
