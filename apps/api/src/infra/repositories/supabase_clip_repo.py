"""Supabase implementation of ClipRepository."""

from __future__ import annotations

from typing import Any

from supabase import Client

from domain.entities.clip import ClipStatus
from domain.ports.clip_repository import ClipRepository

PAGE_SIZE = 1000


class SupabaseClipRepository(ClipRepository):
    def __init__(self, client: Client) -> None:
        self._client = client

    def upsert_batch(self, run_id: str, rows: list[dict[str, Any]]) -> None:
        for row in rows:
            row["run_id"] = run_id

        batch_size = 500
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            self._client.table("clips").upsert(
                batch, on_conflict="run_id,file_name"
            ).execute()

    def find_by_run(
        self, run_id: str, *, status: ClipStatus | None = None, columns: str = "*"
    ) -> list[dict[str, Any]]:
        filters: dict[str, str] = {"run_id": run_id}
        if status is not None:
            filters["status"] = status.value
        return self._paginate(columns, filters)

    def update_transcription(self, clip_id: str, text: str) -> None:
        self._client.table("clips").update(
            {"draft_transcription": text}
        ).eq("id", clip_id).execute()

    def count_by_status(self, run_id: str) -> dict[ClipStatus, int]:
        counts: dict[ClipStatus, int] = {}
        for status in ClipStatus:
            result = (
                self._client.table("clips")
                .select("id", count="exact")
                .eq("run_id", run_id)
                .eq("status", status.value)
                .execute()
            )
            counts[status] = result.count if result.count is not None else 0
        return counts

    def _paginate(
        self, columns: str, filters: dict[str, str]
    ) -> list[dict[str, Any]]:
        all_rows: list[dict[str, Any]] = []
        offset = 0

        while True:
            query = self._client.table("clips").select(columns)
            for key, value in filters.items():
                query = query.eq(key, value)
            result = query.range(offset, offset + PAGE_SIZE - 1).execute()
            batch = result.data or []
            all_rows.extend(batch)
            if len(batch) < PAGE_SIZE:
                break
            offset += PAGE_SIZE

        return all_rows
