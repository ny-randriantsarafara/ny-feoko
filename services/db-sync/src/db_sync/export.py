"""Export corrected clips from Supabase to CSV."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from rich.console import Console
from supabase import Client

console = Console()

EXPORT_COLUMNS = [
    "file_name",
    "source_file",
    "start_sec",
    "end_sec",
    "duration_sec",
    "speech_score",
    "music_score",
    "draft_transcription",
    "corrected_transcription",
]


def export_corrected(
    client: Client,
    run_id: str | None,
    label: str | None,
    output: Path,
) -> None:
    """Export corrected clips to a CSV file."""
    resolved_run_id = _resolve_run_id(client, run_id, label)
    console.print(f"Exporting corrected clips for run [bold]{resolved_run_id}[/]...")

    all_rows: list[dict[str, object]] = []
    page_size = 1000
    offset = 0

    while True:
        query = (
            client.table("clips")
            .select(",".join(EXPORT_COLUMNS))
            .eq("run_id", resolved_run_id)
            .eq("status", "corrected")
            .range(offset, offset + page_size - 1)
        )
        result = query.execute()
        if not result.data:
            break
        all_rows.extend(result.data)
        if len(result.data) < page_size:
            break
        offset += page_size

    if not all_rows:
        console.print("[yellow]No corrected clips found.[/]")
        return

    df = pd.DataFrame(all_rows, columns=EXPORT_COLUMNS)
    df.to_csv(output, index=False)
    console.print(f"[bold green]Exported {len(df)} clips to {output}[/]")


def _resolve_run_id(
    client: Client, run_id: str | None, label: str | None
) -> str:
    if run_id:
        return run_id

    if not label:
        raise SystemExit("Provide --run or --label to identify the run.")

    result = (
        client.table("runs")
        .select("id")
        .eq("label", label)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise SystemExit(f"No run found with label '{label}'")
    return result.data[0]["id"]
