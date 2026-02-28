"""Iterate pipeline: export training data + train Whisper + re-draft pending clips."""

from __future__ import annotations

import time
from pathlib import Path

from ny_feoko_shared.formatting import format_duration
from rich.console import Console
from supabase import Client

from db_sync.export import _resolve_run_id
from db_sync.supabase_client import get_client

console = Console()


def iterate(
    label: str,
    device: str,
    *,
    output_model_dir: Path = Path("models/whisper-mg-v1"),
    training_data_dir: Path = Path("data/training"),
    eval_split: float = 0.1,
    base_model: str = "openai/whisper-small",
    epochs: int = 10,
    batch_size: int = 4,
    lr: float = 1e-5,
    push_to_hub: str | None = None,
) -> Path:
    """Run the full iterate pipeline: export -> train -> re-draft.

    Returns the path to the trained model directory.
    """
    t_start = time.monotonic()

    client = get_client()
    run_id = _resolve_run_id(client, run_id=None, label=label)

    source_dir = _ensure_source_dir(client, run_id, label)

    counts_before = _fetch_status_counts(client, run_id)

    console.print("\n[bold]Step 1/3 — Exporting training data...[/]")
    t0 = time.monotonic()
    dataset_dir = _export(
        client=client, run_id=run_id, source_dir=source_dir,
        output=training_data_dir, eval_split=eval_split,
    )
    export_sec = time.monotonic() - t0

    console.print("\n[bold]Step 2/3 — Training Whisper...[/]")
    t0 = time.monotonic()
    model_dir = _train(
        dataset_dir=dataset_dir, output_dir=output_model_dir, device=device,
        base_model=base_model, epochs=epochs, batch_size=batch_size, lr=lr,
    )
    train_sec = time.monotonic() - t0

    if push_to_hub:
        _push(model_dir, push_to_hub)

    console.print("\n[bold]Step 3/3 — Re-drafting pending clips...[/]")
    t0 = time.monotonic()
    model_path = push_to_hub if push_to_hub else str(model_dir)
    redrafted = _redraft(
        client=client, model_path=model_path, source_dir=source_dir,
        run_id=run_id, device=device,
    )
    redraft_sec = time.monotonic() - t0

    total_sec = time.monotonic() - t_start

    _print_iterate_summary(
        model_dir=model_dir,
        push_to_hub=push_to_hub,
        counts_before=counts_before,
        redrafted=redrafted,
        export_sec=export_sec,
        train_sec=train_sec,
        redraft_sec=redraft_sec,
        total_sec=total_sec,
    )

    return model_dir


def _fetch_status_counts(client: Client, run_id: str) -> dict[str, int]:
    from db_sync.export import fetch_clip_status_counts

    return fetch_clip_status_counts(client, run_id)


def _ensure_source_dir(client: Client, run_id: str, label: str) -> Path:
    """Get the local source directory for a run, downloading clips from Storage if needed."""
    result = (
        client.table("runs")
        .select("source")
        .eq("id", run_id)
        .limit(1)
        .execute()
    )
    if result.data:
        stored_path = Path(result.data[0]["source"])
        if stored_path.exists() and (stored_path / "clips").is_dir():
            console.print(f"Using local clips: [bold]{stored_path}[/]")
            return stored_path

    dest_dir = Path("data/output") / label
    console.print("Local clips not found, downloading from Supabase Storage...")
    from db_sync.sync import download_run_clips

    download_run_clips(client, run_id, dest_dir)
    return dest_dir


def _export(
    client: Client,
    run_id: str,
    source_dir: Path,
    output: Path,
    eval_split: float,
) -> Path:
    from db_sync.export import export_training

    return export_training(
        client,
        run_id=run_id,
        label=None,
        source_dir=source_dir,
        output=output,
        eval_split=eval_split,
        overwrite=True,
    )


def _train(
    dataset_dir: Path,
    output_dir: Path,
    device: str,
    base_model: str,
    epochs: int,
    batch_size: int,
    lr: float,
) -> Path:
    from asr_training.config import TrainingConfig
    from asr_training.train import fine_tune

    config = TrainingConfig(
        base_model=base_model,
        epochs=epochs,
        batch_size=batch_size,
        learning_rate=lr,
    )

    return fine_tune(
        config=config,
        data_dir=dataset_dir,
        output_dir=output_dir.resolve(),
        device=device,
    )


def _push(model_dir: Path, repo_id: str) -> None:
    from asr_training.train import push_to_hub

    push_to_hub(model_dir, repo_id)


def _redraft(
    client: Client,
    model_path: str,
    source_dir: Path,
    run_id: str,
    device: str,
) -> int:
    from asr_training.redraft import redraft_pending

    return redraft_pending(
        client=client,
        model_path=model_path,
        source_dir=source_dir,
        run_id=run_id,
        device=device,
    )


def _print_iterate_summary(
    *,
    model_dir: Path,
    push_to_hub: str | None,
    counts_before: dict[str, int],
    redrafted: int,
    export_sec: float,
    train_sec: float,
    redraft_sec: float,
    total_sec: float,
) -> None:
    from rich.panel import Panel
    from rich.table import Table

    timing = Table(show_header=False, box=None, padding=(0, 2))
    timing.add_column("step", style="dim")
    timing.add_column("time")
    timing.add_row("Export", format_duration(export_sec))
    timing.add_row("Train", format_duration(train_sec))
    timing.add_row("Re-draft", format_duration(redraft_sec))
    timing.add_row("Total", f"[bold]{format_duration(total_sec)}[/]")

    console.print()
    console.print(Panel(timing, title="Iteration Timing", border_style="blue"))

    stats = Table(show_header=False, box=None, padding=(0, 2))
    stats.add_column("metric", style="dim")
    stats.add_column("value")

    corrected = counts_before.get("corrected", 0)
    pending_before = counts_before.get("pending", 0)
    pending_after = pending_before - redrafted

    stats.add_row("Clips used for training", f"[green]{corrected}[/]")
    stats.add_row("Clips re-drafted", str(redrafted))
    stats.add_row(
        "Remaining pending",
        f"{max(0, pending_after)}  (were {pending_before} before re-draft)",
    )
    stats.add_row("Model", str(model_dir))
    if push_to_hub:
        stats.add_row("HuggingFace Hub", f"https://huggingface.co/{push_to_hub}")

    console.print(Panel(stats, title="Iteration Results", border_style="blue"))

    next_lines = [
        "1. Run [bold]./ambara editor[/] to correct the improved drafts",
        "2. Run [bold]./ambara iterate[/] again to train on the new corrections",
        "",
        "[dim]Each iteration produces better drafts, making corrections faster.[/]",
    ]
    console.print(Panel("\n".join(next_lines), title="Next Steps", border_style="green"))
