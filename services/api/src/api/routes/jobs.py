"""GET /jobs — query job status."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.jobs import get_job, list_recent_jobs
from db_sync.supabase_client import get_client

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
def list_jobs(limit: int = 20) -> list[dict]:
    client = get_client()
    return list_recent_jobs(client, limit=limit)


@router.get("/{job_id}")
def get_job_route(job_id: str) -> dict:
    client = get_client()
    job = get_job(client, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
