from fastapi import Depends, FastAPI
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models
from .db import engine, get_db
from .migrations import init_db

app = FastAPI(title="QNE public chatbot")


@app.on_event("startup")
def startup():
    init_db(engine)


@app.get("/health")
def health(db: Session = Depends(get_db)):
    counts = dict(db.query(models.Chunk.source_type, func.count(models.Chunk.id))
                  .group_by(models.Chunk.source_type).all())
    last = db.query(models.SyncRun).order_by(models.SyncRun.id.desc()).first()
    return {
        "ok": True,
        "chunks": counts,
        "last_sync": None if last is None else {
            "at": last.finished_at.isoformat() if last.finished_at else None,
            "fetched": last.fetched, "inserted": last.inserted,
            "updated": last.updated, "deleted": last.deleted, "error": last.error,
        },
    }
