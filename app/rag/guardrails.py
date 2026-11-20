"""Rule-based input checks and fixed replies. Cheap, testable, no LLM involved.

Wording of the replies is a placeholder until the owners confirm it (see docs/PLAN.md section 10).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

REFUSE_TEXT = "Mình không thể hỗ trợ yêu cầu này."
NOT_FOUND_TEXT = "Mình chưa tìm thấy thông tin này trong dữ liệu hiện có."
HANDOFF_TEXT = "Mình đã chuyển câu hỏi của bạn cho tình nguyện viên, họ sẽ phản hồi sớm."


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


_INJECTION = [
    r"ignore (all |the )?(previous|above|prior)",
    r"disregard .*(instruction|rule)",
    r"system prompt",
    r"reveal .*(prompt|instruction)",
    r"bo qua .*(huong dan|chi dan|quy tac)",
    r"quen .*(huong dan|chi dan)",
    r"in ra .*(prompt|huong dan he thong)",
    r"you are now",
    r"developer mode",
]
_SENSITIVE = [
    r"danh sach .*(tre|em be|hoc sinh|nguoi thu huong|nguoi nhan)",
    r"(list|names?) of .*(children|kids|students|beneficiar)",
    r"(so dien thoai|sdt|dia chi nha|cmnd|cccd|can cuoc).*(cua|em|ban|nguoi)",
    r"(so tai khoan|stk).*(cua|ca nhan|nguoi)",
]
_HANDOFF = [
    r"(da|toi|minh) (chuyen|dong) (tien|khoan)",
    r"(kiem tra|tra cuu|xem) (khoan|giao dich|bua an|suat an)",
    r"khieu nai",
    r"phan nan",
    r"(gap|noi voi|lien he) .*(tinh nguyen vien|nguoi phu trach|quan tri vien)",
    r"(toi|minh) (muon|can) (gap|noi) .*(nguoi|tinh nguyen)",
]


@dataclass(frozen=True, slots=True)
class Decision:
    action: str          # "pass" | "refuse" | "handoff"
    reason: str | None = None


def check_input(question: str) -> Decision:
    q = _fold(question)
    for pat in _INJECTION:
        if re.search(pat, q):
            return Decision("refuse", "prompt_injection")
    for pat in _SENSITIVE:
        if re.search(pat, q):
            return Decision("refuse", "sensitive_request")
    for pat in _HANDOFF:
        if re.search(pat, q):
            return Decision("handoff", "needs_human")
    return Decision("pass")


_PHONE = re.compile(r"(?<!\d)(?:\+?84|0)[\s.-]?\d{2,3}[\s.-]?\d{3}[\s.-]?\d{3,4}(?!\d)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_LONG_DIGITS = re.compile(r"(?<!\d)\d{9,}(?!\d)")


def contains_personal_data(text: str) -> bool:
    return bool(_PHONE.search(text) or _EMAIL.search(text) or _LONG_DIGITS.search(text))
