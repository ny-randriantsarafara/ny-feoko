"""CLI entry point for clip extraction pipeline."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(help="Ambara clip extraction — extract clean speech clips from audio files.")
console = Console()


@app.command()
def run(
    input: Path = typer.Option(..., "--input", "-i", help="Input audio file (WAV, MP3, etc.)"),
    output: Path = typer.Option("data/output", "--output", "-o", help="Output directory"),
    whisper_model: str = typer.Option("small", "--whisper-model", help="Whisper model size (stock openai-whisper)"),
    whisper_hf: str = typer.Option("", "--whisper-hf", help="HuggingFace model ID (e.g. 'username/whisper-small-mg'). Overrides --whisper-model."),
    chunk_duration: int = typer.Option(300, "--chunk-duration", help="Chunk size in seconds"),
    vad_threshold: float = typer.Option(0.35, "--vad-threshold", help="VAD speech threshold"),
    speech_threshold: float = typer.Option(0.35, "--speech-threshold", help="Min speech score to accept"),
    device: str = typer.Option("mps", "--device", help="Torch device (mps, cuda, cpu)"),
    label: str = typer.Option("", "--label", "-l", help="Run label for output directory (e.g. 'whisper-small', 'hf-mg-v2')"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Run the full extraction pipeline: VAD → classify → transcribe → write clips."""
    from clip_extraction.infrastructure.vad import SileroVAD
    from clip_extraction.infrastructure.classifier import ASTClassifier
    from clip_extraction.infrastructure.transcriber import WhisperTranscriber
    from clip_extraction.pipeline import run_pipeline

    console.print("[bold]Loading models...[/]")
    vad = SileroVAD(threshold=vad_threshold)
    classifier = ASTClassifier(device=device)

    if whisper_hf:
        from clip_extraction.infrastructure.hf_transcriber import HuggingFaceTranscriber
        console.print(f"[bold]Using HuggingFace model:[/] {whisper_hf}")
        transcriber = HuggingFaceTranscriber(model_id=whisper_hf, device=device)
    else:
        transcriber = WhisperTranscriber(model_name=whisper_model, device=device)

    console.print("[bold green]Models loaded.[/]")

    run_pipeline(
        input_file=str(input),
        output_dir=str(output),
        vad=vad,
        classifier=classifier,
        transcriber=transcriber,
        chunk_duration=chunk_duration,
        speech_threshold=speech_threshold,
        verbose=verbose,
        run_label=label,
    )


@app.command("vad-only")
def vad_only(
    input: Path = typer.Option(..., "--input", "-i", help="Input audio file"),
    output: Path = typer.Option("data/vad_segments.json", "--output", "-o", help="Output JSON file"),
    chunk_duration: int = typer.Option(300, "--chunk-duration"),
    vad_threshold: float = typer.Option(0.35, "--vad-threshold"),
) -> None:
    """Run VAD only — outputs detected speech segments as JSON."""
    from clip_extraction.infrastructure.vad import SileroVAD
    from clip_extraction.pipeline import run_vad_only

    vad = SileroVAD(threshold=vad_threshold)
    run_vad_only(
        input_file=str(input),
        output_file=str(output),
        vad=vad,
        chunk_duration=chunk_duration,
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
