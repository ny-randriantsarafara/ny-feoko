"""Tests for CLI commands."""

from __future__ import annotations

import logging

import pytest
from typer.testing import CliRunner

from ports.cli.app import app

runner = CliRunner()


class TestCliVerboseFlag:
    @pytest.fixture(autouse=True)
    def reset_logging(self) -> None:
        """Reset logging state before each test."""
        root = logging.getLogger()
        root.setLevel(logging.WARNING)  # Reset to a known state
        root.handlers.clear()

    def test_verbose_flag_sets_debug_level(self) -> None:
        # Use subcommand --help to trigger callback (app-level --help skips callback)
        result = runner.invoke(app, ["-v", "ingest", "--help"])
        assert result.exit_code == 0
        assert logging.getLogger().level == logging.DEBUG

    def test_no_verbose_flag_sets_info_level(self) -> None:
        # Use subcommand --help to trigger callback (app-level --help skips callback)
        result = runner.invoke(app, ["ingest", "--help"])
        assert result.exit_code == 0
        assert logging.getLogger().level == logging.INFO
