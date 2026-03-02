"""Supabase implementation of RunRepository."""

from __future__ import annotations

from datetime import datetime

from supabase import Client

from domain.entities.run import Run, RunType
from domain.exceptions import RunNotFoundError
from domain.ports.run_repository import RunRepository


class SupabaseRunRepository(RunRepository):
    def __init__(self, client: Client) -> None:
        self._client = client

    def create(self, label: str, source: str | None, run_type: RunType) -> str:
        payload: dict[str, object] = {"label": label, "type": run_type.value}
        if source is not None:
            payload["source"] = source
        result = self._client.table("runs").insert(payload).execute()
        return str(result.data[0]["id"])

    def find_by_id(self, run_id: str) -> Run | None:
        result = (
            self._client.table("runs")
            .select("*")
            .eq("id", run_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        return self._to_entity(result.data[0])

    def find_by_label(self, label: str) -> Run | None:
        result = (
            self._client.table("runs")
            .select("*")
            .eq("label", label)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        return self._to_entity(result.data[0])

    def list_all(self) -> list[Run]:
        result = (
            self._client.table("runs")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )
        return [self._to_entity(row) for row in (result.data or [])]

    def delete(self, run_id: str) -> None:
        self._client.table("runs").delete().eq("id", run_id).execute()

    def resolve_run_id(self, run_id: str | None, label: str | None) -> str:
        if run_id:
            return run_id

        if not label:
            raise RunNotFoundError("Provide run_id or label to identify the run.")

        result = (
            self._client.table("runs")
            .select("id")
            .eq("label", label)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if not result.data:
            raise RunNotFoundError(f"No run found with label '{label}'")
        return str(result.data[0]["id"])

    def resolve_label(self, run_id: str) -> str:
        result = (
            self._client.table("runs")
            .select("label")
            .eq("id", run_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            raise RunNotFoundError(f"No run found with id '{run_id}'")
        return str(result.data[0]["label"])

    @staticmethod
    def _to_entity(row: dict[str, object]) -> Run:
        return Run(
            id=str(row["id"]),
            label=str(row["label"]),
            source=str(row["source"]) if row.get("source") else None,
            run_type=RunType(str(row.get("type", "extraction"))),
            created_at=datetime.fromisoformat(str(row["created_at"])),
        )
