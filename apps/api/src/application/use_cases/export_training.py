"""Export corrected clips as a HuggingFace audiofolder training dataset."""

from __future__ import annotations

import random
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from domain.entities.clip import ClipStatus
from domain.exceptions import SyncError
from domain.ports.clip_repository import ClipRepository
from domain.ports.run_repository import RunRepository
from domain.ports.storage import AudioStorage


class ExportTraining:
    def __init__(
        self,
        run_repo: RunRepository,
        clip_repo: ClipRepository,
        storage: AudioStorage,
    ) -> None:
        self._run_repo = run_repo
        self._clip_repo = clip_repo
        self._storage = storage

    def execute(
        self,
        run_ids: list[str],
        output_dir: Path,
        eval_split: float = 0.1,
        seed: int = 42,
    ) -> Path:
        """Export corrected clips from multiple runs as a single training dataset.

        Silently overwrites existing output. Returns dataset directory path.
        """
        all_rows: list[dict[str, object]] = []
        all_source_dirs: dict[str, Path] = {}

        for run_id in run_ids:
            label = self._run_repo.resolve_label(run_id)
            source_dir = self._ensure_source_dir(run_id, label)
            all_source_dirs[run_id] = source_dir

            rows = self._clip_repo.find_by_run(
                run_id,
                status=ClipStatus.CORRECTED,
                columns="file_name,corrected_transcription",
            )
            for row in rows:
                row["_source_dir"] = source_dir
            all_rows.extend(rows)

        if not all_rows:
            raise SyncError("No corrected clips found for the selected runs.")

        self._validate_source_files(all_rows)

        labels = [self._run_repo.resolve_label(rid) for rid in run_ids]
        combined_label = "_".join(labels)
        timestamp = datetime.now(tz=UTC).strftime("%Y%m%d")
        dataset_dir = output_dir / f"{timestamp}_{combined_label}"

        if dataset_dir.exists():
            shutil.rmtree(dataset_dir)

        rng = random.Random(seed)
        shuffled = list(all_rows)
        rng.shuffle(shuffled)

        split_idx = max(1, int(len(shuffled) * (1 - eval_split)))
        train_rows = shuffled[:split_idx]
        test_rows = shuffled[split_idx:]

        self._write_split(dataset_dir / "train", train_rows)
        if test_rows:
            self._write_split(dataset_dir / "test", test_rows)

        return dataset_dir

    def _ensure_source_dir(self, run_id: str, label: str) -> Path:
        run = self._run_repo.find_by_id(run_id)
        if run and run.source:
            stored_path = Path(run.source)
            if stored_path.exists() and (stored_path / "clips").is_dir():
                return stored_path

        dest_dir = Path("data/output") / label
        clips = self._clip_repo.find_by_run(
            run_id, columns="file_name"
        )
        file_names = [
            str(row["file_name"])
            for row in clips
            if str(row["file_name"]).endswith(".wav")
        ]

        for file_name in file_names:
            local_path = dest_dir / file_name
            if not local_path.exists():
                self._storage.download(run_id, file_name, local_path)

        return dest_dir

    @staticmethod
    def _validate_source_files(rows: list[dict[str, object]]) -> None:
        missing = [
            str(r["file_name"])
            for r in rows
            if not (Path(str(r["_source_dir"])) / str(r["file_name"])).exists()
        ]
        if missing:
            raise SyncError(
                f"{len(missing)} clip files not found. First missing: {missing[0]}"
            )

    @staticmethod
    def _write_split(
        split_dir: Path, rows: list[dict[str, object]]
    ) -> None:
        split_dir.mkdir(parents=True)
        for row in rows:
            src = Path(str(row["_source_dir"])) / str(row["file_name"])
            shutil.copy2(src, split_dir / src.name)

        df = pd.DataFrame([
            {
                "file_name": Path(str(row["file_name"])).name,
                "transcription": row["corrected_transcription"],
            }
            for row in rows
        ])
        df.to_csv(split_dir / "metadata.csv", index=False)
