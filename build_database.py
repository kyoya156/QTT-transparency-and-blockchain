"""Header-driven ingestion for Nuôi Em data.

The previous version read fixed cell coordinates (`ws.cell(row, 15)`,
`range(4, 14)`, ...). That is the single most dangerous pattern in a financial
pipeline: if a teacher adds one row or a mentor inserts one column, the import
does not fail -- it silently reads the wrong field and the numbers stay
plausible. For a system whose whole purpose is auditability, silent corruption
is worse than a crash.

This module locates columns by their header text instead. If a required header
is missing the import refuses to run.

Two source shapes are supported, both taken from real files:

1. Published statement CSV/XLSX, exactly as the fund publishes it on its own
   site: STT | Date+Doc No | Chi | Thu | Balance | Detail | Năm | Tháng
   Verified against the live sheet (238,173 rows, 2018-2026).

2. Mentor workbook (`mock data.xlsx`) -- stacked blocks in one sheet, located
   by scanning for their header rows.
"""

from __future__ import annotations

import csv
import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from parsers import parse_amount, parse_reference
from reconciliation import (
    MATCH_AMBIGUOUS,
    MATCH_MATCHED,
    MATCH_NE_UNKNOWN,
    AuditChain,
    build_exceptions,
    idempotency_key,
    infer_unit_price,
    split_amount,
)
from schema import ROLE_SEED, SCHEMA, SCHEMA_VERSION


def norm_header(value) -> str:
    """Normalize a header cell for matching."""
    if value is None:
        return ""
    text = str(value).strip().lower().replace("\n", " ")
    return re.sub(r"\s+", " ", text)


_ACCENT_TABLE = str.maketrans(
    "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ",
    "aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyyd",
)


def slug(value) -> str:
    """ASCII-fold a Vietnamese header so 'Nội dung chi tiết' matches 'noi dung'."""
    return norm_header(value).translate(_ACCENT_TABLE)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def clean_text(raw):
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.upper() in {"#N/A", "#REF!", "NULL", "NONE", "-", "N/A"}:
        return None
    return text


def iso_value(raw):
    """Parse a date cell into an ISO date.

    Vietnamese statements are dd/mm/yyyy. Two traps live in this cell, and both
    were measured on the real published file:

    * The sheet packs a newline-separated pair into ONE cell:
      "08/02/2018\\nYG61.000093" (date, then document number). The second line
      is never part of the date.
    * Some readers normalise that newline to a space, so the same cell arrives
      as "31/12/2020 9774.0008477811". Here the trailing token is the account
      BALANCE, not a time: 65,654 of 238,173 real rows looked like this, and
      storing the whole string put 27.6% of transactions at a nonsense date
      that sorted them into the wrong place.

    So: take the leading date token and discard whatever trails it, whether it
    is separated by a newline or a space. Only the date is kept; the document
    number is already kept in its own column, and the balance is not ours.

    Falls back to the raw first token when nothing parses, so a future format
    shows up as visibly odd data rather than being silently nulled.
    """
    if isinstance(raw, datetime):
        return raw.isoformat(sep=" ")
    if isinstance(raw, date):
        return raw.isoformat()
    text = clean_text(raw)
    if not text:
        return None
    # Split on newline first (the fresh-from-Google-Sheets shape), then on
    # whitespace (the round-tripped-through-CSV shape). Both yield the date.
    first_token = re.split(r"[\s]+", text.split("\n")[0].strip())[0]
    for pattern in (
        "%d/%m/%Y",
        "%d/%m/%y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d-%m-%y",
    ):
        try:
            return datetime.strptime(first_token, pattern).isoformat(sep=" ")
        except ValueError:
            continue
    for pattern in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text.split("\n")[0].strip(), pattern).isoformat(sep=" ")
        except ValueError:
            continue
    return first_token


@dataclass
class ColumnMap:
    """Resolved column indices for one table block."""

    index: dict[str, int]

    def get(self, *names, required=False):
        for name in names:
            if name in self.index:
                return self.index[name]
        if required:
            raise KeyError(f"missing required column: {names}")
        return None

    def cell(self, row, *names, required=False):
        idx = self.get(*names, required=required)
        if idx is None or idx >= len(row):
            return None
        return row[idx]


HEADER_ALIASES = {
    "stt": {"stt", "so tt", "#"},
    "date_doc": {"ngay/ tnx date/ so ct/ doc no", "ngay hieu luc", "ngay", "date"},
    "debit": {"chi", "ghi no", "debit"},
    "credit": {"thu", "ghi co", "credit"},
    "balance": {"so du/ balance", "so du", "balance"},
    "detail": {
        "noi dung chi tiet/ transactions in detail",
        "noi dung giao dich",
        "noi dung",
        "detail",
        "description",
    },
    "year": {"nam", "year"},
    "month": {"thang", "month"},
    "tx_id": {"ma gd", "ma giao dich", "so ct", "provider_tx_id", "transaction id"},
    # Mentor-workbook specific headers.
    "acn": {"acn", "ma acn", "ma nha tai tro"},
    "ne": {"ne", "ma ne", "ma nhan dien"},
    "amount": {"amount", "so tien", "so tien (vnd)"},
}


def find_header_matches(header_row: list) -> dict[str, int]:
    """Map our logical fields onto indices in a header row."""
    found: dict[str, int] = {}
    for idx, cell in enumerate(header_row):
        key = norm_header(cell)
        folded = slug(cell)
        for field, aliases in HEADER_ALIASES.items():
            if field in found:
                continue
            if key in aliases or folded in aliases:
                found[field] = idx
    return found


def locate_blocks(rows: list[list], *, max_scan: int = 2000) -> dict[str, tuple[int, dict[str, int]]]:
    """Find each table block by its header row.

    Only the top of the sheet is scanned. A header row sits above the data by
    definition, and scanning all 238k body rows to find one cost 77 s of the
    import's 121 s budget -- for zero benefit. `max_scan` is a guard against a
    pathological layout, not a data limit.

    Note: do NOT pre-filter on row width. A header row can legitimately be as
    wide as its table, and a width guard silently skips the very row we need.
    """
    blocks: dict[str, tuple[int, dict[str, int]]] = {}
    for idx, row in enumerate(rows[:max_scan]):
        if not any(isinstance(c, str) and c.strip() for c in row):
            continue
        matches = find_header_matches(row)
        has_amount = "debit" in matches or "credit" in matches
        if has_amount and "detail" in matches and "statement" not in blocks:
            blocks["statement"] = (idx, matches)
        elif "tx_id" in matches and "processed" not in blocks:
            blocks["processed"] = (idx, matches)
        if "statement" in blocks and "processed" in blocks:
            break
    return blocks


# --------------------------------------------------------------------------
# Statement ingestion (the fund's own published format)
# --------------------------------------------------------------------------


def ingest_statement_rows(
    conn: sqlite3.Connection,
    rows: list[list],
    *,
    header_index: int,
    mapping: dict[str, int],
    source_name: str,
    source_account: str | None,
    default_year: str | None = "2026-2027",
    source_ref_prefix: str = "statement",
    known_ne_codes: set[str] | None = None,
    registry_loaded: bool | None = None,
) -> dict:
    """Load a statement block into bank_transactions + transaction_allocations.

    Performance note: the first version issued two `execute()` calls per row.
    On the fund's real 238k-row statement that cost ~230 s, almost all of it
    SQLite round-trip overhead. We now accumulate rows and flush with
    `executemany`, which is the difference between an import a volunteer will
    tolerate and one they will not run.
    """
    if known_ne_codes is None:
        known_ne_codes = {
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT ne_code FROM student_supports WHERE ne_code IS NOT NULL"
            )
        }
    if registry_loaded is None:
        registry_loaded = bool(known_ne_codes)

    donor_by_acn = {r[0]: r[1] for r in conn.execute("SELECT acn_code, id FROM donors")}

    audit = AuditChain(conn)
    transactions: list[dict] = []
    allocations: list[dict] = []
    tx_params: list[tuple] = []
    pending_allocations: list[tuple] = []
    unit_price_hits = 0
    seen_keys: set[str] = set()
    duplicate_rows = 0
    seen_tx_ids: set[str] = set()
    col = ColumnMap(mapping)

    for offset, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
        if not any(str(c).strip() for c in row):
            continue

        debit = parse_amount(col.cell(row, "debit"))
        credit = parse_amount(col.cell(row, "credit"))
        if debit == 0 and credit == 0:
            continue

        direction = "inbound" if credit > 0 else "outbound"
        amount = credit if direction == "inbound" else debit
        if amount <= 0:
            continue

        detail = clean_text(col.cell(row, "detail")) or ""
        raw_date = col.cell(row, "date_doc")
        tx_time = iso_value(raw_date)
        year_cell = clean_text(col.cell(row, "year"))
        month_cell = clean_text(col.cell(row, "month"))
        academic_year = default_year
        if year_cell and month_cell and str(year_cell).isdigit() and str(month_cell).isdigit():
            month = int(month_cell)
            if 1 <= month <= 12:
                # School year runs Sep -> Aug.
                start = int(year_cell) if month >= 9 else int(year_cell) - 1
                academic_year = f"{start}-{start + 1}"

        doc_no = None
        if isinstance(raw_date, str):
            parts = [p.strip() for p in raw_date.split("\n") if p.strip()]
            if len(parts) > 1:
                doc_no = parts[1]
        explicit_id = clean_text(col.cell(row, "tx_id"))
        provider_tx_id = explicit_id or doc_no or f"AUTO-{source_name}-{offset}"

        # The published sheet reuses document numbers, so a bare doc number is
        # not unique. Disambiguate deterministically with the row position.
        dedupe_id = provider_tx_id
        if dedupe_id in seen_tx_ids:
            dedupe_id = f"{provider_tx_id}#{offset}"
        seen_tx_ids.add(dedupe_id)

        balance = parse_amount(col.cell(row, "balance")) or None
        # Some published rows legitimately reuse the same bank document number,
        # timestamp and amount. The deterministic row-disambiguated id keeps
        # those rows while still producing the same key on a re-import of the
        # same source file.
        key = idempotency_key(source_name, dedupe_id, amount, tx_time)
        if key in seen_keys:
            duplicate_rows += 1
            continue
        seen_keys.add(key)

        parsed = parse_reference(detail)
        tokens = " ".join(sorted(set(parsed.ne_codes + parsed.acn_codes)))

        if parsed.ne_references or parsed.acn_codes:
            status = "matched"
        elif direction == "inbound" and not detail.strip():
            status = "unclassified"
        elif direction == "inbound":
            status = "needs_review"
        else:
            status = "parsed"

        # A bank credit/debit is not automatically accounting revenue/expense.
        # Keep the import neutral until supporting documents classify it.
        category = (
            "Dòng tiền vào (chưa phân loại kế toán)"
            if direction == "inbound"
            else "Dòng tiền ra (chưa phân loại kế toán)"
        )
        tx_params.append(
            (
                dedupe_id,
                key,
                source_account,
                tx_time,
                direction,
                amount,
                balance,
                category,
                status,
                tokens,
                detail,
                academic_year,
            )
        )
        transactions.append(
            {
                "provider_tx_id": dedupe_id,
                "amount": amount,
                "direction": direction,
                "processing_status": status,
                "source_ref": f"{source_ref_prefix}!{offset}",
            }
        )

        distinct = parsed.distinct_ne_codes
        amounts, policy = split_amount(amount, len(distinct))
        if infer_unit_price(amount, len(distinct)):
            unit_price_hits += 1

        for position, ne_code in enumerate(distinct):
            match_status = MATCH_MATCHED
            if ne_code not in known_ne_codes:
                match_status = MATCH_NE_UNKNOWN if parsed.acn_codes else MATCH_AMBIGUOUS
            ref = next(r for r in parsed.ne_references if r.code == ne_code)
            donor_id = donor_by_acn.get(parsed.acn_codes[0]) if parsed.acn_codes else None
            pending_allocations.append(
                (
                    dedupe_id,
                    ne_code,
                    ref.number,
                    ref.meal,
                    donor_id,
                    amounts[position],
                    policy,
                    match_status,
                    offset,
                )
            )
            allocations.append(
                {
                    "provider_tx_id": dedupe_id,
                    "ne_code": ne_code,
                    "allocated_amount_computed": amounts[position],
                    "match_status": match_status,
                }
            )

    # Bulk insert transactions, then resolve their ids in one query.
    conn.executemany(
        """
        INSERT OR IGNORE INTO bank_transactions
            (provider_tx_id, idempotency_key, source_stage, source_account, tx_time,
             direction, amount, balance_after, category, subcategory,
             processing_status, reference_tokens, raw_description, academic_year)
        VALUES (?, ?, 'published_statement', ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)
        """,
        tx_params,
    )

    tx_id_by_provider: dict[str, int] = {}
    for provider_id, tx_id in conn.execute(
        "SELECT provider_tx_id, id FROM bank_transactions"
    ):
        tx_id_by_provider[provider_id] = tx_id

    alloc_params = [
        (
            tx_id_by_provider.get(p[0]),
            p[1],
            p[2],
            p[3],
            p[4],
            p[5],
            p[6],
            p[7],
            p[8],
        )
        for p in pending_allocations
        if tx_id_by_provider.get(p[0]) is not None
    ]
    conn.executemany(
        """
        INSERT OR IGNORE INTO transaction_allocations
            (transaction_id, ne_code, ne_number, meal_suffix, donor_id,
             allocated_amount_computed, allocation_policy, match_status, source_row)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        alloc_params,
    )

    exceptions = build_exceptions(
        transactions, allocations, known_ne_codes, registry_loaded=registry_loaded
    )
    conn.executemany(
        """
        INSERT INTO exception_queue
            (exception_code, severity, entity_type, entity_key, detail, source_ref)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (
                exc["exception_code"],
                exc["severity"],
                exc["entity_type"],
                exc["entity_key"],
                exc["detail"],
                exc["source_ref"],
            )
            for exc in exceptions
        ],
    )

    audit.record(
        "statement_ingested",
        actor="import_pipeline",
        actor_role="finance_officer",
        entity_type="import_run",
        entity_key=source_name,
        detail={
            "rows_loaded": len(transactions),
            "allocations": len(allocations),
            "duplicates_skipped": duplicate_rows,
            "exceptions": len(exceptions),
            "unit_price_tier_hits": unit_price_hits,
        },
    )

    return {
        "transactions": len(transactions),
        "allocations": len(allocations),
        "duplicates_skipped": duplicate_rows,
        "exceptions": len(exceptions),
        "unit_price_tier_hits": unit_price_hits,
        "audit_head": audit.head,
    }


def ingest_statement_file(
    conn: sqlite3.Connection,
    path: Path,
    *,
    source_account: str | None = None,
    default_year: str | None = "2026-2027",
) -> dict:
    """Load a published-statement CSV (or an XLSX sheet in that shape)."""
    rows = read_rows(path)
    blocks = locate_blocks(rows)
    if "statement" not in blocks:
        raise ValueError(
            f"Could not find a statement header in {path.name}. "
            f"Detected blocks: {sorted(blocks)}"
        )
    header_index, mapping = blocks["statement"]
    return ingest_statement_rows(
        conn,
        rows,
        header_index=header_index,
        mapping=mapping,
        source_name=path.name,
        source_account=source_account,
        default_year=default_year,
    )


def read_rows(path: Path) -> list[list]:
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8", errors="ignore", newline="") as handle:
            return list(csv.reader(handle))
    import openpyxl

    workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
    worksheet = workbook[workbook.sheetnames[0]]
    rows = [list(r) for r in worksheet.iter_rows(values_only=True)]
    workbook.close()
    return rows


def ingest_mentor_workbook(conn: sqlite3.Connection, path: Path) -> dict:
    """Read the mentor's workbook without hardcoding a single cell coordinate."""
    rows = read_rows(path)

    header_index = None
    mapping: dict[str, int] = {}
    for idx, row in enumerate(rows):
        matches = find_header_matches(row)
        if "tx_id" in matches or ("acn" in matches and "ne" in matches):
            header_index, mapping = idx, matches
            break

    if header_index is None:
        raise ValueError(
            "Could not locate a transaction header row in the mentor workbook. "
            "Refusing to guess coordinates."
        )

    col = ColumnMap(mapping)
    loaded = 0
    audit = AuditChain(conn)
    for offset, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
        tx_id = clean_text(col.cell(row, "tx_id"))
        if not tx_id:
            continue
        amount = (
            parse_amount(col.cell(row, "credit"))
            or parse_amount(col.cell(row, "amount"))
            or parse_amount(col.cell(row, "debit"))
        )
        if amount <= 0:
            continue
        detail = clean_text(col.cell(row, "detail")) or ""
        if not detail and col.cell(row, "ne"):
            detail = str(col.cell(row, "ne"))
        tx_time = iso_value(col.cell(row, "date_doc"))
        parsed = parse_reference(detail)
        key = idempotency_key(path.name, tx_id, amount, tx_time)
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO bank_transactions
                (provider_tx_id, idempotency_key, source_stage, tx_time, direction,
                 amount, category, processing_status, reference_tokens,
                 raw_description, academic_year)
            VALUES (?, ?, 'mentor_export', ?, 'inbound', ?,
                    'Dòng tiền vào (chưa phân loại kế toán)',
                    ?, ?, ?, '2026-2027')
            """,
            (
                tx_id,
                key,
                tx_time,
                amount,
                "matched" if parsed.ne_references else "needs_review",
                " ".join(sorted(set(parsed.ne_codes + parsed.acn_codes))),
                detail,
            ),
        )
        if cursor.rowcount == 0:
            continue
        loaded += 1

    audit.record(
        "mentor_workbook_ingested",
        actor="import_pipeline",
        actor_role="finance_officer",
        entity_type="import_run",
        entity_key=path.name,
        detail={"rows_loaded": loaded, "header_row": header_index + 1},
    )
    return {"transactions": loaded, "header_row": header_index + 1, "audit_head": audit.head}


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    for name, scope in ROLE_SEED:
        conn.execute("INSERT OR IGNORE INTO roles(name, scope) VALUES (?, ?)", (name, scope))


def remove_database(path: Path) -> None:
    """Remove an existing SQLite file, tolerating sandboxed/read-only trash.

    Some managed environments (and some corporate Windows setups) intercept
    file deletion and route it through the recycle bin, which fails for files
    opened by another process. Falling back to in-place truncation keeps the
    rebuild path working instead of leaving a half-written database behind.
    """
    if not path.exists():
        return
    try:
        path.unlink()
        return
    except OSError:
        pass
    try:
        # Truncate instead: the schema is recreated immediately afterwards.
        with path.open("wb"):
            pass
    except OSError as exc:  # pragma: no cover - environment specific
        raise OSError(f"cannot replace database at {path}: {exc}") from exc


def build_database(source: Path, destination: Path, *, mode: str = "auto") -> dict:
    """Build a fresh database from a source file."""
    if not source.exists():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    remove_database(destination)

    conn = sqlite3.connect(destination)
    conn.execute("PRAGMA foreign_keys = ON")
    # Drop anything left over from a truncated-in-place rebuild.
    for (name,) in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall():
        conn.execute(f'DROP TABLE IF EXISTS "{name}"')
    conn.commit()
    ensure_schema(conn)

    with conn:
        if mode == "statement" or (mode == "auto" and source.suffix.lower() == ".csv"):
            stats = ingest_statement_file(conn, source)
        else:
            stats = ingest_mentor_workbook(conn, source)

        # ANALYZE is not optional. Without it SQLite has no sqlite_stat1 and
        # picks a catastrophic plan for the app's main query (measured 4,188 ms
        # on 1.0 M rows versus ~1 ms with statistics in place).
        conn.execute("ANALYZE")

        counts = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "bank_transactions",
                "transaction_allocations",
                "donors",
                "exception_queue",
                "audit_events",
            )
        }
        conn.execute(
            """
            INSERT INTO import_runs
                (source_name, source_sha256, source_kind, imported_at,
                 raw_transaction_rows, allocation_rows, schema_version)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source.name,
                sha256_file(source),
                "statement" if source.suffix.lower() == ".csv" else "excel",
                datetime.now(timezone.utc).isoformat(),
                counts["bank_transactions"],
                counts["transaction_allocations"],
                SCHEMA_VERSION,
            ),
        )

    conn.close()
    return {"database": str(destination), **counts, **stats}


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Build the Nuôi Em Topic 4 database.")
    parser.add_argument("source", type=Path)
    parser.add_argument("--database", type=Path, default=Path("data/nuoi_em_mvp.sqlite"))
    parser.add_argument("--mode", choices=["auto", "statement", "mentor"], default="auto")
    args = parser.parse_args()
    print(
        json.dumps(
            build_database(args.source, args.database, mode=args.mode),
            ensure_ascii=False,
            indent=2,
        )
    )
