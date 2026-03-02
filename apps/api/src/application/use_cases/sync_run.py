"""Sync a local extraction run to the database and storage."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from domain.entities.run import RunType
from domain.exceptions import SyncError
from domain.ports.clip_repository import ClipRepository
from domain.ports.run_repository import RunRepository
from domain.ports.storage import AudioStorage

CSV_TO_DB_COLUMNS: dict[str, str] = {
    "file_name": "file_name",
    "source_file": "source_file",
    "start_sec": "start_sec",
    "end_sec": "end_sec",
    "duration_sec": "duration_sec",
    "speech_score": "speech_score",
    "music_score": "music_score",
    "transcription": "draft_transcription",
}


class SyncRun:
    def __init__(
        self,
        run_repo: RunRepository,
        clip_repo: ClipRepository,
        storage: AudioStorage,
    ) -> None:
        self._run_repo = run_repo
        self._clip_repo = clip_repo
        self._storage = storage

    def execute(self, run_dir: Path, label: str) -> str:
        """Create a run, upload clips, and upsert metadata. Returns run_id."""
        metadata_path = run_dir / "metadata.csv"
        clips_dir = run_dir / "clips"

        if not metadata_path.exists():
            raise SyncError(f"metadata.csv not found in {run_dir}")
        if not clips_dir.is_dir():
            raise SyncError(f"clips/ directory not found in {run_dir}")

        run_id = self._run_repo.create(label, str(run_dir), RunType.EXTRACTION)

        wav_files = sorted(clips_dir.glob("*.wav"))
        for wav in wav_files:
            self._storage.upload(run_id, f"clips/{wav.name}", wav)

        self._upsert_metadata(run_id, metadata_path)
        return run_id

    def _upsert_metadata(self, run_id: str, metadata_path: Path) -> None:
        df = pd.read_csv(metadata_path)
        rows: list[dict[str, object]] = []
        for _, csv_row in df.iterrows():
            db_row: dict[str, object] = {}
            for csv_col, db_col in CSV_TO_DB_COLUMNS.items():
                if csv_col in csv_row.index:
                    value = csv_row[csv_col]
                    db_row[db_col] = None if pd.isna(value) else value
            rows.append(db_row)
        self._clip_repo.upsert_batch(run_id, rows)
