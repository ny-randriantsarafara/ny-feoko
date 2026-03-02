"""Run management operations: delete, reset, cleanup."""

from __future__ import annotations

from domain.ports.clip_repository import ClipRepository
from domain.ports.run_repository import RunRepository
from domain.ports.storage import AudioStorage


class DeleteRun:
    def __init__(
        self,
        run_repo: RunRepository,
        storage: AudioStorage,
    ) -> None:
        self._run_repo = run_repo
        self._storage = storage

    def execute(self, run_id: str) -> None:
        self._storage.remove_prefix(run_id)
        self._run_repo.delete(run_id)


class Cleanup:
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
        empty_run_ids: list[str],
        orphan_prefixes: list[str],
    ) -> None:
        for run_id in empty_run_ids:
            self._storage.remove_prefix(run_id)
            self._run_repo.delete(run_id)

        for prefix in orphan_prefixes:
            self._storage.remove_prefix(prefix)
