"""GET /jobs -- query job status."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
def list_jobs(request: Request, limit: int = 20) -> list[dict[str, Any]]:
    job_repo = request.app.state.job_repo
    return job_repo.list_recent(limit=limit)


@router.get("/{job_id}")
def get_job(job_id: str, request: Request) -> dict[str, Any]:
    job_repo = request.app.state.job_repo
    job = job_repo.find_by_id(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "id": job.id,
        "type": job.job_type.value,
        "status": job.status.value,
        "progress": job.progress,
        "progress_message": job.progress_message,
        "params": job.params,
        "result": job.result,
        "created_at": job.created_at.isoformat(),
    }
