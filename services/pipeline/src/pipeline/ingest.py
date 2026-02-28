"""Ingest pipeline: download (optional) + extract + sync to Supabase."""

from __future__ import annotations

import time
from pathlib import Path

from ny_feoko_shared.formatting import format_duration
from rich.console import Console

console = Console()


def _is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def ingest(
    input_path: str,
    label: str,
    device: str,
    *,
    input_dir: Path = Path("data/input"),
    output_dir: Path = Path("data/output"),
    whisper_model: str = "small",
    whisper_hf: str = "",
    vad_threshold: float = 0.35,
    speech_threshold: float = 0.35,
    verbose: bool = False,
) -> Path:
    """Run the full ingest pipeline: download (if URL) -> extract -> sync.

    Returns the extraction run directory path.
    """
    t_start = time.monotonic()

    t0 = time.monotonic()
    wav_path = _resolve_input(input_path, label, input_dir)
    download_sec = time.monotonic() - t0

    t0 = time.monotonic()
    run_dir = _extract(
        wav_path,
        output_dir,
        device,
        label,
        whisper_model=whisper_model,
        whisper_hf=whisper_hf,
        vad_threshold=vad_threshold,
        speech_threshold=speech_threshold,
        verbose=verbose,
    )
    extract_sec = time.monotonic() - t0

    t0 = time.monotonic()
    _sync(run_dir, label or run_dir.name)
    sync_sec = time.monotonic() - t0

    total_sec = time.monotonic() - t_start

    _print_ingest_summary(
        run_dir=run_dir,
        is_url=_is_url(input_path),
        download_sec=download_sec,
        extract_sec=extract_sec,
        sync_sec=sync_sec,
        total_sec=total_sec,
    )

    return run_dir


def _resolve_input(input_path: str, label: str, input_dir: Path) -> Path:
    """Download from YouTube if URL, otherwise validate local file."""
    if _is_url(input_path):
        from yt_download.cli import download_audio

        console.print("[bold]Downloading from YouTube...[/]")
        return download_audio(input_path, input_dir, label)

    path = Path(input_path)
    if not path.exists():
        raise SystemExit(f"Input file not found: {path}")
    return path


def _extract(
    wav_path: Path,
    output_dir: Path,
    device: str,
    label: str,
    *,
    whisper_model: str,
    whisper_hf: str,
    vad_threshold: float,
    speech_threshold: float,
    verbose: bool,
) -> Path:
    """Run the clip extraction pipeline."""
    from clip_extraction.infrastructure.classifier import ASTClassifier
    from clip_extraction.infrastructure.vad import SileroVAD
    from clip_extraction.pipeline import run_pipeline

    console.print("[bold]Loading extraction models...[/]")
    vad = SileroVAD(threshold=vad_threshold)
    classifier = ASTClassifier(device=device)

    if whisper_hf:
        from clip_extraction.infrastructure.hf_transcriber import HuggingFaceTranscriber

        console.print(f"[bold]Using HuggingFace model:[/] {whisper_hf}")
        transcriber = HuggingFaceTranscriber(model_id=whisper_hf, device=device)
    else:
        from clip_extraction.infrastructure.transcriber import WhisperTranscriber

        transcriber = WhisperTranscriber(model_name=whisper_model, device=device)

    console.print("[bold green]Models loaded.[/]")

    return run_pipeline(
        input_file=str(wav_path),
        output_dir=str(output_dir),
        vad=vad,
        classifier=classifier,
        transcriber=transcriber,
        speech_threshold=speech_threshold,
        verbose=verbose,
        run_label=label,
    )


def _sync(run_dir: Path, label: str) -> None:
    """Sync extraction run to Supabase."""
    from db_sync.supabase_client import get_client
    from db_sync.sync import sync_run

    console.print("\n[bold]Syncing to Supabase...[/]")
    client = get_client()
    sync_run(client, run_dir, label)


def _print_ingest_summary(
    *,
    run_dir: Path,
    is_url: bool,
    download_sec: float,
    extract_sec: float,
    sync_sec: float,
    total_sec: float,
) -> None:
    """Print a summary panel for the ingest pipeline."""
    from rich.panel import Panel
    from rich.table import Table

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("step", style="dim")
    table.add_column("time")

    if is_url:
        table.add_row("Download", format_duration(download_sec))
    table.add_row("Extract", format_duration(extract_sec))
    table.add_row("Sync to Supabase", format_duration(sync_sec))
    table.add_row("Total", f"[bold]{format_duration(total_sec)}[/]")

    console.print()
    console.print(Panel(table, title="Ingest Timing", border_style="blue"))

    next_step = (
        f"  Run [bold]./ambara editor[/] to start correcting transcripts.\n"
        f"  Output directory: {run_dir}"
    )
    console.print(Panel(next_step, title="Next Step", border_style="green"))
