"""Tests for CLI commands."""

from __future__ import annotations

import logging

import pytest
import typer
from typer.testing import CliRunner

from ports.cli import app as cli_app
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


class TestCliRequestMapping:
    def test_ingest_request_normalizes_supported_values(self) -> None:
        request = cli_app._build_ingest_request(
            input_path="  https://example.com/audio  ",
            label="  run-1  ",
            whisper_model="small",
            whisper_hf="   ",
            vad_threshold=0.4,
            speech_threshold=0.2,
        )

        assert request.url == "https://example.com/audio"
        assert request.label == "run-1"
        assert request.whisper_hf is None

    def test_ingest_request_accepts_local_file_path(self) -> None:
        request = cli_app._build_ingest_request(
            input_path=" ./data/input/example.wav ",
            label="",
            whisper_model="small",
            whisper_hf="",
            vad_threshold=0.35,
            speech_threshold=0.35,
        )

        assert request.url == "./data/input/example.wav"

    @pytest.mark.parametrize("value", ["", "   ", "ftp://example.com/audio"])
    def test_ingest_request_rejects_invalid_input_path_values(self, value: str) -> None:
        with pytest.raises(typer.BadParameter):
            cli_app._build_ingest_request(
                input_path=value,
                label="run-1",
                whisper_model="small",
                whisper_hf="",
                vad_threshold=0.35,
                speech_threshold=0.35,
            )

    def test_train_request_normalizes_whitespace(self) -> None:
        request = cli_app._build_train_request(
            data_dir="  data/training  ",
            output_dir="  models/output  ",
            device="  cpu  ",
            base_model="  openai/whisper-small  ",
            epochs=2,
            batch_size=1,
            lr=1e-5,
            push_to_hub="   ",
        )

        assert request.data_dir == "data/training"
        assert request.output_dir == "models/output"
        assert request.device == "cpu"
        assert request.base_model == "openai/whisper-small"
        assert request.push_to_hub is None

    def test_export_request_normalizes_run_ids(self) -> None:
        request = cli_app._build_export_request(
            run_ids=["  run-a", "run-b  "],
            output="  data/output  ",
            eval_split=0.2,
        )

        assert request.run_ids == ["run-a", "run-b"]
        assert request.output == "data/output"

    def test_redraft_request_normalizes_values(self) -> None:
        request = cli_app._build_redraft_request(
            run_ids=["  run-a  "],
            model="  models/whisper  ",
            device="  auto  ",
            language="  mg  ",
        )

        assert request.run_ids == ["run-a"]
        assert request.model_path == "models/whisper"
        assert request.device == "auto"
        assert request.language == "mg"
