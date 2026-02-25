"""CLI for Whisper fine-tuning and re-drafting pending clips."""

from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(help="Ambara ASR training — fine-tune Whisper and re-draft pending clips.")


def _detect_device(requested: str) -> str:
    if requested != "auto":
        return requested

    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


@app.command()
def train(
    data_dir: Path = typer.Option(
        ..., "--data-dir", "-d", help="Path to exported training dataset"
    ),
    output_dir: Path = typer.Option(
        "models/whisper-mg-v1", "--output-dir", "-o", help="Where to save the fine-tuned model"
    ),
    device: str = typer.Option(
        "auto", "--device", help="Device: auto, mps, cuda, cpu"
    ),
    base_model: str = typer.Option(
        "openai/whisper-small", "--base-model", help="HuggingFace model ID to fine-tune"
    ),
    epochs: int = typer.Option(10, "--epochs", help="Number of training epochs"),
    batch_size: int = typer.Option(4, "--batch-size", help="Per-device batch size"),
    lr: float = typer.Option(1e-5, "--lr", help="Learning rate"),
    push_to_hub: str | None = typer.Option(
        None, "--push-to-hub", help="HuggingFace repo ID to push the model to"
    ),
) -> None:
    """Fine-tune Whisper on an exported training dataset."""
    from asr_training.config import TrainingConfig
    from asr_training.train import fine_tune
    from asr_training.train import push_to_hub as push_fn

    resolved_data = data_dir.resolve()
    if not resolved_data.is_dir():
        raise typer.BadParameter(f"Dataset directory not found: {resolved_data}")

    resolved_device = _detect_device(device)
    config = TrainingConfig(
        base_model=base_model,
        epochs=epochs,
        batch_size=batch_size,
        learning_rate=lr,
    )

    model_dir = fine_tune(
        config=config,
        data_dir=resolved_data,
        output_dir=output_dir.resolve(),
        device=resolved_device,
    )

    if push_to_hub:
        push_fn(model_dir, push_to_hub)


@app.command("re-draft")
def re_draft(
    model: str = typer.Option(
        ..., "--model", "-m", help="Path to fine-tuned model or HuggingFace repo ID"
    ),
    source_dir: Path = typer.Option(
        ..., "--source-dir", "-d", help="Local directory containing clips/ from the extraction run"
    ),
    run: str | None = typer.Option(None, "--run", help="Run UUID"),
    label: str | None = typer.Option(
        None, "--label", "-l", help="Run label (uses most recent match)"
    ),
    device: str = typer.Option(
        "auto", "--device", help="Device: auto, mps, cuda, cpu"
    ),
) -> None:
    """Re-transcribe pending clips using a fine-tuned model and update Supabase."""
    from asr_training.redraft import redraft_pending
    from db_sync.export import _resolve_run_id
    from db_sync.supabase_client import get_client

    resolved_source = source_dir.resolve()
    if not resolved_source.is_dir():
        raise typer.BadParameter(f"Directory not found: {resolved_source}")

    client = get_client()
    run_id = _resolve_run_id(client, run_id=run, label=label)
    resolved_device = _detect_device(device)

    redraft_pending(
        client=client,
        model_path=model,
        source_dir=resolved_source,
        run_id=run_id,
        device=resolved_device,
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
