"""Tests for application use-cases."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pandas as pd
import pytest

from domain.entities.clip import ClipStatus
from domain.entities.run import Run, RunType
from domain.exceptions import RunNotFoundError, SyncError


def _make_run(
    run_id: str = "run-1", label: str = "test", source: str | None = "/path"
) -> Run:
    return Run(
        id=run_id,
        label=label,
        source=source,
        run_type=RunType.EXTRACTION,
        created_at=datetime.now(tz=UTC),
    )


class TestListRuns:
    def test_returns_all_runs(self) -> None:
        from application.use_cases.list_runs import ListRuns

        run_repo = MagicMock()
        runs = [_make_run("r1", "a"), _make_run("r2", "b")]
        run_repo.list_all.return_value = runs

        use_case = ListRuns(run_repo)
        result = use_case.execute()

        assert result == runs
        run_repo.list_all.assert_called_once()


class TestSyncRun:
    def test_sync_creates_run_and_uploads(self, tmp_path: Path) -> None:
        from application.use_cases.sync_run import SyncRun

        run_dir = tmp_path / "run"
        clips_dir = run_dir / "clips"
        clips_dir.mkdir(parents=True)
        (clips_dir / "clip_00001.wav").write_bytes(b"fake-wav")

        df = pd.DataFrame([{
            "file_name": "clips/clip_00001.wav",
            "source_file": "source.wav",
            "start_sec": 0.0,
            "end_sec": 5.0,
            "duration_sec": 5.0,
            "speech_score": 0.9,
            "music_score": 0.1,
            "transcription": "hello",
        }])
        df.to_csv(run_dir / "metadata.csv", index=False)

        run_repo = MagicMock()
        run_repo.create.return_value = "new-run-id"
        clip_repo = MagicMock()
        storage = MagicMock()

        use_case = SyncRun(run_repo, clip_repo, storage)
        result = use_case.execute(run_dir, "test-label")

        assert result == "new-run-id"
        run_repo.create.assert_called_once()
        storage.upload.assert_called_once()
        clip_repo.upsert_batch.assert_called_once()

    def test_sync_raises_on_missing_metadata(self, tmp_path: Path) -> None:
        from application.use_cases.sync_run import SyncRun

        run_repo = MagicMock()
        clip_repo = MagicMock()
        storage = MagicMock()

        use_case = SyncRun(run_repo, clip_repo, storage)
        with pytest.raises(SyncError, match="metadata.csv"):
            use_case.execute(tmp_path, "label")


class TestExportTraining:
    def test_export_creates_dataset(self, tmp_path: Path) -> None:
        from application.use_cases.export_training import ExportTraining

        source_dir = tmp_path / "source"
        clips_dir = source_dir / "clips"
        clips_dir.mkdir(parents=True)
        (clips_dir / "clip_00001.wav").write_bytes(b"fake-wav")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        run_repo = MagicMock()
        run_repo.resolve_label.return_value = "test"
        run_repo.find_by_id.return_value = _make_run(source=str(source_dir))

        clip_repo = MagicMock()
        clip_repo.find_by_run.return_value = [
            {
                "file_name": "clips/clip_00001.wav",
                "corrected_transcription": "hello world",
            }
        ]

        storage = MagicMock()
        use_case = ExportTraining(run_repo, clip_repo, storage)
        result = use_case.execute(["run-1"], output_dir, eval_split=0.0)

        assert result.exists()
        assert (result / "train").is_dir()
        assert (result / "train" / "metadata.csv").exists()

    def test_export_overwrites_existing(self, tmp_path: Path) -> None:
        from application.use_cases.export_training import ExportTraining

        source_dir = tmp_path / "source"
        clips_dir = source_dir / "clips"
        clips_dir.mkdir(parents=True)
        (clips_dir / "clip_00001.wav").write_bytes(b"fake-wav")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        run_repo = MagicMock()
        run_repo.resolve_label.return_value = "test"
        run_repo.find_by_id.return_value = _make_run(source=str(source_dir))

        clip_repo = MagicMock()
        clip_repo.find_by_run.return_value = [
            {
                "file_name": "clips/clip_00001.wav",
                "corrected_transcription": "hello",
            }
        ]

        storage = MagicMock()
        use_case = ExportTraining(run_repo, clip_repo, storage)

        result1 = use_case.execute(["run-1"], output_dir, eval_split=0.0)
        (result1 / "marker.txt").write_text("old")

        result2 = use_case.execute(["run-1"], output_dir, eval_split=0.0)
        assert not (result2 / "marker.txt").exists()

    def test_export_raises_on_no_clips(self) -> None:
        from application.use_cases.export_training import ExportTraining

        run_repo = MagicMock()
        run_repo.resolve_label.return_value = "test"
        run_repo.find_by_id.return_value = _make_run()

        clip_repo = MagicMock()
        clip_repo.find_by_run.return_value = []

        storage = MagicMock()
        use_case = ExportTraining(run_repo, clip_repo, storage)

        with pytest.raises(SyncError, match="No corrected clips"):
            use_case.execute(["run-1"], Path("out"))


class TestDeleteRun:
    def test_deletes_storage_and_run(self) -> None:
        from application.use_cases.manage_runs import DeleteRun

        run_repo = MagicMock()
        storage = MagicMock()

        use_case = DeleteRun(run_repo, storage)
        use_case.execute("run-1")

        storage.remove_prefix.assert_called_once_with("run-1")
        run_repo.delete.assert_called_once_with("run-1")


class TestIngestRun:
    def test_ingest_updates_job_on_failure(self) -> None:
        from application.use_cases.ingest_run import IngestRun

        downloader = MagicMock()
        downloader.download.side_effect = RuntimeError("download failed")

        vad = MagicMock()
        classifier = MagicMock()
        transcriber = MagicMock()
        sync = MagicMock()
        job_repo = MagicMock()

        use_case = IngestRun(downloader, vad, classifier, transcriber, sync, job_repo)
        use_case.execute(
            "job-1", "http://example.com", "label",
            input_dir=Path("data/input"), output_dir=Path("data/output"),
        )

        job_repo.fail.assert_called_once()
        assert "download failed" in job_repo.fail.call_args[0][1]
