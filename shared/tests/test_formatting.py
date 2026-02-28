"""Unit tests for format_duration."""

from __future__ import annotations

import pytest

from ny_feoko_shared.formatting import format_duration


class TestFormatDuration:
    def test_seconds_only(self) -> None:
        """Durations under 60 seconds are formatted as 'Ns'."""
        assert format_duration(45.0) == "45s"

    def test_minutes_and_seconds(self) -> None:
        """Durations under 1 hour show minutes and seconds."""
        assert format_duration(125.0) == "2m 5s"

    def test_hours_minutes_seconds(self) -> None:
        """Durations over 1 hour show hours, minutes, and seconds."""
        assert format_duration(3725.0) == "1h 2m 5s"

    def test_zero(self) -> None:
        """Zero seconds is formatted as '0s'."""
        assert format_duration(0) == "0s"
