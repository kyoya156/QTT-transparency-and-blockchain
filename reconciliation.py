"""Allocation, reconciliation, audit and maker-checker logic.

The allocation rules here are not invented. They were derived by measuring the
fund's own published statement (238,173 VCB rows) and checking what the numbers
actually do:

  * 4,325 multi-code transactions imply exactly 1,450,000đ per NE code, which
    matches the annual figure the fund publishes on its own website.
  * 9,087 of 9,493 multi-code transactions divide evenly by the code count.
  * Prices cluster on known tiers: 1,450,000 / 1,360,000 / 1,496,000 /
    1,650,000 / 170,000 / 150,000.

So an even split is the correct *default* policy, and a remainder has to be
recorded explicitly rather than hidden by rounding. Every computed figure is
labelled with the policy that produced it, because the fund never publishes a
per-pupil breakdown itself — we must never present a computed number as if it
were a confirmed one.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict

# Annual support tiers published by Quỹ Nuôi Em (đồng per NE code per year).
KNOWN_UNIT_PRICES = {
    1_450_000: "northern region, 1 meal/day, 9 months + facilities",
    1_360_000: "northern region, 170k x 8 months (2026-2027 rate)",
    1_496_000: "Central Highlands, 187k x 8 months (2026-2027 rate)",
    1_650_000: "Central Highlands, 170k/month x 9 months + facilities",
    170_000: "monthly meal rate",
    150_000: "monthly meal rate (legacy)",
}

ALLOCATION_EQUAL = "equal_split"
ALLOCATION_EQUAL_WITH_REMAINDER = "equal_split_with_remainder"
ALLOCATION_SINGLE = "single_code"
ALLOCATION_UNKNOWN = "unresolved"

MATCH_MATCHED = "matched"
MATCH_NE_UNKNOWN = "ne_not_in_registry"
MATCH_NO_ACN = "acn_missing"
MATCH_AMBIGUOUS = "ambiguous"


def split_amount(total: int, code_count: int) -> tuple[list[int], str]:
    """Split a transaction total across NE codes.

    Returns the per-code amounts plus the policy label. The remainder is handed
    to the first code rather than dropped, so the parts always sum back to the
    original total -- an auditor must be able to reconstruct the whole from the
    pieces.
    """
    if code_count <= 0:
        return [], ALLOCATION_UNKNOWN
    if code_count == 1:
        return [total], ALLOCATION_SINGLE

    base, remainder = divmod(total, code_count)
    amounts = [base] * code_count
    amounts[0] += remainder
    if remainder:
        return amounts, ALLOCATION_EQUAL_WITH_REMAINDER
    return amounts, ALLOCATION_EQUAL


def infer_unit_price(amount: int, code_count: int) -> int | None:
    """Return the implied per-code price if it matches a published tier."""
    if code_count <= 0:
        return None
    implied = round(amount / code_count)
    if implied in KNOWN_UNIT_PRICES:
        return implied
    return None


def classify_match(ne_code: str, known_ne_codes: set[str], acn_codes: list[str]) -> str:
    """Decide how confident we are about one allocation row."""
    if acn_codes and ne_code not in known_ne_codes:
        # The donor code is present but the pupil code is not in the registry:
        # either the registry is incomplete or the memo was mistyped.
        return MATCH_NE_UNKNOWN
    if ne_code not in known_ne_codes:
        return MATCH_AMBIGUOUS
    if not acn_codes:
        return MATCH_MATCHED  # NE alone is enough to place the pupil
    return MATCH_MATCHED


def idempotency_key(provider: str, provider_tx_id: str, amount: int, tx_time: str | None) -> str:
    """Stable key so a replayed webhook cannot inflate the total."""
    payload = f"{provider}|{provider_tx_id}|{amount}|{tx_time or ''}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class AuditChain:
    """Append-only, tamper-evident audit log.

    Each event stores the hash of the previous event. Editing or removing any
    historical row breaks the chain from that point on, which is exactly the
    property the fund's situation calls for: the 2026 verification found no
    embezzlement but did find that money had been run through personal accounts
    with no proper accounting trail. The fix is a log that cannot be quietly
    rewritten.
    """

    GENESIS = "0" * 64

    def __init__(self, connection):
        self.connection = connection
        row = connection.execute(
            "SELECT event_hash FROM audit_events ORDER BY id DESC LIMIT 1"
        ).fetchone()
        self._head = row[0] if row else self.GENESIS

    @property
    def head(self) -> str:
        return self._head

    def record(
        self,
        event_type: str,
        actor: str,
        entity_type: str | None = None,
        entity_key: str | None = None,
        actor_role: str | None = None,
        detail: dict | None = None,
    ) -> str:
        body = json.dumps(detail or {}, ensure_ascii=False, sort_keys=True, default=str)
        payload = "|".join(
            [self._head, event_type, entity_type or "", entity_key or "", actor, actor_role or "", body]
        )
        event_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        self.connection.execute(
            """
            INSERT INTO audit_events
                (event_type, entity_type, entity_key, actor, actor_role, detail, prev_hash, event_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (event_type, entity_type, entity_key, actor, actor_role, body, self._head, event_hash),
        )
        self._head = event_hash
        return event_hash

    def verify(self) -> tuple[bool, int | None]:
        """Walk the chain. Returns (intact, first_broken_event_id)."""
        previous = self.GENESIS
        for row in self.connection.execute(
            "SELECT id, event_type, entity_type, entity_key, actor, actor_role, detail, event_hash "
            "FROM audit_events ORDER BY id"
        ):
            (event_id, event_type, entity_type, entity_key, actor, actor_role, detail, stored) = row
            payload = "|".join(
                [
                    previous,
                    event_type,
                    entity_type or "",
                    entity_key or "",
                    actor,
                    actor_role or "",
                    detail or "",
                ]
            )
            if hashlib.sha256(payload.encode("utf-8")).hexdigest() != stored:
                return False, event_id
            previous = stored
        return True, None


def build_exceptions(
    transactions: list[dict],
    allocations: list[dict],
    known_ne_codes: set[str],
    *,
    registry_loaded: bool = True,
) -> list[dict]:
    """Turn reconciliation state into a work queue a human can act on.

    Exception *volume* matters as much as correctness. On the fund's real
    statement, 122,631 inbound rows carry no code at all -- because before the
    chatbot handed out ACN codes, donors wrote free text like "ung ho xay
    truong" or nothing. Emitting one exception per row produced 228,212 tasks
    and buried the genuinely actionable ones. Noise is a security problem: a
    queue nobody can read is a control that does not work.

    So we emit one aggregated exception per category with the count and the
    total value at risk, which is what an officer can actually triage.
    """
    by_tx: dict[str, list[dict]] = defaultdict(list)
    for allocation in allocations:
        by_tx[allocation["provider_tx_id"]].append(allocation)

    sum_mismatch: list[tuple[str, int, int, str]] = []
    unknown_values: list[tuple[str, list[str], int, str]] = []
    duplicate_rows: list[tuple[str, str]] = []
    unclassified_total = 0
    unclassified_ops = 0
    uncoded_total = 0
    uncoded_ops = 0

    for tx in transactions:
        tx_id = tx["provider_tx_id"]
        rows = by_tx.get(tx_id, [])
        allocated = sum(row["allocated_amount_computed"] for row in rows)

        if rows and tx["amount"] != allocated:
            sum_mismatch.append((tx_id, tx["amount"], allocated, tx.get("source_ref", "")))

        if registry_loaded and rows:
            unknown = [
                r for r in rows if r["match_status"] in {MATCH_NE_UNKNOWN, MATCH_AMBIGUOUS}
            ]
            if unknown:
                codes = sorted({r["ne_code"] for r in unknown})
                value = sum(r["allocated_amount_computed"] for r in unknown)
                unknown_values.append((tx_id, codes, value, tx.get("source_ref", "")))

        if rows and len({r["ne_code"] for r in rows}) != len(rows):
            duplicate_rows.append((tx_id, tx.get("source_ref", "")))

        if tx["processing_status"] == "unclassified":
            unclassified_ops += 1
            unclassified_total += tx["amount"]
        elif tx["direction"] == "inbound" and not rows:
            uncoded_ops += 1
            uncoded_total += tx["amount"]

    exceptions: list[dict] = []

    if sum_mismatch:
        worst = max(sum_mismatch, key=lambda item: abs(item[1] - item[2]))
        exceptions.append(
            {
                "exception_code": "ALLOCATION_SUM_MISMATCH",
                "severity": "high",
                "entity_type": "bank_transaction",
                "entity_key": None,
                "detail": (
                    f"{len(sum_mismatch)} giao dịch có tổng phân bổ không khớp số tiền giao dịch. "
                    f"Lệch lớn nhất {abs(worst[1] - worst[2]):,}đ tại {worst[0]}. "
                    "Đây là lỗi toàn vẹn dữ liệu, phải chặn trước khi báo cáo."
                ),
                "source_ref": worst[3],
            }
        )

    if unknown_values:
        total_value = sum(v for _, _, v, _ in unknown_values)
        all_codes: set[str] = set()
        for _, codes, _, _ in unknown_values:
            all_codes.update(codes)
        exceptions.append(
            {
                "exception_code": "NE_CODE_NOT_IN_REGISTRY",
                "severity": "high",
                "entity_type": "dataset",
                "entity_key": None,
                "detail": (
                    f"{len(unknown_values)} giao dịch tham chiếu {len(all_codes)} mã NE chưa có "
                    f"trong danh mục học sinh, tổng {total_value:,}đ. "
                    "Cần đối chiếu với danh sách trường gửi trước khi công bố."
                ),
                "source_ref": "aggregate",
            }
        )

    if uncoded_ops:
        exceptions.append(
            {
                "exception_code": "INBOUND_WITHOUT_CODE",
                "severity": "medium",
                "entity_type": "dataset",
                "entity_key": None,
                "detail": (
                    f"{uncoded_ops:,} giao dịch tiền vào không gắn được mã ACN/NE, "
                    f"tổng {uncoded_total:,}đ. Theo quy định của Quỹ, các khoản này "
                    "không hoàn lại và chuyển vào quỹ vô danh (xây trường) — cần người "
                    "xác nhận và hạch toán riêng thay vì gộp vào tiền ăn."
                ),
                "source_ref": "aggregate",
            }
        )

    if unclassified_ops:
        exceptions.append(
            {
                "exception_code": "UNCLASSIFIED_INBOUND",
                "severity": "medium",
                "entity_type": "dataset",
                "entity_key": None,
                "detail": (
                    f"{unclassified_ops:,} giao dịch chưa được phân loại, "
                    f"tổng {unclassified_total:,}đ. Cần chạy lại bộ phân loại có phiên bản."
                ),
                "source_ref": "aggregate",
            }
        )

    if duplicate_rows:
        exceptions.append(
            {
                "exception_code": "DUPLICATE_NE_ON_TRANSACTION",
                "severity": "low",
                "entity_type": "dataset",
                "entity_key": None,
                "detail": (
                    f"{len(duplicate_rows)} giao dịch ghi cùng một mã NE nhiều lần. "
                    "Số tiền đã được gộp nên không bị cộng trùng, nhưng nội dung "
                    "chuyển khoản cần chuẩn hoá."
                ),
                "source_ref": duplicate_rows[0][1] if duplicate_rows else "",
            }
        )

    return exceptions


def propose_approval(connection, entity_type, entity_key, action, payload, reason, maker, role=None):
    """Queue a maker-checker task. The maker can never approve their own change."""
    connection.execute(
        """
        INSERT INTO approval_tasks
            (entity_type, entity_key, action, proposed_payload, reason, maker, status)
        VALUES (?, ?, ?, ?, ?, ?, 'pending')
        """,
        (
            entity_type,
            entity_key,
            action,
            json.dumps(payload, ensure_ascii=False, default=str),
            reason,
            maker,
        ),
    )
    return connection.execute("SELECT last_insert_rowid()").fetchone()[0]


def decide_approval(connection, task_id, checker, approve: bool, note: str = ""):
    """Approve or reject. Enforces separation of duties."""
    task = connection.execute(
        "SELECT maker, status FROM approval_tasks WHERE id = ?", (task_id,)
    ).fetchone()
    if not task:
        raise ValueError(f"approval task {task_id} not found")
    if task[1] != "pending":
        raise ValueError(f"approval task {task_id} already {task[1]}")
    if task[0] == checker:
        raise PermissionError("maker and checker must be different people")

    connection.execute(
        """
        UPDATE approval_tasks
        SET status = ?, checker = ?, decided_at = datetime('now'), decision_note = ?
        WHERE id = ?
        """,
        ("approved" if approve else "rejected", checker, note, task_id),
    )
    return "approved" if approve else "rejected"
