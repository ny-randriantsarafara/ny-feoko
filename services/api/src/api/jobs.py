"""Job lifecycle management — create, update, and query jobs in Supabase."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from supabase import Client


@dataclass(frozen=True)
class JobUpdate:
    status: str | None = None
    progress: int | None = None
    progress_message: str | None = None
    result: dict[str, Any] | None = None


def create_job(
    client: Client,
    job_type: str,
    params: dict[str, Any],
) -> str:
    row = (
        client.table("jobs")
        .insert({"type": job_type, "status": "queued", "params": params})
        .execute()
    )
    return str(row.data[0]["id"])


def update_job(client: Client, job_id: str, update: JobUpdate) -> None:
    payload: dict[str, Any] = {}
    if update.status is not None:
        payload["status"] = update.status
    if update.progress is not None:
        payload["progress"] = update.progress
    if update.progress_message is not None:
        payload["progress_message"] = update.progress_message
    if update.result is not None:
        payload["result"] = update.result
    if payload:
        client.table("jobs").update(payload).eq("id", job_id).execute()


def fail_job(client: Client, job_id: str, error: str) -> None:
    update_job(
        client,
        job_id,
        JobUpdate(status="failed", result={"error": error}),
    )


def get_job(client: Client, job_id: str) -> dict[str, Any] | None:
    result = (
        client.table("jobs")
        .select("*")
        .eq("id", job_id)
        .limit(1)
        .execute()
    )
    if result.data:
        return result.data[0]
    return None


def list_recent_jobs(client: Client, limit: int = 20) -> list[dict[str, Any]]:
    result = (
        client.table("jobs")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data
