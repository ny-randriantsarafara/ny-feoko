"""Pipeline orchestrator: chunk → VAD → group → classify → transcribe → write."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from clip_extraction.domain.ports import ClassifierPort, TranscriberPort, VADPort
from clip_extraction.infrastructure.writer import ClipWriter
from ny_feoko_shared.audio_io import probe_duration, stream_chunks
from ny_feoko_shared.models import AudioSegment, ClipCandidate, ClipResult

console = Console()


def group_segments(
    segments: list[AudioSegment],
    audio: np.ndarray,
    sample_rate: int,
    source_file: Path,
    audio_start_sec: float = 0.0,
    min_duration: float = 5.0,
    max_duration: float = 30.0,
    max_gap: float = 1.5,
) -> list[ClipCandidate]:
    """Merge adjacent VAD segments into 5-30s clip candidates."""
    if not segments:
        return []

    candidates = []
    group: list[AudioSegment] = [segments[0]]

    for seg in segments[1:]:
        gap = seg.start_sec - group[-1].end_sec
        group_duration = seg.end_sec - group[0].start_sec

        if gap <= max_gap and group_duration <= max_duration:
            group.append(seg)
        else:
            candidates.append(group)
            group = [seg]

    candidates.append(group)

    results = []
    for group in candidates:
        duration = group[-1].end_sec - group[0].start_sec
        if duration < min_duration:
            continue

        start_sample = int((group[0].start_sec - audio_start_sec) * sample_rate)
        end_sample = int((group[-1].end_sec - audio_start_sec) * sample_rate)
        end_sample = min(end_sample, len(audio))
        clip_audio = audio[start_sample:end_sample]

        results.append(ClipCandidate(
            segments=group,
            audio=clip_audio,
            source_file=source_file,
        ))

    return results


def run_pipeline(
    input_file: str,
    output_dir: str,
    vad: VADPort,
    classifier: ClassifierPort,
    transcriber: TranscriberPort,
    *,
    chunk_duration: int = 300,
    speech_threshold: float = 0.35,
    sample_rate: int = 16000,
    verbose: bool = False,
    run_label: str = "",
) -> Path:
    """Run the full clip extraction pipeline. Returns the output directory path."""
    from datetime import datetime

    source = Path(input_file)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    label = run_label or source.stem
    run_dir = f"{timestamp}_{label}"
    out = Path(output_dir) / run_dir
    writer = ClipWriter(out, sample_rate)

    total_sec = probe_duration(input_file)
    total_clips = 0
    total_accepted = 0

    clip_durations: list[float] = []
    clip_speech_scores: list[float] = []
    clip_avg_logprobs: list[float] = []
    whisper_rejected_count = 0

    console.print(f"[bold]Processing:[/] {source.name} ({total_sec:.0f}s)")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        chunk_task = progress.add_task("Chunking audio...", total=total_sec)

        for chunk_start, audio in stream_chunks(
            input_file, chunk_duration, sample_rate=sample_rate
        ):
            chunk_end = chunk_start + len(audio) / sample_rate
            progress.update(
                chunk_task,
                completed=min(chunk_end, total_sec),
                description=f"Processing {chunk_start:.0f}s-{chunk_end:.0f}s",
            )

            segments = vad.detect(audio, sample_rate)
            if verbose:
                console.print(f"  VAD: {len(segments)} segments in chunk")

            for seg in segments:
                seg.start_sec += chunk_start
                seg.end_sec += chunk_start

            candidates = group_segments(
                segments, audio, sample_rate, source, audio_start_sec=chunk_start
            )
            if verbose:
                console.print(f"  Grouped: {len(candidates)} clip candidates")

            for candidate in candidates:
                total_clips += 1

                speech_score, music_score = classifier.classify(
                    candidate.audio, sample_rate
                )
                accepted = (
                    speech_score > speech_threshold
                    and speech_score > music_score * 0.8
                )

                if verbose:
                    status = "[green]ACCEPT[/]" if accepted else "[red]REJECT[/]"
                    console.print(
                        f"  Clip {total_clips}: {candidate.duration:.1f}s "
                        f"speech={speech_score:.2f} music={music_score:.2f} "
                        f"{status}"
                    )

                if not accepted:
                    continue

                total_accepted += 1

                result_dict = transcriber.transcribe(candidate.audio, sample_rate)
                whisper_rejected = result_dict["no_speech_prob"] > 0.6

                clip_durations.append(candidate.duration)
                clip_speech_scores.append(speech_score)
                if result_dict["avg_logprob"] is not None:
                    clip_avg_logprobs.append(result_dict["avg_logprob"])
                if whisper_rejected:
                    whisper_rejected_count += 1

                clip_result = ClipResult(
                    candidate=candidate,
                    speech_score=speech_score,
                    music_score=music_score,
                    accepted=True,
                    whisper_text=result_dict["text"],
                    whisper_avg_logprob=result_dict["avg_logprob"],
                    whisper_no_speech_prob=result_dict["no_speech_prob"],
                    whisper_rejected=whisper_rejected,
                )

                writer.write_clip(clip_result)

    writer.flush_metadata()

    console.print(f"\n[bold green]Done![/] {total_accepted}/{total_clips} clips accepted")
    console.print(f"Output: {out}")

    _print_extraction_summary(
        total_clips=total_clips,
        total_accepted=total_accepted,
        durations=clip_durations,
        speech_scores=clip_speech_scores,
        avg_logprobs=clip_avg_logprobs,
        whisper_rejected=whisper_rejected_count,
    )

    return out


def _print_extraction_summary(
    *,
    total_clips: int,
    total_accepted: int,
    durations: list[float],
    speech_scores: list[float],
    avg_logprobs: list[float],
    whisper_rejected: int,
) -> None:
    """Print a quality summary of the extraction run."""
    from rich.panel import Panel
    from rich.table import Table

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


def run_vad_only(
    input_file: str,
    output_file: str,
    vad: VADPort,
    *,
    chunk_duration: int = 300,
    sample_rate: int = 16000,
) -> list[dict]:
    """Run VAD only and return/save segment list as JSON."""
    import json

    all_segments: list[dict] = []
    total_sec = probe_duration(input_file)

    console.print(f"[bold]VAD scan:[/] {input_file} ({total_sec:.0f}s)")

    for chunk_start, audio in stream_chunks(input_file, chunk_duration, sample_rate=sample_rate):
        segments = vad.detect(audio, sample_rate)
        for seg in segments:
            all_segments.append({
                "start_sec": round(seg.start_sec + chunk_start, 3),
                "end_sec": round(seg.end_sec + chunk_start, 3),
                "duration_sec": round(seg.duration, 3),
            })

    Path(output_file).write_text(json.dumps(all_segments, indent=2))
    console.print(f"[bold green]Found {len(all_segments)} segments → {output_file}")
    return all_segments
