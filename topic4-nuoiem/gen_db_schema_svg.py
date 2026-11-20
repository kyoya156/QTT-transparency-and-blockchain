#!/usr/bin/env python3
# -I safe: no local imports besides stdlib.
"""Generates static/assets/db-schema.svg for the Quỹ Minh Bạch Tài Chính admin dashboard.

Draws the 16-table schema (schema.py) as a grouped, colored box-and-line
diagram: solid arrows are real foreign keys, dashed arrows are the business
flow that has no FK (import -> ingestion, matching -> exceptions, requests ->
approval, ledger -> report periods). Lines are drawn before boxes so any
incidental pass-through is masked by an opaque box on top, which keeps the
routing code simple (straight / gently curved anchors, no maze-solving).

The field lists and FK/flow edges below are hand-kept in sync with
`schema.py` — re-run this (`python3 gen_db_schema_svg.py`) after a schema
change and commit the regenerated SVG; nothing wires this into the app's
build automatically. Rendered inside the admin dashboard at #/schema
(static/admin.html).
"""

import html
import os

# ----------------------------------------------------------------- palette
# Matches static/admin.css :root. Four categorical hues for the four domain
# groups, chosen to pass scripts/validate_palette.js (dataviz skill): all six
# checks PASS at L 0.43-0.77 / C>=0.10 / CVD worst-adjacent dE 8.1 / normal-
# vision floor 20.4 / contrast >=3:1 on this page's --bg (#f7f8fa).
BG = "#f7f8fa"
SURFACE = "#ffffff"
TEXT = "#1c2330"
MUTED = "#5d6675"
BORDER = "#e1e5eb"

GROUPS = {
    "ref": {"label": "Dữ liệu tham chiếu", "hue": "#2a6fb0", "soft": "#e8eff8"},
    "tx": {"label": "Giao dịch ngân hàng", "hue": "#d2601f", "soft": "#fdeee1"},
    "recon": {"label": "Đối soát & giải ngân", "hue": "#146b45", "soft": "#e6f4ed"},
    "gov": {"label": "Quản trị & giám sát", "hue": "#6a4c93", "soft": "#efe9f5"},
}

# ------------------------------------------------------------------ tables
# (key, group, title, [field lines])
TABLES = [
    ("schools", "ref", "schools", ["id PK", "school_code UK", "name"]),
    ("students", "ref", "students", ["id PK", "student_code UK", "school_id FK"]),
    ("donors", "ref", "donors", ["id PK", "acn_code UK", ""]),
    ("student_supports", "ref", "student_supports",
     ["id PK", "student_id FK", "donor_id FK"]),

    ("bank_transactions", "tx", "bank_transactions",
     ["id PK", "direction", "amount"]),
    ("transaction_allocations", "tx", "transaction_allocations",
     ["id PK", "transaction_id FK", "ne_code"]),

    ("school_payment_requests", "recon", "school_payment_requests",
     ["id PK", "school_id FK", "status"]),
    ("disbursements", "recon", "disbursements",
     ["id PK", "payment_request_id FK", "transaction_id FK"]),
    ("evidence_documents", "recon", "evidence_documents",
     ["id PK", "payment_request_id FK", "checksum_sha256"]),

    ("roles", "gov", "roles", ["id PK", "name UK", ""]),
    ("import_runs", "gov", "import_runs",
     ["id PK", "source_name", "imported_at"]),
    ("report_periods", "gov", "report_periods",
     ["id PK", "period_label UK", "status"]),
    ("approval_tasks", "gov", "approval_tasks",
     ["id PK", "maker", "checker"]),
    ("exception_queue", "gov", "exception_queue",
     ["id PK", "severity", "status"]),
    ("data_quality_issues", "gov", "data_quality_issues",
     ["id PK", "severity", "issue_code"]),
    ("audit_events", "gov", "audit_events",
     ["id PK", "event_type", "prev_hash→hash"]),
]

COLUMNS = ["ref", "tx", "recon", "gov"]
COL_ORDER = {
    "ref": ["schools", "students", "donors", "student_supports"],
    "tx": ["bank_transactions", "transaction_allocations"],
    "recon": ["school_payment_requests", "disbursements", "evidence_documents"],
    "gov": ["roles", "import_runs", "report_periods", "approval_tasks",
            "exception_queue", "data_quality_issues", "audit_events"],
}

# Real foreign keys (schema.py) -> solid arrows.
FK_EDGES = [
    ("students", "schools"),
    ("student_supports", "students"),
    ("student_supports", "donors"),
    ("transaction_allocations", "bank_transactions"),
    ("transaction_allocations", "donors"),
    ("transaction_allocations", "students"),
    ("transaction_allocations", "schools"),
    ("school_payment_requests", "schools"),
    ("disbursements", "school_payment_requests"),
    ("disbursements", "bank_transactions"),
    ("evidence_documents", "school_payment_requests"),
]

# Business flow that is NOT a foreign key -> dashed arrows with a short label.
FLOW_EDGES = [
    ("import_runs", "bank_transactions", "nạp sao kê"),
    ("import_runs", "students", "nạp danh mục"),
    ("bank_transactions", "exception_queue", "thiếu/lệch mã"),
    ("transaction_allocations", "exception_queue", "mã lạ/trùng"),
    ("school_payment_requests", "approval_tasks", "chờ duyệt"),
    ("disbursements", "report_periods", "tổng hợp kỳ"),
    ("bank_transactions", "report_periods", "tổng hợp kỳ"),
]

# ------------------------------------------------------------------ layout
BOX_W = 214
BOX_H = 86
ROW_GAP = 26
COL_GAP = 150
MARGIN_X = 50
TITLE_H = 58
LEGEND_H = 46
FOOTER_H = 34
TOP_PAD = 24

col_x = {}
x = MARGIN_X
for c in COLUMNS:
    col_x[c] = x
    x += BOX_W + COL_GAP
CANVAS_W = x - COL_GAP + MARGIN_X

content_top = TITLE_H + LEGEND_H + TOP_PAD
tallest_rows = max(len(v) for v in COL_ORDER.values())
content_h = tallest_rows * BOX_H + (tallest_rows - 1) * ROW_GAP
CANVAS_H = content_top + content_h + FOOTER_H + 30

box = {}  # key -> (x, y, w, h, cx, cy)
for c in COLUMNS:
    keys = COL_ORDER[c]
    n = len(keys)
    col_h = n * BOX_H + (n - 1) * ROW_GAP
    start_y = content_top + (content_h - col_h) / 2
    for i, k in enumerate(keys):
        bx = col_x[c]
        by = start_y + i * (BOX_H + ROW_GAP)
        box[k] = dict(x=bx, y=by, w=BOX_W, h=BOX_H, cx=bx + BOX_W / 2, cy=by + BOX_H / 2)

TABLE_BY_KEY = {t[0]: t for t in TABLES}
COL_BY_KEY = {t[0]: t[1] for t in TABLES}

# Group backdrop geometry, computed once so both the drawing pass and the
# label-collision check agree on where each group's title sits.
group_rect = {}
for c in COLUMNS:
    keys = COL_ORDER[c]
    ys = [box[k]["y"] for k in keys]
    ye = [box[k]["y"] + box[k]["h"] for k in keys]
    bx = col_x[c] - 14
    by = min(ys) - 34
    bw = BOX_W + 28
    bh = max(ye) - min(ys) + 34 + 10
    group_rect[c] = dict(x=bx, y=by, w=bw, h=bh)


def esc(s):
    return html.escape(str(s), quote=True)


def side_anchor(a, b):
    """Pick exit/entry side + point given two box dicts (same or diff column)."""
    if abs(a["cx"] - b["cx"]) < 1:
        # same column: vertical link
        if a["cy"] < b["cy"]:
            return (a["cx"], a["y"] + a["h"]), (b["cx"], b["y"])
        return (a["cx"], a["y"]), (b["cx"], b["y"] + b["h"])
    if a["cx"] < b["cx"]:
        return (a["x"] + a["w"], a["cy"]), (b["x"], b["cy"])
    return (a["x"], a["cy"]), (b["x"] + b["w"], b["cy"])


def curve_path(p1, p2):
    x1, y1 = p1
    x2, y2 = p2
    if abs(x1 - x2) < 1:
        # vertical: straight line is cleanest
        return f"M {x1:.1f} {y1:.1f} L {x2:.1f} {y2:.1f}"
    dx = (x2 - x1) * 0.55
    return (f"M {x1:.1f} {y1:.1f} C {x1 + dx:.1f} {y1:.1f}, "
            f"{x2 - dx:.1f} {y2:.1f}, {x2:.1f} {y2:.1f}")


def curve_point_at(p1, p2, t):
    """Point at parameter t on the same path curve_path() draws (cubic, or
    the straight vertical special-case)."""
    x1, y1 = p1
    x2, y2 = p2
    if abs(x1 - x2) < 1:
        return (x1, y1 + (y2 - y1) * t)
    dx = (x2 - x1) * 0.55
    c1 = (x1 + dx, y1)
    c2 = (x2 - dx, y2)
    mt = 1 - t
    x = mt**3 * x1 + 3 * mt**2 * t * c1[0] + 3 * mt * t**2 * c2[0] + t**3 * x2
    y = mt**3 * y1 + 3 * mt**2 * t * c1[1] + 3 * mt * t**2 * c2[1] + t**3 * y2
    return (x, y)


def point_in_any_box(x, y, pad=6):
    for b in box.values():
        if b["x"] - pad <= x <= b["x"] + b["w"] + pad and b["y"] - pad <= y <= b["y"] + b["h"] + pad:
            return True
    # Also steer clear of each group's title strip (the top ~34px of its
    # backdrop), even though the backdrop itself is translucent and harmless.
    for g in group_rect.values():
        if g["x"] <= x <= g["x"] + g["w"] and g["y"] <= y <= g["y"] + 34:
            return True
    return False


def safe_label_point(p1, p2):
    """First point along the curve, trying t values out from the middle, that
    doesn't land on top of a table box (which is drawn above the label)."""
    for t in (0.5, 0.4, 0.6, 0.3, 0.7, 0.2, 0.8, 0.5):
        x, y = curve_point_at(p1, p2, t)
        if not point_in_any_box(x, y):
            return x, y
    return curve_point_at(p1, p2, 0.5)


parts = []
parts.append(
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CANVAS_W:.0f} {CANVAS_H:.0f}" '
    f'width="{CANVAS_W:.0f}" height="{CANVAS_H:.0f}" role="img" '
    f'aria-labelledby="schema-title schema-desc">'
)
parts.append(f'<title id="schema-title">Sơ đồ CSDL — luồng dữ liệu Quỹ Minh Bạch Tài Chính (Topic 4)</title>')
parts.append(
    '<desc id="schema-desc">16 bảng của SQLite, nhóm theo 4 vùng: dữ liệu tham '
    'chiếu, giao dịch ngân hàng, đối soát &amp; giải ngân, quản trị &amp; giám sát. '
    'Mũi tên liền là khóa ngoại thật; mũi tên đứt là luồng nghiệp vụ không có khóa ngoại.</desc>'
)
parts.append(f'<rect x="0" y="0" width="{CANVAS_W:.0f}" height="{CANVAS_H:.0f}" fill="{BG}" />')

# markers
parts.append('<defs>')
parts.append(
    '<marker id="arrow-solid" viewBox="0 0 10 10" refX="9" refY="5" '
    'markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
    f'<path d="M0,0 L10,5 L0,10 z" fill="{MUTED}" /></marker>'
)
parts.append(
    '<marker id="arrow-dash" viewBox="0 0 10 10" refX="9" refY="5" '
    'markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
    f'<path d="M0,0 L10,5 L0,10 z" fill="{GROUPS["gov"]["hue"]}" /></marker>'
)
parts.append('</defs>')

# -------------------------------------------------------------- title + legend
parts.append(
    f'<text x="{MARGIN_X}" y="30" font-family="system-ui,-apple-system,Segoe UI,Roboto,sans-serif" '
    f'font-size="19" font-weight="700" fill="{TEXT}">Sơ đồ CSDL — luồng dữ liệu hệ thống Quỹ Minh Bạch Tài Chính</text>'
)
parts.append(
    f'<text x="{MARGIN_X}" y="50" font-family="system-ui,-apple-system,Segoe UI,Roboto,sans-serif" '
    f'font-size="12.5" fill="{MUTED}">16 bảng · schema.py v2.0 · '
    'liền = khóa ngoại thật · đứt = luồng nghiệp vụ (không khóa ngoại)</text>'
)

legend_y = TITLE_H + 6
lx = MARGIN_X
for c in COLUMNS:
    g = GROUPS[c]
    parts.append(f'<rect x="{lx}" y="{legend_y}" width="14" height="14" rx="3" fill="{g["hue"]}" />')
    parts.append(
        f'<text x="{lx + 20}" y="{legend_y + 11}" font-family="system-ui,-apple-system,Segoe UI,sans-serif" '
        f'font-size="12.5" fill="{TEXT}">{esc(g["label"])}</text>'
    )
    lx += 20 + 9 * len(g["label"]) + 34

# line-style legend, right-aligned
line_legend_x = CANVAS_W - MARGIN_X - 230
parts.append(f'<line x1="{line_legend_x}" y1="{legend_y+7}" x2="{line_legend_x+28}" y2="{legend_y+7}" '
             f'stroke="{MUTED}" stroke-width="2" marker-end="url(#arrow-solid)" />')
parts.append(f'<text x="{line_legend_x+36}" y="{legend_y+11}" font-family="system-ui,-apple-system,Segoe UI,sans-serif" '
             f'font-size="12.5" fill="{TEXT}">khóa ngoại</text>')
line_legend_x2 = line_legend_x + 120
parts.append(f'<line x1="{line_legend_x2}" y1="{legend_y+7}" x2="{line_legend_x2+28}" y2="{legend_y+7}" '
             f'stroke="{GROUPS["gov"]["hue"]}" stroke-width="2" stroke-dasharray="2 3" '
             f'marker-end="url(#arrow-dash)" />')
parts.append(f'<text x="{line_legend_x2+36}" y="{legend_y+11}" font-family="system-ui,-apple-system,Segoe UI,sans-serif" '
             f'font-size="12.5" fill="{TEXT}">luồng nghiệp vụ</text>')

# -------------------------------------------------------------- group backdrops
for c in COLUMNS:
    r = group_rect[c]
    bx, by, bw, bh = r["x"], r["y"], r["w"], r["h"]
    g = GROUPS[c]
    parts.append(
        f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="14" '
        f'fill="{g["soft"]}" stroke="{g["hue"]}" stroke-opacity="0.35" stroke-width="1.5" />'
    )
    parts.append(
        f'<text x="{bx+14:.1f}" y="{by+20:.1f}" font-family="system-ui,-apple-system,Segoe UI,sans-serif" '
        f'font-size="12.5" font-weight="700" fill="{g["hue"]}">{esc(g["label"].upper())}</text>'
    )

# -------------------------------------------------------------- edges (lines first)
for a_key, b_key in FK_EDGES:
    a, b = box[a_key], box[b_key]
    p1, p2 = side_anchor(a, b)
    d = curve_path(p1, p2)
    parts.append(f'<path d="{d}" fill="none" stroke="{MUTED}" stroke-width="1.6" '
                 f'marker-end="url(#arrow-solid)" opacity="0.85" />')

for a_key, b_key, label in FLOW_EDGES:
    a, b = box[a_key], box[b_key]
    p1, p2 = side_anchor(a, b)
    d = curve_path(p1, p2)
    col = GROUPS["gov"]["hue"]
    parts.append(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="1.6" '
                 f'stroke-dasharray="2 4" marker-end="url(#arrow-dash)" opacity="0.8" />')
    lxp, lyp = safe_label_point(p1, p2)
    w = 8 * len(label) + 10
    parts.append(f'<rect x="{lxp - w/2:.1f}" y="{lyp - 9:.1f}" width="{w:.1f}" height="15" rx="4" '
                 f'fill="{BG}" opacity="0.92" />')
    parts.append(f'<text x="{lxp:.1f}" y="{lyp+2:.1f}" text-anchor="middle" '
                 f'font-family="system-ui,-apple-system,Segoe UI,sans-serif" font-size="10.5" '
                 f'fill="{col}">{esc(label)}</text>')

# -------------------------------------------------------------- boxes (on top)
for key, group, title, fields in TABLES:
    b = box[key]
    g = GROUPS[group]
    parts.append(
        f'<rect x="{b["x"]:.1f}" y="{b["y"]:.1f}" width="{b["w"]:.1f}" height="{b["h"]:.1f}" rx="9" '
        f'fill="{SURFACE}" stroke="{BORDER}" stroke-width="1" />'
    )
    parts.append(
        f'<rect x="{b["x"]:.1f}" y="{b["y"]:.1f}" width="{b["w"]:.1f}" height="26" rx="9" '
        f'fill="{g["hue"]}" />'
    )
    # square off the bottom corners of the header strip
    parts.append(
        f'<rect x="{b["x"]:.1f}" y="{b["y"]+13:.1f}" width="{b["w"]:.1f}" height="13" '
        f'fill="{g["hue"]}" />'
    )
    parts.append(
        f'<text x="{b["x"]+10:.1f}" y="{b["y"]+17.5:.1f}" '
        f'font-family="ui-monospace,SFMono-Regular,Menlo,monospace" font-size="12.5" '
        f'font-weight="700" fill="#ffffff">{esc(title)}</text>'
    )
    fy = b["y"] + 26 + 16
    for line in fields:
        if line:
            is_key = "PK" in line or "FK" in line or "UK" in line
            col = TEXT if is_key else MUTED
            parts.append(
                f'<text x="{b["x"]+10:.1f}" y="{fy:.1f}" '
                f'font-family="ui-monospace,SFMono-Regular,Menlo,monospace" font-size="11" '
                f'fill="{col}">{esc(line)}</text>'
            )
        fy += 16

# -------------------------------------------------------------- footer
parts.append(
    f'<text x="{MARGIN_X}" y="{CANVAS_H-14:.1f}" '
    f'font-family="system-ui,-apple-system,Segoe UI,sans-serif" font-size="11.5" fill="{MUTED}">'
    'Tiền vào → bank_transactions → transaction_allocations (chia theo mã NE). '
    'Tiền ra → school_payment_requests → disbursements → evidence_documents. '
    'Xem docs/ERD_VA_LUONG_LOI.md để biết luồng lỗi theo từng gate.</text>'
)

parts.append('</svg>')

svg = "\n".join(parts)
out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "assets", "db-schema.svg")
with open(out_path, "w", encoding="utf-8") as f:
    f.write(svg)
print("wrote", out_path, len(svg), "bytes", CANVAS_W, "x", CANVAS_H)
