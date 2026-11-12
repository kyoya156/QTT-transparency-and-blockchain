"""FastAPI entrypoint. The public chat page and /chat arrive in M4."""

from __future__ import annotations

from fastapi import FastAPI

from app import __version__
from app.api.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="QNE public chatbot",
        version=__version__,
        description="Answers sponsors' questions from crawled content only, with sources.",
    )
    app.include_router(health_router)
    return app


app = create_app()
