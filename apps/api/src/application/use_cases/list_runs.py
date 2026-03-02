"""List available runs for frontend selection."""

from __future__ import annotations

from domain.entities.run import Run
from domain.ports.run_repository import RunRepository


class ListRuns:
    def __init__(self, run_repo: RunRepository) -> None:
        self._run_repo = run_repo

    def execute(self) -> list[Run]:
        return self._run_repo.list_all()
