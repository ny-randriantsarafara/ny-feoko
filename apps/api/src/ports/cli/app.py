"""Unified CLI for the Ambara platform."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import NoReturn

import torch
import typer
from pydantic import ValidationError

from application.types import ExportRequest, IngestRequest, RedraftRequest, TrainRequest
from domain.exceptions import MissingConfigError, RunNotFoundError, SyncError
from infra.telemetry.logging import configure_cli_logging

logger = logging.getLogger(__name__)

app = typer.Typer(help="Ambara -- Malagasy ASR data pipeline and training platform.")


def _raise_request_validation_error(command_name: str, error: ValidationError) -> NoReturn:
    first_error = error.errors()[0]
    field = ".".join(str(part) for part in first_error.get("loc", [])) or "request"
    message = str(first_error.get("msg", "invalid value"))
    raise typer.BadParameter(f"Invalid {command_name} option `{field}`: {message}") from error


def _build_ingest_request(
    *,
    input_path: str,
    label: str,
    whisper_model: str,
    whisper_hf: str,
    vad_threshold: float,
    speech_threshold: float,
) -> IngestRequest:
    try:
        return IngestRequest(
            url=input_path,
            label=label,
            whisper_model=whisper_model,
            whisper_hf=whisper_hf,
            vad_threshold=vad_threshold,
            speech_threshold=speech_threshold,
        )
    except ValidationError as error:
        _raise_request_validation_error("ingest", error)


def _build_train_request(
    *,
    data_dir: str,
    output_dir: str,
    device: str,
    base_model: str,
    epochs: int,
    batch_size: int,
    lr: float,
    push_to_hub: str | None,
) -> TrainRequest:
    try:
        return TrainRequest(
            data_dir=data_dir,
            output_dir=output_dir,
            device=device,
            base_model=base_model,
            epochs=epochs,
            batch_size=batch_size,
            lr=lr,
            push_to_hub=push_to_hub,
        )
    except ValidationError as error:
        _raise_request_validation_error("train", error)


def _build_export_request(*, run_ids: list[str], output: str, eval_split: float) -> ExportRequest:
    try:
        return ExportRequest(run_ids=run_ids, output=output, eval_split=eval_split)
    except ValidationError as error:
        _raise_request_validation_error("export", error)


def _build_redraft_request(
    *,
    run_ids: list[str],
    model: str,
    device: str,
    language: str,
) -> RedraftRequest:
    try:
        return RedraftRequest(
            run_ids=run_ids,
            model_path=model,
            device=device,
            language=language,
        )
    except ValidationError as error:
        _raise_request_validation_error("redraft", error)


def _purge_python_cache(api_root: Path) -> tuple[int, int]:
    pycache_dirs = sorted(
        (path for path in api_root.rglob("__pycache__") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    removed_dirs = 0
    for cache_dir in pycache_dirs:
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
            removed_dirs += 1

    removed_files = 0
    for bytecode_file in [*api_root.rglob("*.pyc"), *api_root.rglob("*.pyo")]:
        if bytecode_file.exists():
            bytecode_file.unlink()
            removed_files += 1

    return removed_dirs, removed_files


@app.callback()
def main_callback(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
) -> None:
    """Configure CLI before running commands."""
    configure_cli_logging(verbose=verbose)


@app.command()
def ingest(
    input_path: str = typer.Argument(..., help="Input audio file path or YouTube URL"),
    label: str = typer.Option("", "--label", "-l", help="Run label"),
    device: str = typer.Option("auto", "--device", help="Device: auto, mps, cuda, cpu"),
    whisper_model: str = typer.Option("small", "--whisper-model"),
    whisper_hf: str = typer.Option("", "--whisper-hf"),
    vad_threshold: float = typer.Option(0.35, "--vad-threshold"),
    speech_threshold: float = typer.Option(0.35, "--speech-threshold"),
) -> None:
    """Download (if URL) + extract clips + sync to database."""
    request = _build_ingest_request(
        input_path=input_path,
        label=label,
        whisper_model=whisper_model,
        whisper_hf=whisper_hf,
        vad_threshold=vad_threshold,
        speech_threshold=speech_threshold,
    )

    from application.services.audio_processing import detect_device
    from application.services.clip_extraction import run_pipeline
    from application.use_cases.sync_run import SyncRun
    from infra.clients.ml.model_cache import get_models
    from infra.clients.supabase import get_client
    from infra.clients.youtube import YouTubeDownloader
    from infra.repositories.supabase_clip_repo import SupabaseClipRepository
    from infra.repositories.supabase_run_repo import SupabaseRunRepository
    from infra.repositories.supabase_storage import SupabaseAudioStorage

    resolved_device = detect_device(device)

    is_url = request.url.startswith("http://") or request.url.startswith("https://")
    if is_url:
        downloader = YouTubeDownloader()
        audio_path = downloader.download(request.url, Path("data/input"), request.label)
    else:
        audio_path = Path(request.url)
        if not audio_path.exists():
            raise typer.BadParameter(f"Input file not found: {audio_path}")

    models = get_models(
        resolved_device,
        vad_threshold=request.vad_threshold,
        whisper_model=request.whisper_model,
        whisper_hf=request.whisper_hf or "",
    )

    run_dir = run_pipeline(
        str(audio_path),
        "data/output",
        models.vad,
        models.classifier,
        models.transcriber,
        speech_threshold=request.speech_threshold,
        run_label=request.label,
    )
    if run_dir is None:
        typer.echo("No clips extracted.", err=True)
        raise typer.Exit(1)

    client = get_client()
    sync = SyncRun(
        SupabaseRunRepository(client),
        SupabaseClipRepository(client),
        SupabaseAudioStorage(client),
    )
    sync.execute(run_dir, request.label or run_dir.name)
    typer.echo(f"Sync complete: {run_dir}")


@app.command()
def sync(
    dir: Path = typer.Option(..., "--dir", "-d", help="Path to extraction run directory"),
    label: str = typer.Option("", "--label", "-l", help="Run label"),
) -> None:
    """Upload clips and metadata from a local extraction run to database."""
    from application.use_cases.sync_run import SyncRun
    from infra.clients.supabase import get_client
    from infra.repositories.supabase_clip_repo import SupabaseClipRepository
    from infra.repositories.supabase_run_repo import SupabaseRunRepository
    from infra.repositories.supabase_storage import SupabaseAudioStorage

    resolved_dir = dir.resolve()
    if not resolved_dir.is_dir():
        raise typer.BadParameter(f"Directory not found: {resolved_dir}")

    client = get_client()
    use_case = SyncRun(
        SupabaseRunRepository(client),
        SupabaseClipRepository(client),
        SupabaseAudioStorage(client),
    )
    use_case.execute(resolved_dir, label or resolved_dir.name)


@app.command("export")
def export_cmd(
    run_ids: list[str] = typer.Option(..., "--run-id", help="Run UUID(s) to export"),
    output: Path = typer.Option("data/output", "--output", "-o"),
    eval_split: float = typer.Option(0.1, "--eval-split"),
) -> None:
    """Export corrected clips as a HuggingFace training dataset."""
    request = _build_export_request(run_ids=run_ids, output=str(output), eval_split=eval_split)

    from application.use_cases.export_training import ExportTraining
    from infra.clients.supabase import get_client
    from infra.repositories.supabase_clip_repo import SupabaseClipRepository
    from infra.repositories.supabase_run_repo import SupabaseRunRepository
    from infra.repositories.supabase_storage import SupabaseAudioStorage

    client = get_client()
    use_case = ExportTraining(
        SupabaseRunRepository(client),
        SupabaseClipRepository(client),
        SupabaseAudioStorage(client),
    )
    dataset_dir = use_case.execute(
        request.run_ids,
        Path(request.output).resolve(),
        eval_split=request.eval_split,
    )
    typer.echo(f"Exported to {dataset_dir}")


@app.command()
def redraft(
    run_ids: list[str] = typer.Option(..., "--run-id", help="Run UUID(s) to redraft"),
    model: str = typer.Option(..., "--model", "-m", help="Model path or HF repo ID"),
    device: str = typer.Option("auto", "--device"),
    language: str = typer.Option("mg", "--language"),
) -> None:
    """Re-transcribe pending clips using a fine-tuned model."""
    request = _build_redraft_request(
        run_ids=run_ids,
        model=model,
        device=device,
        language=language,
    )

    from application.services.audio_processing import detect_device
    from application.services.training import get_transcriptions
    from domain.entities.clip import ClipStatus
    from infra.clients.supabase import get_client
    from infra.repositories.supabase_clip_repo import SupabaseClipRepository
    from infra.repositories.supabase_run_repo import SupabaseRunRepository

    resolved_device = detect_device(request.device)
    client = get_client()
    run_repo = SupabaseRunRepository(client)
    clip_repo = SupabaseClipRepository(client)

    total_updated = 0
    for run_id in request.run_ids:
        label = run_repo.resolve_label(run_id)
        pending = clip_repo.find_by_run(run_id, status=ClipStatus.PENDING, columns="id,file_name")
        if not pending:
            typer.echo(f"No pending clips for {label}")
            continue

        run = run_repo.find_by_id(run_id)
        source_dir = Path("data/output") / label
        if run and run.source:
            stored = Path(run.source)
            if stored.exists() and (stored / "clips").is_dir():
                source_dir = stored

        transcriptions = get_transcriptions(
            request.model_path,
            source_dir,
            pending,
            resolved_device,
            request.language,
        )
        for clip_id, text in transcriptions:
            clip_repo.update_transcription(clip_id, text)
            total_updated += 1

    typer.echo(f"Updated {total_updated} clips")


@app.command("delete-run")
def delete_run_cmd(
    run_id: str = typer.Option(..., "--run-id", help="Run UUID to delete"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Delete a run and all its clips, edits, and storage files."""
    from application.use_cases.manage_runs import DeleteRun
    from infra.clients.supabase import get_client
    from infra.repositories.supabase_run_repo import SupabaseRunRepository
    from infra.repositories.supabase_storage import SupabaseAudioStorage

    if not yes:
        typer.confirm(f"Delete run {run_id} and all associated data?", abort=True)

    client = get_client()
    use_case = DeleteRun(
        SupabaseRunRepository(client),
        SupabaseAudioStorage(client),
    )
    use_case.execute(run_id)
    typer.echo("Run deleted.")


@app.command()
def train(
    data_dir: Path = typer.Option(..., "--data-dir", "-d"),
    output_dir: Path = typer.Option("models/whisper-mg-v1", "--output-dir", "-o"),
    device: str = typer.Option("auto", "--device"),
    base_model: str = typer.Option("openai/whisper-small", "--base-model"),
    epochs: int = typer.Option(10, "--epochs"),
    batch_size: int = typer.Option(4, "--batch-size"),
    lr: float = typer.Option(1e-5, "--lr"),
    push_to_hub: str | None = typer.Option(None, "--push-to-hub"),
) -> None:
    """Fine-tune Whisper on an exported training dataset."""
    request = _build_train_request(
        data_dir=str(data_dir),
        output_dir=str(output_dir),
        device=device,
        base_model=base_model,
        epochs=epochs,
        batch_size=batch_size,
        lr=lr,
        push_to_hub=push_to_hub,
    )

    from application.services.audio_processing import detect_device
    from application.services.training import TrainingConfig, fine_tune
    from application.services.training import push_to_hub as push_fn

    resolved_device = detect_device(request.device)
    config = TrainingConfig(
        base_model=request.base_model,
        epochs=request.epochs,
        batch_size=request.batch_size,
        learning_rate=request.lr,
    )

    model_dir = fine_tune(
        config,
        Path(request.data_dir).resolve(),
        Path(request.output_dir).resolve(),
        resolved_device,
    )
    typer.echo(f"Model saved to {model_dir}")

    if request.push_to_hub:
        push_fn(model_dir, request.push_to_hub)
        typer.echo(f"Pushed to https://huggingface.co/{request.push_to_hub}")


@app.command()
def api(
    host: str = typer.Option("0.0.0.0", "--host"),
    port: int = typer.Option(8000, "--port"),
) -> None:
    """Start the REST API server."""
    import uvicorn

    uvicorn.run(
        "ports.rest.app:create_app",
        host=host,
        port=port,
        factory=True,
    )


@app.command("purge-api-cache")
def purge_api_cache() -> None:
    """Clear API in-memory model cache and Python bytecode caches."""
    from infra.clients.ml.model_cache import clear_models

    api_root = Path(__file__).resolve().parents[3]
    had_models = clear_models()
    removed_dirs, removed_files = _purge_python_cache(api_root)

    model_state = "cleared" if had_models else "already empty"
    typer.echo(
        "Purged API cache: "
        f"model cache {model_state}, "
        f"removed {removed_dirs} __pycache__ dirs, "
        f"removed {removed_files} bytecode files"
    )


def main() -> None:
    try:
        app()
    except torch.cuda.OutOfMemoryError as e:
        logger.error("CUDA out of memory: %s", e)
        logger.error(
            "Suggestion: Reduce --batch-size to 1 or 2, especially for whisper-medium/large"
        )
        raise typer.Exit(1) from e
    except (RunNotFoundError, MissingConfigError, SyncError) as e:
        logger.error("Error: %s", e)
        raise typer.Exit(1) from e
    except Exception as e:
        logger.exception("Unexpected error: %s", e)
        raise typer.Exit(1) from e


if __name__ == "__main__":
    main()
