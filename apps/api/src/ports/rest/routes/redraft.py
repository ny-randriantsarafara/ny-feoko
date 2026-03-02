"""POST /redraft -- start redraft job."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/redraft", tags=["redraft"])


class RedraftRequest(BaseModel):
    run_ids: list[str]
    model_path: str
    device: str | None = None
    language: str = "mg"


class RedraftResponse(BaseModel):
    job_id: str


def _run_redraft_job(
    redraft_use_case: object,
    job_id: str,
    run_ids: list[str],
    model_path: str,
    device: str,
    language: str,
) -> None:
    redraft_use_case.execute(job_id, run_ids, model_path, device, language)


@router.post("", response_model=RedraftResponse)
def redraft(body: RedraftRequest, request: Request) -> RedraftResponse:
    settings = request.app.state.settings
    device = body.device or settings.device
    job_repo = request.app.state.job_repo

    job_id = job_repo.create(
        "redraft",
        {
            "run_ids": body.run_ids,
            "model_path": body.model_path,
            "device": device,
            "language": body.language,
        },
    )

    request.app.state.executor.submit(
        _run_redraft_job,
        request.app.state.redraft,
        job_id,
        body.run_ids,
        body.model_path,
        device,
        body.language,
    )

    return RedraftResponse(job_id=job_id)
