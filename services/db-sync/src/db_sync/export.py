"""Export corrected clips from Supabase to CSV or training-ready directories."""

from __future__ import annotations

import random
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from rich.console import Console
from supabase import Client

from db_sync.exceptions import RunNotFoundError, SyncError
from db_sync.pagination import paginate_table
from db_sync.run_resolution import resolve_label, resolve_run_id

# Backward compatibility for pipeline/iterate.py and asr-training/cli.py
_resolve_run_id = resolve_run_id

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
    resolved_run_id = resolve_run_id(client, run_id, label)
    console.print(f"Exporting corrected clips for run [bold]{resolved_run_id}[/]...")

    all_rows = _fetch_corrected_clips(client, resolved_run_id, EXPORT_COLUMNS)

    if not all_rows:
        console.print("[yellow]No corrected clips found.[/]")
        return

    df = pd.DataFrame(all_rows, columns=EXPORT_COLUMNS)
    df.to_csv(output, index=False)
    console.print(f"[bold green]Exported {len(df)} clips to {output}[/]")


def fetch_clip_status_counts(client: Client, run_id: str) -> dict[str, int]:
    """Fetch clip counts by status for a run. Returns {status: count}."""
    counts: dict[str, int] = {"pending": 0, "corrected": 0, "discarded": 0}
    for status in counts:
        result = (
            client.table("clips")
            .select("id", count="exact")
            .eq("run_id", run_id)
            .eq("status", status)
            .execute()
        )
        counts[status] = result.count if result.count is not None else 0
    return counts


def export_training(
    client: Client,
    run_id: str | None,
    label: str | None,
    source_dir: Path,
    output: Path,
    eval_split: float,
    seed: int = 42,
    overwrite: bool = False,
) -> Path:
    """Export corrected clips as a HuggingFace audiofolder dataset.

    Creates a timestamped directory under `output` with train/ and test/
    subdirectories, each containing WAV files and a metadata.csv.

    Returns the path to the created dataset directory.
    """
    resolved_run_id = resolve_run_id(client, run_id, label)
    resolved_label = resolve_label(client, resolved_run_id)
    console.print(f"Exporting training data for run [bold]{resolved_label}[/]...")

    counts = fetch_clip_status_counts(client, resolved_run_id)
    total = sum(counts.values())
    console.print(
        f"  Clips in run: [bold]{total}[/]  "
        f"([green]{counts['corrected']} corrected[/], "
        f"{counts['pending']} pending, "
        f"[dim]{counts['discarded']} discarded[/])"
    )

    rows = _fetch_corrected_clips(
        client, resolved_run_id, ["file_name", "corrected_transcription"]
    )
    if not rows:
        raise SyncError("No corrected clips found for this run.")

    word_counts = [
        len(str(r["corrected_transcription"]).split())
        for r in rows
        if r["corrected_transcription"]
    ]
    empty_count = sum(1 for r in rows if not r["corrected_transcription"])

    if word_counts:
        avg_words = sum(word_counts) / len(word_counts)
        console.print(f"  Avg transcription length: {avg_words:.1f} words")

    if empty_count > 0:
        console.print(
            f"  [yellow]Warning: {empty_count} corrected clips have empty transcriptions[/]"
        )

    short_count = sum(1 for wc in word_counts if wc <= 2)
    if short_count > 0:
        console.print(
            f"  [yellow]Warning: {short_count} clips have very short transcriptions "
            f"(1-2 words) — verify they are correct[/]"
        )

    missing = [
        r["file_name"]
        for r in rows
        if not (source_dir / str(r["file_name"])).exists()
    ]
    if missing:
        raise SyncError(
            f"{len(missing)} clip files not found in {source_dir}. "
            f"First missing: {missing[0]}"
        )

    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d")
    dataset_dir = output / f"{timestamp}_{resolved_label}"
    if dataset_dir.exists():
        if overwrite:
            shutil.rmtree(dataset_dir)
        else:
            raise SyncError(f"Output directory already exists: {dataset_dir}")

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
    return paginate_table(
        client,
        "clips",
        columns=",".join(columns),
        filters={"run_id": run_id, "status": "corrected"},
    )
