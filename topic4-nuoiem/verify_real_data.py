"""Verify the built database against the fund's own published figures.

Run after every change to the parser or the ingestion pipeline. Every number
here is compared against an externally published figure, not against another
number produced by this codebase — that is the point.

Notes on two traps this script used to fall into:

* It read `data/real_test.sqlite`, a scratch database left over from
  profiling, so it silently reported figures from a stale build. It now reads
  the database the app actually serves.
* Its tamper test mutated the live database and then "restored" it by deleting
  the row, which meant a second run found nothing to tamper with and reported
  the chain as intact. Tamper testing now happens on a throwaway copy, so the
  test is repeatable and the real database is never written to.
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from reconciliation import AuditChain  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATABASE = BASE / "data" / "nuoi_em_mvp.sqlite"

# Published by the fund in its own public statement header, 2018-2026.
PUBLISHED_INBOUND = 553_550_809_401
PUBLISHED_OUTBOUND = 553_541_302_920

failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    mark = "PASS" if condition else "FAIL"
    print(f"  [{mark}] {label}" + (f"  {detail}" if detail else ""))
    if not condition:
        failures.append(label)


if not DATABASE.exists():
    sys.exit(f"database not found: {DATABASE}\nrun build_database.py first")

conn = sqlite3.connect(f"file:{DATABASE.as_posix()}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row

print("=" * 78)
print(f"DATABASE {DATABASE.name}  ({DATABASE.stat().st_size / 1e6:.0f} MB)")
print("=" * 78)

print()
print("=== 1. Integrity invariant: allocation rows must sum to their transactions ===")
alloc = conn.execute(
    "SELECT COALESCE(SUM(allocated_amount_computed), 0) FROM transaction_allocations"
).fetchone()[0]
linked = conn.execute(
    "SELECT COALESCE(SUM(amount), 0) FROM bank_transactions WHERE id IN "
    "(SELECT DISTINCT transaction_id FROM transaction_allocations)"
).fetchone()[0]
print(f"  allocations total : {alloc:>20,}")
print(f"  linked tx total   : {linked:>20,}")
check("parts sum to the whole", alloc == linked, f"delta {alloc - linked:+,}")

print()
print("=== 2. Totals against the fund's own published header ===")
inbound = conn.execute(
    "SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM bank_transactions WHERE direction='inbound'"
).fetchone()
outbound = conn.execute(
    "SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM bank_transactions WHERE direction='outbound'"
).fetchone()
print(f"  inbound  {inbound[0]:>9,} rows  {inbound[1]:>20,} d")
print(f"  outbound {outbound[0]:>9,} rows  {outbound[1]:>20,} d")
print(f"  published                              Thu {PUBLISHED_INBOUND:,} / Chi {PUBLISHED_OUTBOUND:,}")
in_delta = inbound[1] - PUBLISHED_INBOUND
out_delta = outbound[1] - PUBLISHED_OUTBOUND
print(f"  inbound delta  : {in_delta:+,}")
print(f"  outbound delta : {out_delta:+,}")
check("outbound matches published to the dong", out_delta == 0, f"delta {out_delta:+,}")
check(
    "inbound matches published to the dong",
    in_delta == 0,
    f"delta {in_delta:+,} ({in_delta / PUBLISHED_INBOUND * 100:.4f}%)",
)

print()
print("=== 3. Parser hygiene: NE numbers must stay inside the catalogue width ===")
# Measure the NUMERIC width, not the string length. "NE00001S" is 8 characters
# but its numeric part is 5 digits, which is legitimate: the trailing S/T is a
# meal marker, not part of the number. The catalogue constraint is about the
# number, so the string length is the wrong thing to check.
#
# Six-digit numbers are not forbidden outright. Two memos in the real corpus
# list a genuine donor block in shorthand:
#     "NE140370, 140371, 140372"     a block of three sequential codes
#     "NE121215,16,17"               same, with the tail truncated
# Those are reachable ONLY through the bare-continuation rule, which requires
# an explicit NE head. What must never happen is a 6-digit number taken from a
# date or a bank trace, which is what the width cap exists to prevent. So the
# check allows long numbers but requires each one to be part of a continuation
# run (i.e. to have a neighbour within 3), and caps the total.
wide_rows = conn.execute(
    """
    SELECT ne_code, ne_number FROM transaction_allocations
    WHERE LENGTH(TRIM(SUBSTR(ne_code, 3), 'ST')) > 5
    ORDER BY ne_number
    """
).fetchall()
wide_numbers = sorted({row["ne_number"] for row in wide_rows})
orphans = [
    n
    for n in wide_numbers
    if not any(other != n and abs(other - n) <= 3 for other in wide_numbers)
]
check(
    "no isolated over-width numbers (dates/traces)",
    not orphans,
    f"orphans: {orphans}" if orphans else f"{len(wide_numbers)} long codes, all in continuation runs",
)
check(
    "over-width rows stay negligible",
    len(wide_rows) <= 20,
    f"{len(wide_rows)} of {conn.execute('SELECT COUNT(*) FROM transaction_allocations').fetchone()[0]:,} rows",
)
if wide_numbers:
    print(f"    tolerated long codes: {['NE%d' % n for n in wide_numbers]}")
widths = conn.execute(
    """
    SELECT LENGTH(TRIM(SUBSTR(ne_code, 3), 'ST')) AS w, COUNT(*) AS n
    FROM transaction_allocations GROUP BY w ORDER BY w
    """
).fetchall()
for row in widths:
    print(f"    numeric width {row['w']}: {row['n']:>9,}")

print()
print("=== 4. Audit chain is intact on the served database ===")
intact, broken_at = AuditChain(conn).verify()
check("chain intact", intact, f"first broken id {broken_at}" if not intact else "")

print()
print("=== 5. Tamper detection (on a throwaway copy, never the real db) ===")
tmp_dir = Path(tempfile.mkdtemp(prefix="nuoiem_verify_"))
tmp_db = tmp_dir / "tamper.sqlite"
try:
    shutil.copyfile(DATABASE, tmp_db)
    scratch = sqlite3.connect(tmp_db)
    before, _ = AuditChain(scratch).verify()
    # A privileged database owner can remove the append-only trigger. The hash
    # chain must still reveal an un-rehashed change after that bypass.
    scratch.execute("DROP TRIGGER IF EXISTS audit_events_no_update")
    scratch.execute("UPDATE audit_events SET detail = ? WHERE id = 1", ('{"rows_loaded": 1}',))
    scratch.commit()
    after, detected_at = AuditChain(scratch).verify()
    scratch.close()
    check("chain intact before tamper", before)
    check("tamper detected", not after, f"detected at event {detected_at}")
except Exception as exc:  # pragma: no cover - defensive
    check("tamper test ran", False, str(exc))
finally:
    shutil.rmtree(tmp_dir, ignore_errors=True)

print()
print("=== 6. Exception queue is aggregated, not one row per problem ===")
rows = conn.execute(
    "SELECT exception_code, severity, detail FROM exception_queue ORDER BY severity"
).fetchall()
count = conn.execute("SELECT COUNT(*) FROM exception_queue").fetchone()[0]
uncoded = conn.execute(
    "SELECT COUNT(*) FROM bank_transactions WHERE direction='inbound' AND id NOT IN "
    "(SELECT DISTINCT transaction_id FROM transaction_allocations)"
).fetchone()[0]
print(f"  exception rows in queue : {count}")
print(f"  underlying uncoded rows : {uncoded:,}")
for row in rows:
    print(f"  [{row['severity']}] {row['exception_code']}")
    print(f"        {row['detail'][:150]}")
check(
    "queue is aggregated (far fewer rows than problems)",
    count < max(10, uncoded // 100),
    f"{count} queue rows vs {uncoded:,} problems",
)

print()
print("=== 7. Allocation splits resolve to published unit prices ===")
tier_hits = conn.execute(
    "SELECT COUNT(*) FROM transaction_allocations WHERE allocated_amount_computed IN "
    "(1450000, 1360000, 1496000, 1650000, 500000, 170000, 150000)"
).fetchone()[0]
total_alloc = conn.execute("SELECT COUNT(*) FROM transaction_allocations").fetchone()[0]
print(f"  allocation rows matching a published tier: {tier_hits:,} / {total_alloc:,}")
check("a meaningful share hit a published tier", tier_hits > total_alloc * 0.2)

print()
print("=" * 78)
if failures:
    print(f"RESULT: {len(failures)} CHECK(S) FAILED")
    for item in failures:
        print(f"  - {item}")
    sys.exit(1)
print("RESULT: ALL CHECKS PASSED")
