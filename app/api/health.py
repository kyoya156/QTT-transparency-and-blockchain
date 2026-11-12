"""Liveness/readiness plus the last sync run, so staleness is visible."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import SyncRun

router = APIRouter(tags=["ops"])


@router.get("/healthz")
def healthz(session: Session = Depends(get_session)) -> JSONResponse:
    payload: dict[str, object] = {"status": "ok", "db": True, "last_sync": None}

    try:
        session.execute(text("SELECT 1"))
        last_run = session.execute(
            select(SyncRun).order_by(SyncRun.started_at.desc()).limit(1)
        ).scalar_one_or_none()
    except SQLAlchemyError as exc:
        payload.update({"status": "degraded", "db": False, "error": str(exc)[:300]})
        return JSONResponse(payload, status_code=503)

    if last_run is not None:
        payload["last_sync"] = {
            "started_at": last_run.started_at.isoformat(),
            "finished_at": last_run.finished_at.isoformat() if last_run.finished_at else None,
            "status": last_run.status,
            "fetched": last_run.fetched,
            "inserted": last_run.inserted,
            "updated": last_run.updated,
            "deleted": last_run.deleted,
            "unchanged": last_run.unchanged,
        }

    return JSONResponse(payload)
