"""Clip extraction pipeline: chunk -> VAD -> group -> classify -> transcribe -> write."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import soundfile as sf

from application.services.audio_processing import stream_chunks
from domain.entities.clip import AudioSegment, ClipCandidate, ClipResult
from domain.ports.classifier import ClassifierPort
from domain.ports.transcriber import TranscriberPort
from domain.ports.vad import VADPort

MUSIC_SCORE_WEIGHT = 0.8
NO_SPEECH_THRESHOLD = 0.6


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

    candidates: list[list[AudioSegment]] = []
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

    results: list[ClipCandidate] = []
    for grp in candidates:
        duration = grp[-1].end_sec - grp[0].start_sec
        if duration < min_duration:
            continue

        start_sample = int((grp[0].start_sec - audio_start_sec) * sample_rate)
        end_sample = int((grp[-1].end_sec - audio_start_sec) * sample_rate)
        end_sample = min(end_sample, len(audio))
        clip_audio = audio[start_sample:end_sample]

        results.append(ClipCandidate(
            segments=grp,
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
    run_label: str = "",
) -> Path | None:
    """Run the full clip extraction pipeline. Returns the output directory path."""
    source = Path(input_file)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    label = run_label or source.stem
    run_dir_name = f"{timestamp}_{label}"
    out = Path(output_dir) / run_dir_name
    clips_dir = out / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    counter = 0

    for chunk_start, audio in stream_chunks(
        input_file, chunk_duration, sample_rate=sample_rate
    ):
        segments = [
            AudioSegment(
                start_sec=seg.start_sec + chunk_start,
                end_sec=seg.end_sec + chunk_start,
            )
            for seg in vad.detect(audio, sample_rate)
        ]

        candidates = group_segments(
            segments, audio, sample_rate, source, audio_start_sec=chunk_start
        )

        for candidate in candidates:
            speech_score, music_score = classifier.classify(
                candidate.audio, sample_rate
            )
            accepted = (
                speech_score > speech_threshold
                and speech_score > music_score * MUSIC_SCORE_WEIGHT
            )

            if not accepted:
                continue

            result_dict = transcriber.transcribe(candidate.audio, sample_rate)
            whisper_rejected = result_dict["no_speech_prob"] > NO_SPEECH_THRESHOLD

            counter += 1
            clip_name = f"clip_{counter:05d}.wav"
            clip_path = clips_dir / clip_name
            sf.write(str(clip_path), candidate.audio, sample_rate, subtype="PCM_16")

            clip_result = ClipResult(
                candidate=candidate,
                speech_score=speech_score,
                music_score=music_score,
                accepted=True,
                whisper_text=result_dict["text"],
                whisper_avg_logprob=result_dict["avg_logprob"],
                whisper_no_speech_prob=result_dict["no_speech_prob"],
                whisper_rejected=whisper_rejected,
                clip_path=clip_path,
            )

            rows.append({
                "file_name": f"clips/{clip_name}",
                "source_file": str(clip_result.candidate.source_file),
                "start_sec": round(clip_result.candidate.start_sec, 2),
                "end_sec": round(clip_result.candidate.end_sec, 2),
                "duration_sec": round(clip_result.candidate.duration, 2),
                "speech_score": round(clip_result.speech_score, 3),
                "music_score": round(clip_result.music_score, 3),
                "transcription": clip_result.whisper_text or "",
            })

    if rows:
        df = pd.DataFrame(rows)
        df.to_csv(out / "metadata.csv", index=False)

    return out if rows else None
