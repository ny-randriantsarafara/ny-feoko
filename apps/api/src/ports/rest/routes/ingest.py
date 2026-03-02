"""POST /ingest -- start YouTube ingestion job."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Request
from pydantic import BaseModel

from infra.clients.ml.model_cache import get_models

logger = logging.getLogger(__name__)

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
        whisper_hf=body.whisper_hf,
    )

    ingest_use_case = request.app.state.ingest
    ingest_use_case._vad = models.vad
    ingest_use_case._classifier = models.classifier
    ingest_use_case._transcriber = models.transcriber

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
