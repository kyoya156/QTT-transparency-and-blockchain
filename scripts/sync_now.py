"""Keo noi dung moi nhat tu crawler. Chay trong container:
    docker compose exec api python -m scripts.sync_now
"""
import argparse
import json
import sys

from app.db import SessionLocal, engine
from app.migrations import init_db
from app.sync.crawler_client import CrawlerError
from app.sync.sync_chunks import run_sync


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--allow-empty", action="store_true", help="cho phep xoa het / ket qua rong (than trong)")
    args = ap.parse_args()
    init_db(engine)
    db = SessionLocal()
    try:
        print(json.dumps(run_sync(db, allow_empty=args.allow_empty), ensure_ascii=False))
        return 0
    except CrawlerError as e:
        print(f"SYNC LOI: {e}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
