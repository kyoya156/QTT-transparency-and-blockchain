#!/usr/bin/env python
"""M2 retrieval CLI: ask a question, see the evidence the bot would answer from.

    python scripts/ask.py "Học bổng mỗi tháng bao nhiêu?"
    python scripts/ask.py "hoc bong" --no-embed --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Windows consoles default to cp1252 and would crash on any Vietnamese character.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from app.rag.embeddings import EmbedderUnavailable  # noqa: E402
from app.rag.retrieve import retrieve  # noqa: E402


def _format_number(value: float | None, digits: int) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Retrieve evidence for a sponsor's question.")
    parser.add_argument("question", nargs="+", help="câu hỏi tiếng Việt")
    parser.add_argument("-k", type=int, default=None, help="number of chunks to show")
    parser.add_argument(
        "--no-embed",
        action="store_true",
        help="keyword-only search (no torch, no model download)",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--source", help="comma separated source types, e.g. web,post")
    args = parser.parse_args(argv)

    print(
        "note: dev tool, ignores department labels and access rules; do not use on real data",
        file=sys.stderr,
    )
    question = " ".join(args.question).strip()
    source_types = [value.strip() for value in args.source.split(",") if value.strip()] if args.source else None

    try:
        result = retrieve(
            question,
            k=args.k,
            source_types=source_types,
            use_vector=not args.no_embed,
        )
    except EmbedderUnavailable as exc:
        print(f"không tạo được embedding: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
        return 0

    mode = "FTS + vector (RRF)" if result.used_vector else "FTS"
    print(f"Câu hỏi : {result.query}")
    print(f"Tìm kiếm: {mode} · {len(result.chunks)} đoạn")
    print(
        "Bằng chứng: "
        + ("ĐỦ" if result.is_confident else "KHÔNG ĐỦ (bot sẽ nói không tìm thấy)")
        + f" (similarity={_format_number(result.best_similarity, 3)},"
        + f" ts_rank={_format_number(result.best_ts_rank, 4)})"
    )

    if not result.chunks:
        print("\nKhông có đoạn nội dung nào khớp.")
        return 0

    for index, item in enumerate(result.chunks, start=1):
        chunk = item.chunk
        # show the page's own update date; otherwise say plainly that this is the crawl date
        date = (
            chunk.source_date.isoformat()
            if chunk.source_date
            else (
                f"crawl {chunk.display_date.isoformat()}"
                if chunk.display_date
                else "chưa xác định"
            )
        )
        print(f"\n{index}. [{item.rrf_score:.4f}] {chunk.source_type}:{chunk.source_id} · phần {chunk.part}")
        print(f"   {chunk.title or '(không tiêu đề)'} — cập nhật {date}")
        print(f"   {chunk.url or '(không có link)'}")
        print(
            f"   similarity={_format_number(item.vector_similarity, 3)}"
            f" ts_rank={_format_number(item.fts_rank, 4)}"
        )
        print("   " + " ".join(chunk.content.split())[:300])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
