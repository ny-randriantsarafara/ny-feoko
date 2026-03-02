"""Tests for application services."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from application.services.audio_processing import format_duration
from application.services.clip_extraction import group_segments
from domain.entities.clip import AudioSegment


class TestGroupSegments:
    def test_empty_segments(self) -> None:
        result = group_segments([], np.zeros(16000), 16000, Path("test.wav"))
        assert result == []

    def test_single_long_segment(self) -> None:
        segments = [AudioSegment(start_sec=0.0, end_sec=10.0)]
        audio = np.zeros(16000 * 10, dtype=np.float32)
        result = group_segments(segments, audio, 16000, Path("test.wav"))
        assert len(result) == 1
        assert result[0].duration == pytest.approx(10.0)

    def test_short_segment_rejected(self) -> None:
        segments = [AudioSegment(start_sec=0.0, end_sec=2.0)]
        audio = np.zeros(16000 * 2, dtype=np.float32)
        result = group_segments(
            segments, audio, 16000, Path("test.wav"), min_duration=5.0
        )
        assert len(result) == 0

    def test_adjacent_segments_merged(self) -> None:
        segments = [
            AudioSegment(start_sec=0.0, end_sec=3.0),
            AudioSegment(start_sec=3.5, end_sec=7.0),
        ]
        audio = np.zeros(16000 * 7, dtype=np.float32)
        result = group_segments(
            segments, audio, 16000, Path("test.wav"), max_gap=1.5
        )
        assert len(result) == 1
        assert result[0].start_sec == 0.0
        assert result[0].end_sec == 7.0

    def test_distant_segments_split(self) -> None:
        segments = [
            AudioSegment(start_sec=0.0, end_sec=6.0),
            AudioSegment(start_sec=10.0, end_sec=16.0),
        ]
        audio = np.zeros(16000 * 16, dtype=np.float32)
        result = group_segments(
            segments, audio, 16000, Path("test.wav"), max_gap=1.5
        )
        assert len(result) == 2

    def test_audio_start_offset(self) -> None:
        segments = [AudioSegment(start_sec=100.0, end_sec=110.0)]
        audio = np.zeros(16000 * 10, dtype=np.float32)
        result = group_segments(
            segments, audio, 16000, Path("test.wav"), audio_start_sec=100.0
        )
        assert len(result) == 1
        assert len(result[0].audio) > 0


class TestFormatDuration:
    def test_seconds_only(self) -> None:
        assert format_duration(45) == "45s"

    def test_minutes_and_seconds(self) -> None:
        assert format_duration(125) == "2m 5s"

    def test_hours(self) -> None:
        assert format_duration(3665) == "1h 1m 5s"

    def test_exact_minute(self) -> None:
        assert format_duration(60) == "1m"

    def test_zero(self) -> None:
        assert format_duration(0) == "0s"


class TestDetectDevice:
    def test_explicit_device(self) -> None:
        from application.services.audio_processing import detect_device

        assert detect_device("cuda") == "cuda"
        assert detect_device("cpu") == "cpu"
        assert detect_device("mps") == "mps"

    def test_auto_fallback_to_cpu(self) -> None:
        from application.services.audio_processing import detect_device

        with (
            patch("torch.cuda.is_available", return_value=False),
            patch("torch.backends.mps.is_available", return_value=False),
        ):
            assert detect_device("auto") == "cpu"
