"""FastAPI app factory for the Ambara API worker."""

from __future__ import annotations

from fastapi import FastAPI

from api.config import Settings
from api.routes.export import router as export_router
from api.routes.ingest import router as ingest_router
from api.routes.jobs import router as jobs_router
from api.routes.redraft import router as redraft_router


def create_app() -> FastAPI:
    settings = Settings.from_env()
    app = FastAPI(title="Ambara API Worker")
    app.state.settings = settings
    app.include_router(ingest_router)
    app.include_router(jobs_router)
    app.include_router(redraft_router)
    app.include_router(export_router)
    return app
