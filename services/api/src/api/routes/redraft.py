"""POST /redraft — start redraft job (re-transcribe pending clips)."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Request
from pydantic import BaseModel

from api.jobs import JobUpdate, create_job, fail_job, update_job
from db_sync.supabase_client import get_client

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=1)

router = APIRouter(prefix="/redraft", tags=["redraft"])


class RedraftRequest(BaseModel):
    label: str
    model_path: str
    device: str | None = None
    language: str = "mg"


class RedraftResponse(BaseModel):
    job_id: str


def _run_redraft(
    job_id: str,
    label: str,
    model_path: str,
    device: str,
    language: str,
) -> None:
    from asr_training.redraft import redraft_pending
    from db_sync.run_resolution import resolve_run_id
    from db_sync.supabase_client import get_client
    from pipeline.iterate import _ensure_source_dir

    client = get_client()

    try:
        update_job(
            client,
            job_id,
            JobUpdate(status="running", progress=0, progress_message="Resolving run..."),
        )
        run_id = resolve_run_id(client, run_id=None, label=label)

        update_job(
            client,
            job_id,
            JobUpdate(progress=10, progress_message="Locating source audio..."),
        )
        source_dir = _ensure_source_dir(client, run_id, label)

        update_job(
            client,
            job_id,
            JobUpdate(progress=20, progress_message="Loading model and re-drafting..."),
        )
        clips_updated = redraft_pending(client, model_path, source_dir, run_id, device, language)

        update_job(
            client,
            job_id,
            JobUpdate(
                status="done",
                progress=100,
                result={"run_id": run_id, "clips_updated": clips_updated},
            ),
        )
    except Exception as exc:
        logger.exception("Redraft job %s failed: %s", job_id, exc)
        fail_job(client, job_id, str(exc))


@router.post("", response_model=RedraftResponse)
def redraft(body: RedraftRequest, request: Request) -> RedraftResponse:
    settings = request.app.state.settings
    device = body.device or settings.device
    client = get_client()
    job_id = create_job(
        client,
        "redraft",
        {
            "label": body.label,
            "model_path": body.model_path,
            "device": device,
            "language": body.language,
        },
    )
    _executor.submit(_run_redraft, job_id, body.label, body.model_path, device, body.language)
    return RedraftResponse(job_id=job_id)
