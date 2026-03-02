"""FastAPI app factory for the Ambara API worker."""

from __future__ import annotations

from fastapi import FastAPI

from api.config import Settings


def create_app() -> FastAPI:
    settings = Settings.from_env()
    app = FastAPI(title="Ambara API Worker")
    app.state.settings = settings
    return app
