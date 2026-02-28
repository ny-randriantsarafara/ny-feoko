"""Tests for yt-download CLI: _sanitize, _get_title, error handling."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from yt_download.cli import _get_title, _sanitize, download_audio


class TestSanitize:
    """Tests for _sanitize: safe filename from video title."""

    def test_replaces_special_characters(self) -> None:
        """Special chars (@#$% etc.) are removed."""
        assert _sanitize("Hello @ World!") == "hello-world"
        assert _sanitize("Video#123") == "video123"

    def test_collapses_multiple_spaces(self) -> None:
        """Multiple spaces are collapsed to a single hyphen."""
        assert _sanitize("multiple   spaces   here") == "multiple-spaces-here"

    def test_strips_leading_trailing_whitespace(self) -> None:
        """Leading/trailing whitespace is stripped before processing."""
        assert _sanitize("  trim me  ") == "trim-me"

    def test_lowercases_output(self) -> None:
        """Output is lowercased."""
        assert _sanitize("UPPERCASE Title") == "uppercase-title"

    def test_truncates_to_80_chars(self) -> None:
        """Result is truncated to 80 characters."""
        long_title = "a" * 100
        assert len(_sanitize(long_title)) == 80
        assert _sanitize(long_title) == "a" * 80

    def test_preserves_hyphens(self) -> None:
        """Hyphens are preserved (within word-char rules)."""
        assert _sanitize("word-word") == "word-word"

    def test_keeps_underscores(self) -> None:
        """Underscores are kept (part of \\w)."""
        assert _sanitize("hello_world") == "hello_world"


class TestGetTitle:
    """Tests for _get_title: fetches video title via yt-dlp."""

    def test_returns_title_from_ytdlp_stdout(self) -> None:
        """Returns trimmed title from yt-dlp stdout."""
        mock_result = MagicMock()
        mock_result.stdout = "  My Video Title  \n"
        mock_result.stderr = ""
        with patch("yt_download.cli.subprocess.run", return_value=mock_result):
            result = _get_title("https://youtube.com/watch?v=abc")
            assert result == "My Video Title"

    def test_raises_runtime_error_on_ytdlp_failure(self) -> None:
        """Raises RuntimeError with stderr when yt-dlp fails."""
        stderr = "ERROR: Unable to extract video data"
        with patch(
            "yt_download.cli.subprocess.run",
            side_effect=subprocess.CalledProcessError(1, ["yt-dlp"], stderr=stderr),
        ):
            with pytest.raises(RuntimeError, match=f"Failed to fetch title.*{stderr}"):
                _get_title("https://youtube.com/watch?v=invalid")

    def test_raises_runtime_error_preserves_cause(self) -> None:
        """RuntimeError chains from CalledProcessError (from exc)."""
        exc = subprocess.CalledProcessError(1, ["yt-dlp"], stderr="network error")
        with patch("yt_download.cli.subprocess.run", side_effect=exc):
            with pytest.raises(RuntimeError) as exc_info:
                _get_title("https://bad-url")
            assert exc_info.value.__cause__ is exc


class TestDownloadAudio:
    """Tests for download_audio: error handling on subprocess failure."""

    def test_raises_runtime_error_on_download_failure(self, tmp_path: Path) -> None:
        """Raises RuntimeError with stderr when yt-dlp download fails."""
        stderr = "ERROR: Video unavailable"
        with patch(
            "yt_download.cli.subprocess.run",
            side_effect=subprocess.CalledProcessError(1, ["yt-dlp"], stderr=stderr),
        ):
            with pytest.raises(RuntimeError, match=f"Failed to download audio.*{stderr}"):
                download_audio(
                    "https://youtube.com/watch?v=bad",
                    tmp_path,
                    label="test-label",
                )
