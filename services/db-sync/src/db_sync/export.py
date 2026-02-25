"""Export corrected clips from Supabase to CSV or training-ready directories."""

from __future__ import annotations

import random
import shutil
from datetime import UTC, datetime
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

    all_rows = _fetch_corrected_clips(client, resolved_run_id, EXPORT_COLUMNS)

    if not all_rows:
        console.print("[yellow]No corrected clips found.[/]")
        return

    df = pd.DataFrame(all_rows, columns=EXPORT_COLUMNS)
    df.to_csv(output, index=False)
    console.print(f"[bold green]Exported {len(df)} clips to {output}[/]")


def export_training(
    client: Client,
    run_id: str | None,
    label: str | None,
    source_dir: Path,
    output: Path,
    eval_split: float,
    seed: int = 42,
) -> Path:
    """Export corrected clips as a HuggingFace audiofolder dataset.

    Creates a timestamped directory under `output` with train/ and test/
    subdirectories, each containing WAV files and a metadata.csv.

    Returns the path to the created dataset directory.
    """
    resolved_run_id = _resolve_run_id(client, run_id, label)
    resolved_label = _resolve_label(client, resolved_run_id)
    console.print(f"Exporting training data for run [bold]{resolved_label}[/]...")

    rows = _fetch_corrected_clips(
        client, resolved_run_id, ["file_name", "corrected_transcription"]
    )
    if not rows:
        raise SystemExit("No corrected clips found for this run.")

    missing = [
        r["file_name"]
        for r in rows
        if not (source_dir / str(r["file_name"])).exists()
    ]
    if missing:
        raise SystemExit(
            f"{len(missing)} clip files not found in {source_dir}. "
            f"First missing: {missing[0]}"
        )

    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d")
    dataset_dir = output / f"{timestamp}_{resolved_label}"
    if dataset_dir.exists():
        raise SystemExit(f"Output directory already exists: {dataset_dir}")

    rng = random.Random(seed)
    shuffled = list(rows)
    rng.shuffle(shuffled)

    split_idx = max(1, int(len(shuffled) * (1 - eval_split)))
    train_rows = shuffled[:split_idx]
    test_rows = shuffled[split_idx:]

    _write_split(source_dir, dataset_dir / "train", train_rows)
    if test_rows:
        _write_split(source_dir, dataset_dir / "test", test_rows)

    console.print(
        f"[bold green]Exported {len(rows)} clips "
        f"({len(train_rows)} train, {len(test_rows)} test) "
        f"to {dataset_dir}[/]"
    )
    return dataset_dir


def _write_split(
    source_dir: Path,
    split_dir: Path,
    rows: list[dict[str, object]],
) -> None:
    """Copy WAV files and write metadata.csv for one split."""
    split_dir.mkdir(parents=True)

    for row in rows:
        src = source_dir / str(row["file_name"])
        shutil.copy2(src, split_dir / src.name)

    df = pd.DataFrame(
        [
            {
                "file_name": Path(str(row["file_name"])).name,
                "transcription": row["corrected_transcription"],
            }
            for row in rows
        ]
    )
    df.to_csv(split_dir / "metadata.csv", index=False)


def _fetch_corrected_clips(
    client: Client,
    run_id: str,
    columns: list[str],
) -> list[dict[str, object]]:
    """Paginate through all corrected clips for a run."""
    all_rows: list[dict[str, object]] = []
    page_size = 1000
    offset = 0

    while True:
        result = (
            client.table("clips")
            .select(",".join(columns))
            .eq("run_id", run_id)
            .eq("status", "corrected")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        if not result.data:
            break
        all_rows.extend(result.data)
        if len(result.data) < page_size:
            break
        offset += page_size

    return all_rows


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


def _resolve_label(client: Client, run_id: str) -> str:
    result = (
        client.table("runs")
        .select("label")
        .eq("id", run_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise SystemExit(f"No run found with id '{run_id}'")
    return result.data[0]["label"]
