"""Re-transcribe pending clips using a fine-tuned Whisper model."""

from __future__ import annotations

import logging
from pathlib import Path

from application.services.training import get_transcriptions
from domain.entities.clip import ClipStatus
from domain.ports.clip_repository import ClipRepository
from domain.ports.job_repository import JobRepository
from domain.ports.run_repository import RunRepository
from domain.ports.storage import AudioStorage

logger = logging.getLogger(__name__)


class RedraftClips:
    def __init__(
        self,
        run_repo: RunRepository,
        clip_repo: ClipRepository,
        storage: AudioStorage,
        job_repo: JobRepository,
    ) -> None:
        self._run_repo = run_repo
        self._clip_repo = clip_repo
        self._storage = storage
        self._job_repo = job_repo

    def execute(
        self,
        job_id: str,
        run_ids: list[str],
        model_path: str,
        device: str,
        language: str = "mg",
    ) -> None:
        """Re-transcribe pending clips for multiple runs with job tracking."""
        try:
            self._job_repo.update(
                job_id,
                status="running",
                progress=0,
                progress_message="Resolving runs...",
            )

            total_updated = 0
            for i, run_id in enumerate(run_ids):
                label = self._run_repo.resolve_label(run_id)
                source_dir = self._ensure_source_dir(run_id, label)

                pending = self._clip_repo.find_by_run(
                    run_id,
                    status=ClipStatus.PENDING,
                    columns="id,file_name",
                )

                if not pending:
                    continue

                progress_pct = int(((i + 0.5) / len(run_ids)) * 100)
                self._job_repo.update(
                    job_id,
                    progress=progress_pct,
                    progress_message=f"Re-drafting {label} ({len(pending)} clips)...",
                )

                transcriptions = get_transcriptions(
                    model_path, source_dir, pending, device, language
                )

                for clip_id, text in transcriptions:
                    self._clip_repo.update_transcription(clip_id, text)
                    total_updated += 1

            self._job_repo.update(
                job_id,
                status="done",
                progress=100,
                result={"clips_updated": total_updated},
            )
        except Exception as exc:
            logger.exception("Redraft job %s failed: %s", job_id, exc)
            self._job_repo.fail(job_id, str(exc))

    def _ensure_source_dir(self, run_id: str, label: str) -> Path:
        run = self._run_repo.find_by_id(run_id)
        if run and run.source:
            stored_path = Path(run.source)
            if stored_path.exists() and (stored_path / "clips").is_dir():
                return stored_path

        dest_dir = Path("data/output") / label
        clips = self._clip_repo.find_by_run(run_id, columns="file_name")
        for row in clips:
            file_name = str(row["file_name"])
            if file_name.endswith(".wav"):
                local_path = dest_dir / file_name
                if not local_path.exists():
                    self._storage.download(run_id, file_name, local_path)
        return dest_dir
