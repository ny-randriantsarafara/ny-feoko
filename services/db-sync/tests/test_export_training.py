"""Tests for the training data export (WAV copy, CSV format, train/test split)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest
import soundfile as sf

from db_sync.export import export_training

SAMPLE_RATE = 16_000


@pytest.fixture
def source_dir(tmp_path: Path) -> Path:
    """Create a source directory with clips/ containing WAV files."""
    src = tmp_path / "source"
    clips = src / "clips"
    clips.mkdir(parents=True)

    for i in range(10):
        audio = np.random.default_rng(i).standard_normal(SAMPLE_RATE * 5).astype(np.float32)
        sf.write(str(clips / f"clip_{i:03d}.wav"), audio, SAMPLE_RATE)

    return src


@pytest.fixture
def mock_client(source_dir: Path) -> MagicMock:
    """Mock Supabase client that returns 10 corrected clips."""
    client = MagicMock()

    corrected_rows = [
        {"file_name": f"clips/clip_{i:03d}.wav", "corrected_transcription": f"Transcript {i}"}
        for i in range(10)
    ]

    runs_chain = MagicMock()
    runs_chain.select.return_value = runs_chain
    runs_chain.eq.return_value = runs_chain
    runs_chain.order.return_value = runs_chain
    runs_chain.limit.return_value = runs_chain

    clips_chain = MagicMock()
    clips_chain.select.return_value = clips_chain
    clips_chain.eq.return_value = clips_chain

    def range_side_effect(start: int, end: int) -> MagicMock:
        mock = MagicMock()
        if start == 0:
            mock.execute.return_value = MagicMock(data=corrected_rows)
        else:
            mock.execute.return_value = MagicMock(data=[])
        return mock

    clips_chain.range.side_effect = range_side_effect

    def table_side_effect(name: str) -> MagicMock:
        if name == "runs":
            runs_chain.execute.return_value = MagicMock(
                data=[{"id": "run-uuid-123", "label": "test-run"}]
            )
            return runs_chain
        return clips_chain

    client.table.side_effect = table_side_effect
    return client


class TestExportTraining:
    def test_creates_train_and_test_dirs(
        self, mock_client: MagicMock, source_dir: Path, tmp_path: Path
    ) -> None:
        output = tmp_path / "training"
        result = export_training(
            mock_client,
            run_id="run-uuid-123",
            label=None,
            source_dir=source_dir,
            output=output,
            eval_split=0.2,
        )

        assert (result / "train").is_dir()
        assert (result / "test").is_dir()

    def test_copies_wav_files(
        self, mock_client: MagicMock, source_dir: Path, tmp_path: Path
    ) -> None:
        output = tmp_path / "training"
        result = export_training(
            mock_client,
            run_id="run-uuid-123",
            label=None,
            source_dir=source_dir,
            output=output,
            eval_split=0.2,
        )

        train_wavs = list((result / "train").glob("*.wav"))
        test_wavs = list((result / "test").glob("*.wav"))
        assert len(train_wavs) + len(test_wavs) == 10

    def test_split_ratio(
        self, mock_client: MagicMock, source_dir: Path, tmp_path: Path
    ) -> None:
        output = tmp_path / "training"
        result = export_training(
            mock_client,
            run_id="run-uuid-123",
            label=None,
            source_dir=source_dir,
            output=output,
            eval_split=0.2,
        )

        train_wavs = list((result / "train").glob("*.wav"))
        test_wavs = list((result / "test").glob("*.wav"))
        assert len(train_wavs) == 8
        assert len(test_wavs) == 2

    def test_metadata_csv_format(
        self, mock_client: MagicMock, source_dir: Path, tmp_path: Path
    ) -> None:
        output = tmp_path / "training"
        result = export_training(
            mock_client,
            run_id="run-uuid-123",
            label=None,
            source_dir=source_dir,
            output=output,
            eval_split=0.2,
        )

        train_csv = pd.read_csv(result / "train" / "metadata.csv")
        assert list(train_csv.columns) == ["file_name", "transcription"]
        assert len(train_csv) == 8

        for _, row in train_csv.iterrows():
            assert (result / "train" / row["file_name"]).exists()

    def test_deterministic_split(
        self, mock_client: MagicMock, source_dir: Path, tmp_path: Path
    ) -> None:
        output1 = tmp_path / "training1"
        output2 = tmp_path / "training2"

        result1 = export_training(
            mock_client, run_id="run-uuid-123", label=None,
            source_dir=source_dir, output=output1, eval_split=0.2,
        )
        result2 = export_training(
            mock_client, run_id="run-uuid-123", label=None,
            source_dir=source_dir, output=output2, eval_split=0.2,
        )

        csv1 = pd.read_csv(result1 / "train" / "metadata.csv")
        csv2 = pd.read_csv(result2 / "train" / "metadata.csv")
        assert list(csv1["file_name"]) == list(csv2["file_name"])

    def test_zero_eval_split(
        self, mock_client: MagicMock, source_dir: Path, tmp_path: Path
    ) -> None:
        output = tmp_path / "training"
        result = export_training(
            mock_client,
            run_id="run-uuid-123",
            label=None,
            source_dir=source_dir,
            output=output,
            eval_split=0.0,
        )

        train_wavs = list((result / "train").glob("*.wav"))
        assert len(train_wavs) == 10
        assert not (result / "test").exists()
