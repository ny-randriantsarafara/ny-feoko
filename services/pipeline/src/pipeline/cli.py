"""CLI for the ingest and iterate composite commands."""

from __future__ import annotations

from pathlib import Path

import typer

app = typer.Typer(help="Ambara pipeline — composite commands for the full workflow.")


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
def ingest(
    input_path: str = typer.Argument(
        ..., help="Input audio file path or YouTube URL"
    ),
    label: str = typer.Option(
        "", "--label", "-l", help="Run label (defaults to filename or video title)"
    ),
    device: str = typer.Option("auto", "--device", help="Device: auto, mps, cuda, cpu"),
    whisper_model: str = typer.Option(
        "small", "--whisper-model", help="Whisper model size"
    ),
    whisper_hf: str = typer.Option(
        "", "--whisper-hf", help="HuggingFace model ID (overrides --whisper-model)"
    ),
    vad_threshold: float = typer.Option(0.35, "--vad-threshold"),
    speech_threshold: float = typer.Option(0.35, "--speech-threshold"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Download (if URL) + extract clips + sync to Supabase — all in one shot."""
    from pipeline.ingest import ingest as run_ingest

    resolved_device = _detect_device(device)
    run_ingest(
        input_path=input_path,
        label=label,
        device=resolved_device,
        whisper_model=whisper_model,
        whisper_hf=whisper_hf,
        vad_threshold=vad_threshold,
        speech_threshold=speech_threshold,
        verbose=verbose,
    )


@app.command()
def iterate(
    label: str = typer.Option(
        ..., "--label", "-l", help="Run label in Supabase"
    ),
    device: str = typer.Option("auto", "--device", help="Device: auto, mps, cuda, cpu"),
    base_model: str = typer.Option(
        "openai/whisper-small", "--base-model", help="HuggingFace model to fine-tune"
    ),
    epochs: int = typer.Option(10, "--epochs", help="Training epochs"),
    batch_size: int = typer.Option(4, "--batch-size", help="Per-device batch size"),
    lr: float = typer.Option(1e-5, "--lr", help="Learning rate"),
    eval_split: float = typer.Option(0.1, "--eval-split", help="Fraction for evaluation"),
    push_to_hub: str | None = typer.Option(
        None, "--push-to-hub", help="HuggingFace repo ID to push model to"
    ),
    output_model: Path = typer.Option(
        "models/whisper-mg-v1", "--output-model", "-o", help="Where to save the model"
    ),
) -> None:
    """Export corrected data + train Whisper + re-draft pending clips — all in one shot."""
    from pipeline.iterate import iterate as run_iterate

    resolved_device = _detect_device(device)
    run_iterate(
        label=label,
        device=resolved_device,
        output_model_dir=output_model,
        base_model=base_model,
        epochs=epochs,
        batch_size=batch_size,
        lr=lr,
        eval_split=eval_split,
        push_to_hub=push_to_hub,
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
