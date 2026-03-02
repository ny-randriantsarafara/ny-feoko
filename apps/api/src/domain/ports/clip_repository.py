"""Abstract port for clip persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from domain.entities.clip import ClipStatus


class ClipRepository(ABC):
    @abstractmethod
    def upsert_batch(self, run_id: str, rows: list[dict[str, Any]]) -> None:
        """Upsert a batch of clip metadata rows for a run."""
        ...

    @abstractmethod
    def find_by_run(
        self, run_id: str, *, status: ClipStatus | None = None, columns: str = "*"
    ) -> list[dict[str, Any]]:
        """Return clips for a run, optionally filtered by status."""
        ...

    @abstractmethod
    def update_transcription(self, clip_id: str, text: str) -> None:
        """Update the draft_transcription for a clip."""
        ...

    @abstractmethod
    def count_by_status(self, run_id: str) -> dict[ClipStatus, int]:
        """Return clip counts keyed by status for a run."""
        ...
