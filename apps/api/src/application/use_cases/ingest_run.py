"""Ingest pipeline: download -> extract clips -> sync to database."""

from __future__ import annotations

import logging
from pathlib import Path

from application.services.clip_extraction import run_pipeline
from application.use_cases.sync_run import SyncRun
from domain.ports.classifier import ClassifierPort
from domain.ports.downloader import AudioDownloader
from domain.ports.job_repository import JobRepository
from domain.ports.transcriber import TranscriberPort
from domain.ports.vad import VADPort

logger = logging.getLogger(__name__)


class IngestRun:
    def __init__(
        self,
        downloader: AudioDownloader,
        vad: VADPort,
        classifier: ClassifierPort,
        transcriber: TranscriberPort,
        sync: SyncRun,
        job_repo: JobRepository,
    ) -> None:
        self._downloader = downloader
        self._vad = vad
        self._classifier = classifier
        self._transcriber = transcriber
        self._sync = sync
        self._job_repo = job_repo

    def execute(
        self,
        job_id: str,
        url: str,
        label: str,
        *,
        input_dir: Path,
        output_dir: Path,
        speech_threshold: float = 0.35,
    ) -> None:
        """Run the full ingest pipeline with job progress tracking."""
        try:
            self._job_repo.update(
                job_id,
                status="running",
                progress=0,
                progress_message="Downloading from YouTube...",
            )
            audio_path = self._downloader.download(url, input_dir, label)

            self._job_repo.update(
                job_id, progress=30, progress_message="Extracting clips..."
            )
            run_dir = run_pipeline(
                str(audio_path),
                str(output_dir),
                self._vad,
                self._classifier,
                self._transcriber,
                speech_threshold=speech_threshold,
                run_label=label,
            )
            if run_dir is None:
                self._job_repo.fail(job_id, "Pipeline returned no output directory")
                return

            self._job_repo.update(
                job_id, progress=80, progress_message="Syncing to database..."
            )
            run_id = self._sync.execute(run_dir, label)

            self._job_repo.update(
                job_id,
                status="done",
                progress=100,
                result={"run_id": run_id, "run_dir": str(run_dir)},
            )
        except Exception as exc:
            logger.exception("Ingest job %s failed: %s", job_id, exc)
            self._job_repo.fail(job_id, str(exc))
