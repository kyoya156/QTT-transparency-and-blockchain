#!/usr/bin/env python
"""Mirror crawler chunks into the chatbot index.

    python scripts/sync_now.py --init
    python scripts/sync_now.py --file data/chunks.json
    python scripts/sync_now.py --source http --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# allow `python scripts/sync_now.py` from the repo root without installing
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Windows consoles default to cp1252 and would crash on any Vietnamese character.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from app.config import get_settings  # noqa: E402
from app.db import init_schema  # noqa: E402
from app.sync.crawler_client import (  # noqa: E402
    ChunkSource,
    ChunkSourceError,
    HttpChunkSource,
    InvalidChunk,
    JsonFileSource,
)
from app.sync.sync_chunks import run_sync  # noqa: E402


def build_source(args: argparse.Namespace) -> ChunkSource:
    settings = get_settings()
    kind = args.source or settings.sync_source
    if kind == "http":
        return HttpChunkSource()
    if kind == "file":
        return JsonFileSource(args.file or settings.sync_file)
    raise ChunkSourceError(f"unknown sync source {kind!r} (expected 'file' or 'http')")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync crawler chunks into the chatbot index.")
    parser.add_argument("--source", choices=("file", "http"), help="where to read chunks from")
    parser.add_argument("--file", help="path to a crawler JSON export (with --source file)")
    parser.add_argument("--dry-run", action="store_true", help="report the diff, write nothing")
    parser.add_argument("--init", action="store_true", help="create extensions and tables first")
    parser.add_argument(
        "--embed",
        action="store_true",
        help="embed chunks that need a vector after syncing (needs requirements-embed.txt)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    # uvicorn/sqlalchemy chatter is noise for a one-shot CLI
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    try:
        if args.init:
            init_schema()
            print("schema ready")
        stats = run_sync(build_source(args), dry_run=args.dry_run)
    except (ChunkSourceError, InvalidChunk, ValueError) as exc:
        print(f"sync failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - database/connection failures
        print(f"sync failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(stats.as_dict(), ensure_ascii=False, indent=2))

    if args.embed and not args.dry_run:
        from app.rag.embeddings import EmbedderUnavailable, get_embedder
        from app.sync.embed_chunks import embed_chunks

        try:
            embedded = embed_chunks(embedder=get_embedder())
        except EmbedderUnavailable as exc:
            print(f"embedding skipped: {exc}", file=sys.stderr)
            return 2
        print(json.dumps({"embedded": embedded}, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
