"""Sync a local extraction run to Supabase (metadata + audio clips)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.progress import Progress
from supabase import Client

console = Console()

CSV_TO_DB_COLUMNS: dict[str, str] = {
    "file_name": "file_name",
    "source_file": "source_file",
    "start_sec": "start_sec",
    "end_sec": "end_sec",
    "duration_sec": "duration_sec",
    "speech_score": "speech_score",
    "music_score": "music_score",
    "transcription": "draft_transcription",
}


def sync_run(client: Client, run_dir: Path, label: str) -> None:
    """Create a run, upload clips, and upsert metadata."""
    metadata_path = run_dir / "metadata.csv"
    clips_dir = run_dir / "clips"

    if not metadata_path.exists():
        raise SystemExit(f"metadata.csv not found in {run_dir}")
    if not clips_dir.is_dir():
        raise SystemExit(f"clips/ directory not found in {run_dir}")

    run_id = _create_run(client, label, source=str(run_dir))
    console.print(f"[bold green]Run created:[/] {run_id} ({label})")

    _upload_clips(client, run_id, clips_dir)
    _upsert_metadata(client, run_id, metadata_path)

    console.print("[bold green]Sync complete.[/]")


def _create_run(client: Client, label: str, source: str) -> str:
    result = (
        client.table("runs")
        .insert({"label": label, "source": source})
        .execute()
    )
    return result.data[0]["id"]


def _upload_clips(client: Client, run_id: str, clips_dir: Path) -> None:
    wav_files = sorted(clips_dir.glob("*.wav"))
    if not wav_files:
        console.print("[yellow]No WAV files found in clips/[/]")
        return

    console.print(f"Uploading {len(wav_files)} clips to storage...")

    with Progress() as progress:
        task = progress.add_task("Uploading", total=len(wav_files))
        for wav in wav_files:
            storage_path = f"{run_id}/clips/{wav.name}"
            with open(wav, "rb") as f:
                client.storage.from_("clips").upload(
                    storage_path,
                    f,
                    file_options={"content-type": "audio/wav", "upsert": "true"},
                )
            progress.advance(task)


def _upsert_metadata(client: Client, run_id: str, metadata_path: Path) -> None:
    df = pd.read_csv(metadata_path)
    console.print(f"Upserting {len(df)} clip rows...")

    rows: list[dict[str, object]] = []
    for _, csv_row in df.iterrows():
        db_row: dict[str, object] = {"run_id": run_id}
        for csv_col, db_col in CSV_TO_DB_COLUMNS.items():
            if csv_col in csv_row.index:
                value = csv_row[csv_col]
                db_row[db_col] = None if pd.isna(value) else value
        rows.append(db_row)

    batch_size = 500
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        client.table("clips").upsert(
            batch, on_conflict="run_id,file_name"
        ).execute()

    console.print(f"[bold green]Upserted {len(rows)} clips.[/]")
