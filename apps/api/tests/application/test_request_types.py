"""Tests for application request schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from application.types import ExportRequest, IngestRequest, RedraftRequest, TrainRequest


class TestIngestRequest:
    def test_defaults_are_applied(self) -> None:
        request = IngestRequest(url="https://example.com/audio", label="run-1")

        assert request.whisper_model == "small"
        assert request.whisper_hf is None
        assert request.vad_threshold == pytest.approx(0.35)
        assert request.speech_threshold == pytest.approx(0.35)

    def test_empty_whisper_hf_normalizes_to_none(self) -> None:
        request = IngestRequest(
            url="https://example.com/audio", label="run-1", whisper_hf="   "
        )

        assert request.whisper_hf is None

    def test_blank_label_normalizes_to_empty_string(self) -> None:
        request = IngestRequest(url="https://example.com/audio", label="   ")

        assert request.label == ""

    @pytest.mark.parametrize("field", ["vad_threshold", "speech_threshold"])
    @pytest.mark.parametrize("value", [-0.01, 1.01])
    def test_rejects_thresholds_outside_unit_interval(self, field: str, value: float) -> None:
        payload = {
            "url": "https://example.com/audio",
            "label": "run-1",
            field: value,
        }

        with pytest.raises(ValidationError):
            IngestRequest(**payload)

    @pytest.mark.parametrize("value", ["", "   ", "ftp://example.com/audio"])
    def test_rejects_invalid_url_values(self, value: str) -> None:
        with pytest.raises(ValidationError):
            IngestRequest(url=value, label="run-1")

    def test_accepts_local_file_path_url_value(self) -> None:
        request = IngestRequest(url=" ./data/input/example.wav ", label="run-1")

        assert request.url == "./data/input/example.wav"

    @pytest.mark.parametrize(
        "payload",
        [
            {"label": "run-1"},
        ],
    )
    def test_requires_url(self, payload: dict[str, str]) -> None:
        with pytest.raises(ValidationError):
            IngestRequest(**payload)


class TestTrainRequest:
    def test_defaults_are_applied(self) -> None:
        request = TrainRequest(data_dir="data/training")

        assert request.output_dir == "models/whisper-mg-v1"
        assert request.device == "auto"
        assert request.base_model == "openai/whisper-small"
        assert request.epochs == 10
        assert request.batch_size == 4
        assert request.lr == pytest.approx(1e-5)
        assert request.push_to_hub is None

    def test_push_to_hub_blank_normalizes_to_none(self) -> None:
        request = TrainRequest(data_dir="data/training", push_to_hub="   ")

        assert request.push_to_hub is None

    def test_push_to_hub_trims_whitespace(self) -> None:
        request = TrainRequest(data_dir="data/training", push_to_hub="  org/model  ")

        assert request.push_to_hub == "org/model"

    @pytest.mark.parametrize("field,value", [("epochs", 0), ("batch_size", 0), ("lr", 0.0)])
    def test_rejects_invalid_numeric_values(self, field: str, value: float) -> None:
        payload = {"data_dir": "data/training", field: value}

        with pytest.raises(ValidationError):
            TrainRequest(**payload)

    @pytest.mark.parametrize("value", ["", "   "])
    def test_rejects_blank_data_dir(self, value: str) -> None:
        with pytest.raises(ValidationError):
            TrainRequest(data_dir=value)


class TestExportRequest:
    def test_defaults_are_applied(self) -> None:
        request = ExportRequest(run_ids=["run-1"])

        assert request.output == "data/output"
        assert request.eval_split == pytest.approx(0.1)

    @pytest.mark.parametrize("value", [[], ["   "]])
    def test_rejects_empty_run_ids(self, value: list[str]) -> None:
        with pytest.raises(ValidationError):
            ExportRequest(run_ids=value)

    @pytest.mark.parametrize("value", [-0.01, 0.51])
    def test_rejects_eval_split_outside_range(self, value: float) -> None:
        with pytest.raises(ValidationError):
            ExportRequest(run_ids=["run-1"], eval_split=value)

    @pytest.mark.parametrize("value", ["", "   "])
    def test_rejects_blank_output(self, value: str) -> None:
        with pytest.raises(ValidationError):
            ExportRequest(run_ids=["run-1"], output=value)

    def test_normalizes_trimmed_run_ids(self) -> None:
        request = ExportRequest(run_ids=["  run-1", "run-2  "])

        assert request.run_ids == ["run-1", "run-2"]


class TestRedraftRequest:
    def test_defaults_are_applied(self) -> None:
        request = RedraftRequest(run_ids=["run-1"], model_path="models/run-1")

        assert request.device == "auto"
        assert request.language == "mg"

    @pytest.mark.parametrize("value", [[], ["   "]])
    def test_rejects_empty_run_ids(self, value: list[str]) -> None:
        with pytest.raises(ValidationError):
            RedraftRequest(run_ids=value, model_path="models/run-1")

    @pytest.mark.parametrize("value", ["", "   "])
    def test_rejects_blank_model_path(self, value: str) -> None:
        with pytest.raises(ValidationError):
            RedraftRequest(run_ids=["run-1"], model_path=value)

    def test_normalizes_model_path_and_language(self) -> None:
        request = RedraftRequest(
            run_ids=["run-1"],
            model_path="  models/run-1  ",
            language="  mg  ",
        )

        assert request.model_path == "models/run-1"
        assert request.language == "mg"
