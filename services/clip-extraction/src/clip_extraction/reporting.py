"""Reporting utilities for clip extraction pipeline."""

from __future__ import annotations

import numpy as np
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def print_extraction_summary(
    *,
    total_clips: int,
    total_accepted: int,
    durations: list[float],
    speech_scores: list[float],
    avg_logprobs: list[float],
    whisper_rejected: int,
) -> None:
    """Print a quality summary of the extraction run."""
    if total_clips == 0:
        return

    acceptance_pct = (total_accepted / total_clips) * 100

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("metric", style="dim")
    table.add_column("value")

    table.add_row("Candidates evaluated", str(total_clips))
    table.add_row("Clips accepted", f"{total_accepted} ({acceptance_pct:.0f}%)")

    if durations:
        total_audio = sum(durations)
        table.add_row(
            "Clip duration",
            f"{min(durations):.1f}s / {np.mean(durations):.1f}s / "
            f"{max(durations):.1f}s  (min / mean / max)",
        )
        table.add_row("Total audio retained", f"{total_audio:.0f}s ({total_audio / 60:.1f} min)")

    if speech_scores:
        mean_speech = np.mean(speech_scores)
        high_conf = sum(1 for s in speech_scores if s > 0.7)
        borderline = sum(1 for s in speech_scores if 0.35 <= s <= 0.7)
        table.add_row("Avg speech score", f"{mean_speech:.2f}")
        table.add_row(
            "Speech confidence",
            f"{high_conf} high (>0.7), {borderline} borderline (0.35-0.7)",
        )

    if avg_logprobs:
        mean_logprob = np.mean(avg_logprobs)
        table.add_row(
            "Avg Whisper confidence",
            f"{mean_logprob:.2f}  (closer to 0 = more confident)",
        )

    table.add_row(
        "Whisper-rejected clips",
        f"{whisper_rejected} / {total_accepted}",
    )

    lines: list[str] = []

    if acceptance_pct < 30:
        lines.append(
            "[yellow]Low acceptance rate.[/] The audio may contain a lot of music or singing. "
            "Try lowering [bold]--speech-threshold[/] (e.g. 0.2) to keep more clips."
        )
    elif acceptance_pct > 90:
        lines.append(
            "[yellow]Very high acceptance rate.[/] Some music/singing clips "
            "may have slipped through. "
            "Try raising [bold]--speech-threshold[/] (e.g. 0.5) for cleaner data."
        )

    if whisper_rejected > total_accepted * 0.3 and total_accepted > 0:
        lines.append(
            f"[yellow]{whisper_rejected} clips were rejected by Whisper[/] (low confidence). "
            "This is normal for a low-resource language — the drafts will improve after training."
        )

    tips = "\n".join(lines) if lines else "[green]Extraction looks healthy.[/]"

    console.print()
    console.print(Panel(table, title="Extraction Summary", border_style="blue"))
    console.print(Panel(tips, title="Quality Notes", border_style="dim"))
