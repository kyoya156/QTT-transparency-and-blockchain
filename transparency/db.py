"""Database for ledger_records, shared by the listener (writes) and the public API (reads).

LISTENER_DB_URL, else the app's DATABASE_URL, else sqlite file transparency_data/ledger.db.
Opening it installs the insert-only guard (measure 4).
"""
from __future__ import annotations

import functools
import os
import pathlib

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from . import guard

ROOT = pathlib.Path(__file__).resolve().parents[1]


@functools.lru_cache(maxsize=1)
def sessions() -> sessionmaker:
    url = os.environ.get("LISTENER_DB_URL") or os.environ.get("DATABASE_URL") or ""
    if not url:
        (ROOT / "transparency_data").mkdir(exist_ok=True)
        url = f"sqlite:///{(ROOT / 'transparency_data' / 'ledger.db').as_posix()}"
    eng = create_engine(url, pool_pre_ping=True)
    guard.install(eng)
    return sessionmaker(bind=eng, expire_on_commit=False)
