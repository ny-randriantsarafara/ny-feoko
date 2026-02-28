"""Resolve run identifiers (id or label) to run_id and label."""

from __future__ import annotations

from supabase import Client

from db_sync.exceptions import RunNotFoundError


def resolve_run_id(
    client: Client, run_id: str | None, label: str | None
) -> str:
    """Resolve run_id or label to a run UUID.

    If run_id is provided, returns it. Otherwise looks up the most recent
    run with the given label.

    Raises:
        RunNotFoundError: If neither run_id nor label provided, or no run found.
    """
    if run_id:
        return run_id

    if not label:
        raise RunNotFoundError("Provide --run or --label to identify the run.")

    result = (
        client.table("runs")
        .select("id")
        .eq("label", label)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise RunNotFoundError(f"No run found with label '{label}'")
    return result.data[0]["id"]


def resolve_label(client: Client, run_id: str) -> str:
    """Resolve run_id to its label.

    Raises:
        RunNotFoundError: If no run found with the given id.
    """
    result = (
        client.table("runs")
        .select("label")
        .eq("id", run_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise RunNotFoundError(f"No run found with id '{run_id}'")
    return result.data[0]["label"]
