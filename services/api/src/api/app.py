"""FastAPI app factory for the Ambara API worker."""

from __future__ import annotations

from fastapi import FastAPI

from api.config import Settings
from api.routes.ingest import router as ingest_router


def create_app() -> FastAPI:
    settings = Settings.from_env()
    app = FastAPI(title="Ambara API Worker")
    app.state.settings = settings
    app.include_router(ingest_router)
    return app
