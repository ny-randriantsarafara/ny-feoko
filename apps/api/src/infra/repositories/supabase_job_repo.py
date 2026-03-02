"""Supabase implementation of JobRepository."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from supabase import Client

from domain.entities.job import Job, JobStatus, JobType
from domain.ports.job_repository import JobRepository


class SupabaseJobRepository(JobRepository):
    def __init__(self, client: Client) -> None:
        self._client = client

    def create(self, job_type: str, params: dict[str, Any]) -> str:
        row = (
            self._client.table("jobs")
            .insert({"type": job_type, "status": "queued", "params": params})
            .execute()
        )
        return str(row.data[0]["id"])

    def update(
        self,
        job_id: str,
        *,
        status: str | None = None,
        progress: int | None = None,
        progress_message: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {}
        if status is not None:
            payload["status"] = status
        if progress is not None:
            payload["progress"] = progress
        if progress_message is not None:
            payload["progress_message"] = progress_message
        if result is not None:
            payload["result"] = result
        if payload:
            self._client.table("jobs").update(payload).eq("id", job_id).execute()

    def fail(self, job_id: str, error: str) -> None:
        self.update(job_id, status="failed", result={"error": error})

    def find_by_id(self, job_id: str) -> Job | None:
        result = (
            self._client.table("jobs")
            .select("*")
            .eq("id", job_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        return self._to_entity(result.data[0])

    def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        result = (
            self._client.table("jobs")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []

    @staticmethod
    def _to_entity(row: dict[str, Any]) -> Job:
        return Job(
            id=str(row["id"]),
            job_type=JobType(str(row["type"])),
            status=JobStatus(str(row["status"])),
            progress=int(row.get("progress", 0)),
            progress_message=row.get("progress_message"),
            params=row.get("params", {}),
            result=row.get("result"),
            created_at=datetime.fromisoformat(str(row["created_at"])),
        )
