"""Doi chieu ban sao chunk voi crawler: them moi, cap nhat khi noi dung doi, xoa cai crawler khong con.

Khoa doi chieu = id chunk ben crawler (src_id). Noi dung doi -> embedding = NULL de M2 embed lai.
"""
import datetime
import hashlib

from dateutil import parser as dateparser
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from .crawler_client import ALLOWED_TYPES, CrawlerError, fetch_all


def content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _date(meta: dict):
    for k in ("published_at", "crawled_at"):
        v = meta.get(k)
        if v:
            try:
                d = dateparser.parse(str(v))
                return d if d.tzinfo else d.replace(tzinfo=datetime.timezone.utc)
            except (ValueError, OverflowError):
                pass
    return None


def reconcile(db: Session, items: list[dict], allow_empty: bool = False,
              max_delete_ratio: float | None = None) -> dict:
    ratio = settings.sync_max_delete_ratio if max_delete_ratio is None else max_delete_ratio
    existing = {c.src_id: c for c in db.query(models.Chunk).all()}
    if existing and not items and not allow_empty:
        raise CrawlerError("crawler tra 0 chunk trong khi DB da co du lieu: huy de khong xoa nham")

    counts = {"fetched": 0, "inserted": 0, "updated": 0, "deleted": 0, "rejected": 0}
    seen: set[int] = set()
    for it in items:
        text = (it.get("content") or "").strip()
        if it.get("source_type") not in ALLOWED_TYPES or not text or it.get("id") is None:
            counts["rejected"] += 1
            continue
        sid = int(it["id"])
        if sid in seen:
            continue
        seen.add(sid)
        counts["fetched"] += 1
        meta = it.get("metadata") or {}
        h = content_hash(text)
        fields = dict(source_type=it["source_type"], source_id=str(it.get("source_id", "")),
                      url=meta.get("url"), title=meta.get("title"), part=meta.get("part"),
                      source_date=_date(meta))
        c = existing.get(sid)
        if c is None:
            db.add(models.Chunk(src_id=sid, content=text, content_hash=h, **fields))
            counts["inserted"] += 1
        elif c.content_hash != h:
            c.content, c.content_hash = text, h
            c.embedding, c.embed_model = None, None
            for k, v in fields.items():
                setattr(c, k, v)
            counts["updated"] += 1
        else:
            for k, v in fields.items():          # metadata doi (url, ngay) khong can embed lai
                if getattr(c, k) != v:
                    setattr(c, k, v)

    gone = [c for sid, c in existing.items() if sid not in seen]
    if existing and len(gone) / len(existing) > ratio and not allow_empty:
        db.rollback()
        raise CrawlerError(f"se xoa {len(gone)}/{len(existing)} chunk (> {ratio:.0%}): huy, kiem tra crawler")
    for c in gone:
        db.delete(c)
    counts["deleted"] = len(gone)
    db.commit()
    return counts


def run_sync(db: Session, allow_empty: bool = False, **fetch_kwargs) -> dict:
    """Keo + doi chieu + ghi sync_runs (ca khi loi)."""
    run = models.SyncRun()
    db.add(run)
    db.commit()
    try:
        items = fetch_all(**fetch_kwargs)
        counts = reconcile(db, items, allow_empty=allow_empty)
        run.fetched, run.inserted = counts["fetched"], counts["inserted"]
        run.updated, run.deleted = counts["updated"], counts["deleted"]
        return counts
    except Exception as e:
        db.rollback()
        run.error = str(e)[:500]
        raise
    finally:
        run.finished_at = datetime.datetime.now(datetime.timezone.utc)
        db.add(run)
        db.commit()
