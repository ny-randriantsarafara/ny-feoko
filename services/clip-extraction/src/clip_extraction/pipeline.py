"""Pipeline orchestrator: chunk → VAD → group → classify → transcribe → write."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from ny_feoko_shared.audio_io import probe_duration, stream_chunks
from ny_feoko_shared.models import AudioSegment, ClipCandidate, ClipResult
from clip_extraction.domain.ports import VADPort, ClassifierPort, TranscriberPort
from clip_extraction.infrastructure.writer import ClipWriter

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
) -> None:
    """Run the full clip extraction pipeline."""
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

    console.print(f"[bold]Processing:[/] {source.name} ({total_sec:.0f}s)")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        chunk_task = progress.add_task("Chunking audio...", total=total_sec)

        for chunk_start, audio in stream_chunks(input_file, chunk_duration, sample_rate=sample_rate):
            chunk_end = chunk_start + len(audio) / sample_rate
            progress.update(chunk_task, completed=min(chunk_end, total_sec),
                            description=f"Processing {chunk_start:.0f}s-{chunk_end:.0f}s")

            # VAD
            segments = vad.detect(audio, sample_rate)
            if verbose:
                console.print(f"  VAD: {len(segments)} segments in chunk")

            # Make segment times absolute (relative to file start)
            for seg in segments:
                seg.start_sec += chunk_start
                seg.end_sec += chunk_start

            # Group into clip candidates
            candidates = group_segments(segments, audio, sample_rate, source, audio_start_sec=chunk_start)
            if verbose:
                console.print(f"  Grouped: {len(candidates)} clip candidates")

            for candidate in candidates:
                total_clips += 1

                # Classify
                speech_score, music_score = classifier.classify(candidate.audio, sample_rate)
                accepted = speech_score > speech_threshold and speech_score > music_score * 0.8

                if verbose:
                    status = "[green]ACCEPT[/]" if accepted else "[red]REJECT[/]"
                    console.print(
                        f"  Clip {total_clips}: {candidate.duration:.1f}s "
                        f"speech={speech_score:.2f} music={music_score:.2f} {status}"
                    )

                if not accepted:
                    continue

                total_accepted += 1

                # Transcribe
                result_dict = transcriber.transcribe(candidate.audio, sample_rate)
                whisper_rejected = result_dict["no_speech_prob"] > 0.6

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
