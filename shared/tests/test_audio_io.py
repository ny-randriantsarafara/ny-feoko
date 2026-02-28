"""Unit tests for audio_io probe_duration and stream_chunks."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, call, patch

import numpy as np
import pytest

from ny_feoko_shared.audio_io import probe_duration, stream_chunks


class TestProbeDuration:
    def test_returns_duration_from_ffprobe(self) -> None:
        """probe_duration returns correct float parsed from ffprobe JSON stdout."""
        mock_result = MagicMock()
        mock_result.stdout = '{"format": {"duration": "12.345"}}'
        with patch("ny_feoko_shared.audio_io.subprocess.run", return_value=mock_result) as mock_run:
            result = probe_duration("/tmp/test.wav")
            assert result == pytest.approx(12.345)
            mock_run.assert_called_once()

    def test_returns_duration_when_numeric_in_json(self) -> None:
        """probe_duration handles numeric duration in JSON (no string)."""
        mock_result = MagicMock()
        mock_result.stdout = '{"format": {"duration": 42.5}}'
        with patch("ny_feoko_shared.audio_io.subprocess.run", return_value=mock_result):
            result = probe_duration("/tmp/test.wav")
            assert result == pytest.approx(42.5)

    def test_raises_on_ffprobe_failure(self) -> None:
        """probe_duration raises CalledProcessError when ffprobe fails."""
        with patch(
            "ny_feoko_shared.audio_io.subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "ffprobe"),
        ):
            with pytest.raises(subprocess.CalledProcessError):
                probe_duration("/tmp/test.wav")


class TestStreamChunks:
    def test_yields_chunks_of_correct_types(self) -> None:
        """stream_chunks yields correct number of chunks with (float, np.ndarray) pairs."""
        path = "/tmp/test.wav"
        with patch("ny_feoko_shared.audio_io.probe_duration", return_value=30.0):
            with patch("ny_feoko_shared.audio_io.load_audio_segment") as mock_load:
                mock_load.return_value = np.zeros(16000 * 10, dtype=np.float32)
                chunks = list(
                    stream_chunks(path, chunk_duration_sec=10, overlap_sec=2)
                )
                assert len(chunks) == 3
                for start_sec, audio in chunks:
                    assert isinstance(start_sec, float)
                    assert isinstance(audio, np.ndarray)
                    assert audio.dtype == np.float32
                # Verify chunk boundaries and overlap logic: 1st no overlap, 2nd and 3rd with 2s overlap
                mock_load.assert_has_calls([
                    call(path, 0.0, 10.0, 16000),   # no overlap on first chunk
                    call(path, 8.0, 12.0, 16000),   # 2s overlap
                    call(path, 18.0, 12.0, 16000),  # 2s overlap
                ])
