"""POST /ingest — start YouTube ingestion job (download, extract, sync)."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Request
from pydantic import BaseModel

from api.jobs import JobUpdate, create_job, fail_job, update_job
from db_sync.supabase_client import get_client

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=1)

router = APIRouter(prefix="/ingest", tags=["ingest"])


class IngestRequest(BaseModel):
    url: str
    label: str
    whisper_model: str = "small"
    whisper_hf: str = ""
    vad_threshold: float = 0.35
    speech_threshold: float = 0.35


class IngestResponse(BaseModel):
    job_id: str


def _run_ingest(
    job_id: str,
    url: str,
    label: str,
    whisper_model: str,
    whisper_hf: str,
    vad_threshold: float,
    speech_threshold: float,
    device: str,
    input_dir: str,
    output_dir: str,
) -> None:
    from pathlib import Path

    from yt_download.cli import download_audio

    from api.models_cache import get_models
    from clip_extraction.pipeline import run_pipeline
    from db_sync.supabase_client import get_client
    from db_sync.sync import sync_run

    client = get_client()
    settings_input = Path(input_dir)
    settings_output = Path(output_dir)

    try:
        update_job(
            client,
            job_id,
            JobUpdate(status="running", progress=0, progress_message="Downloading from YouTube..."),
        )
        audio_path = download_audio(url, settings_input, label)

        update_job(
            client,
            job_id,
            JobUpdate(progress=20, progress_message="Loading models..."),
        )
        models = get_models(
            device,
            vad_threshold=vad_threshold,
            whisper_model=whisper_model,
            whisper_hf=whisper_hf,
        )

        update_job(
            client,
            job_id,
            JobUpdate(progress=30, progress_message="Extracting clips..."),
        )
        run_dir = run_pipeline(
            str(audio_path),
            str(settings_output),
            models.vad,
            models.classifier,
            models.transcriber,
            speech_threshold=speech_threshold,
            run_label=label,
        )
        if run_dir is None:
            fail_job(client, job_id, "Pipeline returned no output directory")
            return

        update_job(
            client,
            job_id,
            JobUpdate(progress=80, progress_message="Syncing to Supabase..."),
        )
        sync_run(client, run_dir, label)

        result = (
            client.table("runs")
            .select("id")
            .eq("label", label)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        run_id = result.data[0]["id"] if result.data else ""

        update_job(
            client,
            job_id,
            JobUpdate(
                status="done",
                progress=100,
                result={"run_id": run_id, "run_dir": str(run_dir)},
            ),
        )
    except Exception as exc:
        logger.exception("Ingest job %s failed: %s", job_id, exc)
        fail_job(client, job_id, str(exc))


@router.post("", response_model=IngestResponse)
def ingest(body: IngestRequest, request: Request) -> IngestResponse:
    settings = request.app.state.settings
    client = get_client()
    job_id = create_job(
        client,
        "ingest",
        {
            "url": body.url,
            "label": body.label,
            "whisper_model": body.whisper_model,
            "whisper_hf": body.whisper_hf,
            "vad_threshold": body.vad_threshold,
            "speech_threshold": body.speech_threshold,
        },
    )
    _executor.submit(
        _run_ingest,
        job_id,
        body.url,
        body.label,
        body.whisper_model,
        body.whisper_hf,
        body.vad_threshold,
        body.speech_threshold,
        settings.device,
        str(settings.input_dir),
        str(settings.output_dir),
    )
    return IngestResponse(job_id=job_id)
