#!/usr/bin/env python
"""Embed chunks that are missing a vector.

    python scripts/embed_chunks.py
    python scripts/embed_chunks.py --force --batch 8
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Windows consoles default to cp1252 and would crash on any Vietnamese character.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from app.rag.embeddings import EmbedderUnavailable, get_embedder  # noqa: E402
from app.sync.embed_chunks import embed_chunks  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fill chunks.embedding.")
    parser.add_argument("--force", action="store_true", help="re-embed everything")
    parser.add_argument("--batch", type=int, default=None, help="batch size")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        count = embed_chunks(
            embedder=get_embedder(), force=args.force, batch_size=args.batch
        )
    except EmbedderUnavailable as exc:
        print(f"không cài được embedding: {exc}", file=sys.stderr)
        return 2

    print(f"embedded {count} chunks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
