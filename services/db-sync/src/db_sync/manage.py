"""Management operations: delete runs, reset database, clean up orphans."""

from __future__ import annotations

from rich.console import Console
from supabase import Client

from db_sync.exceptions import RunNotFoundError

console = Console()


def delete_run(client: Client, run_id: str) -> None:
    """Delete a single run, its clips/edits (via cascade), and its storage objects."""
    run = _fetch_run(client, run_id)
    clip_count, corrected_count = _count_clips(client, run_id)

    console.print(f"[bold]Run:[/]       {run['label']}  ({run_id})")
    console.print(f"[bold]Clips:[/]     {clip_count}  ({corrected_count} corrected)")

    _remove_storage_prefix(client, run_id)
    client.table("runs").delete().eq("id", run_id).execute()

    console.print("[bold green]Run deleted.[/]")


def reset_all(client: Client) -> None:
    """Wipe all runs, clips, clip_edits, and storage objects."""
    run_count = _count_table(client, "runs")
    clip_count = _count_table(client, "clips")
    edit_count = _count_table(client, "clip_edits")

    console.print(f"[bold]Runs:[/]       {run_count}")
    console.print(f"[bold]Clips:[/]      {clip_count}")
    console.print(f"[bold]Edits:[/]      {edit_count}")

    run_ids = _all_run_ids(client)
    for rid in run_ids:
        _remove_storage_prefix(client, rid)

    client.table("clip_edits").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    client.table("clips").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    client.table("runs").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()

    console.print("[bold green]Database and storage wiped.[/]")


def cleanup(
    client: Client,
    empty_runs: list[dict[str, object]],
    orphan_prefixes: list[str],
) -> None:
    """Remove pre-identified orphaned data."""
    for run in empty_runs:
        _remove_storage_prefix(client, run["id"])
        client.table("runs").delete().eq("id", run["id"]).execute()

    for prefix in orphan_prefixes:
        _remove_storage_prefix(client, prefix)

    console.print("[bold green]Cleanup complete.[/]")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_run(client: Client, run_id: str) -> dict[str, object]:
    result = client.table("runs").select("*").eq("id", run_id).maybe_single().execute()
    if not result.data:
        raise RunNotFoundError(f"Run not found: {run_id}")
    return result.data


def _count_clips(client: Client, run_id: str) -> tuple[int, int]:
    total = (
        client.table("clips")
        .select("*", count="exact", head=True)
        .eq("run_id", run_id)
        .execute()
    )
    corrected = (
        client.table("clips")
        .select("*", count="exact", head=True)
        .eq("run_id", run_id)
        .eq("status", "corrected")
        .execute()
    )
    return total.count or 0, corrected.count or 0


def _count_table(client: Client, table: str) -> int:
    result = client.table(table).select("*", count="exact", head=True).execute()
    return result.count or 0


def _all_run_ids(client: Client) -> list[str]:
    result = client.table("runs").select("id").execute()
    return [row["id"] for row in (result.data or [])]


def _remove_storage_prefix(client: Client, prefix: str) -> None:
    """Remove all objects under a given prefix in the clips bucket."""
    objects = client.storage.from_("clips").list(prefix)
    if not objects:
        return

    paths = [f"{prefix}/{obj['name']}" for obj in objects]

    sub_folders = [obj for obj in objects if obj.get("id") is None]
    for folder in sub_folders:
        sub_path = f"{prefix}/{folder['name']}"
        sub_objects = client.storage.from_("clips").list(sub_path)
        if sub_objects:
            paths.extend(f"{sub_path}/{obj['name']}" for obj in sub_objects)

    file_paths = [p for p in paths if not p.endswith("/")]
    if file_paths:
        client.storage.from_("clips").remove(file_paths)


def _find_empty_runs(client: Client) -> list[dict[str, object]]:
    """Find runs that have zero clips."""
    all_runs = client.table("runs").select("id,label").execute()
    empty: list[dict[str, object]] = []
    for run in all_runs.data or []:
        count_result = (
            client.table("clips")
            .select("*", count="exact", head=True)
            .eq("run_id", run["id"])
            .execute()
        )
        if (count_result.count or 0) == 0:
            empty.append(run)
    return empty


def _find_orphan_storage_prefixes(client: Client) -> list[str]:
    """Find top-level storage prefixes that don't match any run ID."""
    top_level = client.storage.from_("clips").list("")
    if not top_level:
        return []

    run_ids = set(_all_run_ids(client))
    return [
        obj["name"]
        for obj in top_level
        if obj.get("id") is None and obj["name"] not in run_ids
    ]
