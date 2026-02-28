"""Tests for group_segments."""

from pathlib import Path

import numpy as np
import pytest

from ny_feoko_shared.models import AudioSegment

from clip_extraction.domain.segment_grouping import group_segments


def _make_audio(duration_sec: float, sample_rate: int = 16000) -> np.ndarray:
    """Create a dummy audio array of given duration."""
    n = int(duration_sec * sample_rate)
    return np.zeros(n, dtype=np.float32)


def test_adjacent_segments_group_into_one_candidate() -> None:
    """Segments with small gaps (<= max_gap) group into one ClipCandidate."""
    # Two adjacent segments: 0-3s and 3.5-6.5s (gap 0.5s < 1.5 default)
    # Total duration 6.5s >= min_duration 5.0
    segments = [
        AudioSegment(start_sec=0.0, end_sec=3.0),
        AudioSegment(start_sec=3.5, end_sec=6.5),
    ]
    audio = _make_audio(10.0)
    source = Path("/tmp/test.wav")

    result = group_segments(
        segments,
        audio,
        sample_rate=16000,
        source_file=source,
        audio_start_sec=0.0,
        min_duration=5.0,
        max_duration=30.0,
        max_gap=1.5,
    )

    assert len(result) == 1
    assert len(result[0].segments) == 2
    assert result[0].start_sec == 0.0
    assert result[0].end_sec == 6.5
    assert result[0].duration == 6.5
    assert result[0].source_file == source


def test_large_gap_creates_separate_candidates() -> None:
    """Large gap between segments (> max_gap) creates separate candidates."""
    # Segments: 0-3s, gap 5s, then 8-11s (gap >> 1.5)
    segments = [
        AudioSegment(start_sec=0.0, end_sec=3.0),
        AudioSegment(start_sec=8.0, end_sec=11.0),
    ]
    audio = _make_audio(15.0)
    source = Path("/tmp/test.wav")

    result = group_segments(
        segments,
        audio,
        sample_rate=16000,
        source_file=source,
        audio_start_sec=0.0,
        min_duration=5.0,
        max_duration=30.0,
        max_gap=1.5,
    )

    # First group 0-3s is too short (< 5s min_duration), second 8-11s too short
    assert len(result) == 0


def test_large_gap_with_long_segments() -> None:
    """Large gap creates separate candidates when segments are long enough."""
    # Two groups of 6s each, separated by 3s gap (>> max_gap 1.5)
    segments = [
        AudioSegment(start_sec=0.0, end_sec=6.0),   # 6s
        AudioSegment(start_sec=9.0, end_sec=15.0), # 6s, gap=3s from previous
    ]
    audio = _make_audio(20.0)
    source = Path("/tmp/test.wav")

    result = group_segments(
        segments,
        audio,
        sample_rate=16000,
        source_file=source,
        audio_start_sec=0.0,
        min_duration=5.0,
        max_duration=30.0,
        max_gap=1.5,
    )

    assert len(result) == 2
    assert result[0].duration == 6.0
    assert result[1].duration == 6.0


def test_empty_segments_returns_empty_list() -> None:
    """Empty segments returns empty list."""
    result = group_segments(
        segments=[],
        audio=_make_audio(10.0),
        sample_rate=16000,
        source_file=Path("/tmp/test.wav"),
    )
    assert result == []


def test_segment_below_min_duration_filtered_out() -> None:
    """Single segment shorter than min_duration is not returned."""
    segments = [AudioSegment(start_sec=0.0, end_sec=2.0)]  # 2s < 5s
    audio = _make_audio(10.0)

    result = group_segments(
        segments,
        audio,
        sample_rate=16000,
        source_file=Path("/tmp/test.wav"),
        min_duration=5.0,
    )
    assert len(result) == 0
