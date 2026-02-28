"""Segment grouping: merge adjacent VAD segments into clip candidates."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ny_feoko_shared.models import AudioSegment, ClipCandidate


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
