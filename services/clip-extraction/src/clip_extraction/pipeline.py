"""Pipeline orchestrator: chunk → VAD → group → classify → transcribe → write."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from clip_extraction.domain.ports import ClassifierPort, TranscriberPort, VADPort
from clip_extraction.domain.segment_grouping import group_segments
from clip_extraction.infrastructure.writer import ClipWriter
from clip_extraction.reporting import print_extraction_summary
from ny_feoko_shared.audio_io import probe_duration, stream_chunks
from ny_feoko_shared.models import ClipResult

MUSIC_SCORE_WEIGHT = 0.8
NO_SPEECH_THRESHOLD = 0.6

console = Console()


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
                    and speech_score > music_score * MUSIC_SCORE_WEIGHT
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
                whisper_rejected = result_dict["no_speech_prob"] > NO_SPEECH_THRESHOLD

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

    print_extraction_summary(
        total_clips=total_clips,
        total_accepted=total_accepted,
        durations=clip_durations,
        speech_scores=clip_speech_scores,
        avg_logprobs=clip_avg_logprobs,
        whisper_rejected=whisper_rejected_count,
    )

    return out


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
