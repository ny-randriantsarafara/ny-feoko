"""CLI for downloading YouTube audio as 16kHz mono WAV."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(help="Ambara YouTube downloader — download audio as training-ready WAV.")
console = Console()


def _sanitize(name: str) -> str:
    """Turn a video title into a safe filename."""
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s]+", "-", name.strip())
    return name.lower()[:80]


def _get_title(url: str) -> str:
    """Fetch video title via yt-dlp."""
    result = subprocess.run(
        ["yt-dlp", "--get-title", url],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


@app.command()
def download(
    url: str = typer.Argument(..., help="YouTube video URL"),
    output_dir: Path = typer.Option("data/input", "--output", "-o", help="Output directory"),
    label: str = typer.Option("", "--label", "-l", help="Filename label (defaults to video title)"),
) -> None:
    """Download YouTube audio and convert to 16kHz mono WAV."""
    output_dir.mkdir(parents=True, exist_ok=True)

    if not label:
        console.print("[bold]Fetching video title...[/]")
        title = _get_title(url)
        label = _sanitize(title)
        console.print(f"[dim]Title: {title}[/]")

    out_path = output_dir / f"{label}.wav"

    console.print(f"[bold]Downloading & converting to WAV...[/]")

    # yt-dlp downloads best audio, pipes to ffmpeg for 16kHz mono WAV
    subprocess.run(
        [
            "yt-dlp",
            "--extract-audio",
            "--audio-format", "wav",
            "--postprocessor-args", "ffmpeg:-ac 1 -ar 16000",
            "-o", str(out_path),
            url,
        ],
        check=True,
    )

    from ny_feoko_shared.audio_io import probe_duration
    duration = probe_duration(str(out_path))

    console.print(f"[bold green]Done![/] {out_path} ({duration:.0f}s)")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
