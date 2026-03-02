"""Tests for domain entities — construction, immutability, enum values."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from domain.entities.clip import (
    AudioSegment,
    Clip,
    ClipCandidate,
    ClipResult,
    ClipStatus,
)
from domain.entities.job import Job, JobStatus, JobType
from domain.entities.run import Run, RunType
from domain.exceptions import MissingConfigError, RunNotFoundError, SyncError


class TestRunEntity:
    def test_construction(self) -> None:
        now = datetime.now(tz=UTC)
        run = Run(
            id="abc-123",
            label="test-run",
            source="/some/path",
            run_type=RunType.EXTRACTION,
            created_at=now,
        )
        assert run.id == "abc-123"
        assert run.label == "test-run"
        assert run.source == "/some/path"
        assert run.run_type == RunType.EXTRACTION
        assert run.created_at == now

    def test_immutability(self) -> None:
        run = Run(
            id="x",
            label="y",
            source=None,
            run_type=RunType.READING,
            created_at=datetime.now(tz=UTC),
        )
        with pytest.raises(AttributeError):
            run.label = "changed"  # type: ignore[misc]

    def test_run_type_values(self) -> None:
        assert RunType.EXTRACTION.value == "extraction"
        assert RunType.READING.value == "reading"


class TestClipEntity:
    def test_construction(self) -> None:
        clip = Clip(
            id="clip-1",
            run_id="run-1",
            file_name="clips/clip_00001.wav",
            source_file="source.wav",
            start_sec=10.0,
            end_sec=20.0,
            duration_sec=10.0,
            speech_score=0.95,
            music_score=0.1,
            draft_transcription="hello",
            corrected_transcription="hello world",
            status=ClipStatus.CORRECTED,
            priority=1.0,
        )
        assert clip.status == ClipStatus.CORRECTED
        assert clip.priority == 1.0

    def test_immutability(self) -> None:
        clip = Clip(
            id="c",
            run_id="r",
            file_name="f.wav",
            source_file=None,
            start_sec=None,
            end_sec=None,
            duration_sec=None,
            speech_score=None,
            music_score=None,
            draft_transcription=None,
            corrected_transcription=None,
            status=ClipStatus.PENDING,
        )
        with pytest.raises(AttributeError):
            clip.status = ClipStatus.DISCARDED  # type: ignore[misc]

    def test_clip_status_values(self) -> None:
        assert ClipStatus.PENDING.value == "pending"
        assert ClipStatus.CORRECTED.value == "corrected"
        assert ClipStatus.DISCARDED.value == "discarded"


class TestAudioSegment:
    def test_duration(self) -> None:
        seg = AudioSegment(start_sec=1.0, end_sec=3.5)
        assert seg.duration == pytest.approx(2.5)

    def test_immutability(self) -> None:
        seg = AudioSegment(start_sec=0.0, end_sec=1.0)
        with pytest.raises(AttributeError):
            seg.start_sec = 5.0  # type: ignore[misc]


class TestClipCandidate:
    def test_properties(self) -> None:
        segments = [
            AudioSegment(start_sec=1.0, end_sec=3.0),
            AudioSegment(start_sec=4.0, end_sec=8.0),
        ]
        audio = np.zeros(16000 * 7, dtype=np.float32)
        candidate = ClipCandidate(
            segments=segments,
            audio=audio,
            source_file=Path("test.wav"),
        )
        assert candidate.start_sec == 1.0
        assert candidate.end_sec == 8.0
        assert candidate.duration == pytest.approx(7.0)


class TestClipResult:
    def test_defaults(self) -> None:
        segments = [AudioSegment(start_sec=0.0, end_sec=5.0)]
        candidate = ClipCandidate(
            segments=segments,
            audio=np.zeros(16000 * 5, dtype=np.float32),
            source_file=Path("test.wav"),
        )
        result = ClipResult(
            candidate=candidate,
            speech_score=0.9,
            music_score=0.1,
            accepted=True,
        )
        assert result.whisper_text is None
        assert result.whisper_rejected is False
        assert result.clip_path is None


class TestJobEntity:
    def test_construction(self) -> None:
        now = datetime.now(tz=UTC)
        job = Job(
            id="job-1",
            job_type=JobType.INGEST,
            status=JobStatus.QUEUED,
            progress=0,
            progress_message=None,
            params={"url": "https://example.com"},
            result=None,
            created_at=now,
        )
        assert job.job_type == JobType.INGEST
        assert job.status == JobStatus.QUEUED
        assert job.progress == 0

    def test_immutability(self) -> None:
        job = Job(
            id="j",
            job_type=JobType.EXPORT,
            status=JobStatus.DONE,
            progress=100,
            progress_message="done",
            params={},
            result={"path": "/out"},
            created_at=datetime.now(tz=UTC),
        )
        with pytest.raises(AttributeError):
            job.status = JobStatus.FAILED  # type: ignore[misc]

    def test_job_type_values(self) -> None:
        assert JobType.INGEST.value == "ingest"
        assert JobType.REDRAFT.value == "redraft"
        assert JobType.EXPORT.value == "export"

    def test_job_status_values(self) -> None:
        assert JobStatus.QUEUED.value == "queued"
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.DONE.value == "done"
        assert JobStatus.FAILED.value == "failed"


class TestDomainExceptions:
    def test_run_not_found_error(self) -> None:
        with pytest.raises(RunNotFoundError, match="not found"):
            raise RunNotFoundError("Run not found")

    def test_missing_config_error(self) -> None:
        with pytest.raises(MissingConfigError, match="missing"):
            raise MissingConfigError("Config missing")

    def test_sync_error(self) -> None:
        with pytest.raises(SyncError, match="failed"):
            raise SyncError("Sync failed")
