import pathlib

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models
from .api import admin as admin_api, ledger as ledger_api, search as search_api, tickets as tickets_api
from .db import engine, get_db
from .migrations import init_db

app = FastAPI(title="Internal knowledge assistant")
app.include_router(search_api.router)
app.include_router(admin_api.router)
app.include_router(tickets_api.router)
app.include_router(ledger_api.router)


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


# Trang admin (HTML tinh): gan nhan du lieu/cong cu, nguoi dung, nhat ky.
_STATIC = pathlib.Path(__file__).parent / "static"
_STATIC.mkdir(exist_ok=True)
app.mount("/admin", StaticFiles(directory=str(_STATIC), html=True), name="admin")
