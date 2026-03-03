"""POST /ingest -- start YouTube ingestion job."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Request
from pydantic import BaseModel

from application.types import IngestRequest
from application.use_cases.ingest_run import IngestRun
from infra.clients.ml.model_cache import get_models

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingest"])


class IngestResponse(BaseModel):
    job_id: str


def _run_ingest_job(
    ingest_use_case: object,
    job_id: str,
    url: str,
    label: str,
    settings: object,
    speech_threshold: float,
) -> None:
    ingest_use_case.execute(
        job_id,
        url,
        label,
        input_dir=Path(settings.input_dir),
        output_dir=Path(settings.output_dir),
        speech_threshold=speech_threshold,
    )


@router.post("", response_model=IngestResponse)
def ingest(body: IngestRequest, request: Request) -> IngestResponse:
    settings = request.app.state.settings
    job_repo = request.app.state.job_repo

    models = get_models(
        settings.device,
        vad_threshold=body.vad_threshold,
        whisper_model=body.whisper_model,
        whisper_hf=body.whisper_hf or "",
    )

    ingest_use_case = IngestRun(
        downloader=request.app.state.ingest_downloader,
        vad=models.vad,
        classifier=models.classifier,
        transcriber=models.transcriber,
        sync=request.app.state.sync,
        job_repo=job_repo,
    )

    job_id = job_repo.create(
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

    request.app.state.executor.submit(
        _run_ingest_job,
        ingest_use_case,
        job_id,
        body.url,
        body.label,
        settings,
        body.speech_threshold,
    )

    return IngestResponse(job_id=job_id)
