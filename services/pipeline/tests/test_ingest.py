"""Tests for the ingest pipeline orchestration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pipeline.ingest import _is_url, _resolve_input, ingest


class TestIsUrl:
    def test_https(self) -> None:
        assert _is_url("https://youtube.com/watch?v=abc") is True

    def test_http(self) -> None:
        assert _is_url("http://example.com/video.mp4") is True

    def test_local_path(self) -> None:
        assert _is_url("data/input/test.wav") is False

    def test_absolute_path(self) -> None:
        assert _is_url("/home/user/test.wav") is False


class TestResolveInput:
    def test_local_file_exists(self, tmp_path: Path) -> None:
        wav = tmp_path / "test.wav"
        wav.write_bytes(b"fake")
        result = _resolve_input(str(wav), "", tmp_path)
        assert result == wav

    def test_local_file_missing(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit, match="not found"):
            _resolve_input(str(tmp_path / "missing.wav"), "", tmp_path)

    @patch("yt_download.cli.download_audio")
    def test_url_calls_download(self, mock_download: MagicMock, tmp_path: Path) -> None:
        expected = tmp_path / "out.wav"
        mock_download.return_value = expected
        result = _resolve_input("https://youtube.com/watch?v=abc", "label", tmp_path)
        assert result == expected
        mock_download.assert_called_once_with("https://youtube.com/watch?v=abc", tmp_path, "label")


class TestIngest:
    @patch("pipeline.ingest._sync")
    @patch("pipeline.ingest._extract")
    @patch("pipeline.ingest._resolve_input")
    def test_chains_resolve_extract_sync(
        self,
        mock_resolve: MagicMock,
        mock_extract: MagicMock,
        mock_sync: MagicMock,
        tmp_path: Path,
    ) -> None:
        wav_path = tmp_path / "input.wav"
        run_dir = tmp_path / "output" / "20260227_120000_test"

        mock_resolve.return_value = wav_path
        mock_extract.return_value = run_dir

        result = ingest("https://youtube.com/watch?v=abc", label="test", device="cpu")

        mock_resolve.assert_called_once()
        mock_extract.assert_called_once()
        mock_sync.assert_called_once_with(run_dir, "test")
        assert result == run_dir

    @patch("pipeline.ingest._sync")
    @patch("pipeline.ingest._extract")
    @patch("pipeline.ingest._resolve_input")
    def test_uses_run_dir_name_when_no_label(
        self,
        mock_resolve: MagicMock,
        mock_extract: MagicMock,
        mock_sync: MagicMock,
        tmp_path: Path,
    ) -> None:
        run_dir = tmp_path / "20260227_120000_auto-name"
        mock_resolve.return_value = tmp_path / "input.wav"
        mock_extract.return_value = run_dir

        ingest("data/input/test.wav", label="", device="cpu")

        mock_sync.assert_called_once_with(run_dir, "20260227_120000_auto-name")
