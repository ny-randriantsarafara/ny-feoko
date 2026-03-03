"""FastAPI app factory with dependency injection wiring."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from application.use_cases.export_training import ExportTraining
from application.use_cases.list_runs import ListRuns
from application.use_cases.manage_runs import Cleanup, DeleteRun
from application.use_cases.redraft_clips import RedraftClips
from application.use_cases.sync_run import SyncRun
from infra.clients.supabase import get_client
from infra.clients.youtube import YouTubeDownloader
from infra.config import Settings
from infra.repositories.supabase_clip_repo import SupabaseClipRepository
from infra.repositories.supabase_job_repo import SupabaseJobRepository
from infra.repositories.supabase_run_repo import SupabaseRunRepository
from infra.repositories.supabase_storage import SupabaseAudioStorage
from infra.telemetry.setup import init_telemetry
from ports.rest.routes.export import router as export_router
from ports.rest.routes.ingest import router as ingest_router
from ports.rest.routes.jobs import router as jobs_router
from ports.rest.routes.metrics import router as metrics_router
from ports.rest.routes.redraft import router as redraft_router
from ports.rest.routes.runs import router as runs_router


def create_app() -> FastAPI:
    settings = Settings.from_env()

    # Initialize telemetry before anything else
    init_telemetry(
        service_name=settings.otel_service_name,
        otlp_endpoint=settings.otel_endpoint,
        console_export=settings.otel_console_export,
    )

    client = get_client()

    run_repo = SupabaseRunRepository(client)
    clip_repo = SupabaseClipRepository(client)
    job_repo = SupabaseJobRepository(client)
    storage = SupabaseAudioStorage(client)

    sync_use_case = SyncRun(run_repo, clip_repo, storage)

    app = FastAPI(title="Ambara API")

    # Auto-instrument FastAPI for HTTP traces
    FastAPIInstrumentor.instrument_app(app)

    app.state.settings = settings
    app.state.executor = ThreadPoolExecutor(max_workers=1)

    app.state.ingest_downloader = YouTubeDownloader()
    app.state.export = ExportTraining(run_repo, clip_repo, storage)
    app.state.redraft = RedraftClips(run_repo, clip_repo, storage, job_repo)
    app.state.list_runs = ListRuns(run_repo)
    app.state.delete_run = DeleteRun(run_repo, storage)
    app.state.cleanup = Cleanup(run_repo, clip_repo, storage)
    app.state.job_repo = job_repo
    app.state.run_repo = run_repo
    app.state.sync = sync_use_case

    app.include_router(ingest_router)
    app.include_router(export_router)
    app.include_router(redraft_router)
    app.include_router(jobs_router)
    app.include_router(runs_router)
    app.include_router(metrics_router)

    return app
