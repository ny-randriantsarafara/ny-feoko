"""Abstract port for run persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod

from domain.entities.run import Run, RunType


class RunRepository(ABC):
    @abstractmethod
    def create(self, label: str, source: str | None, run_type: RunType) -> str:
        """Create a new run and return its id."""
        ...

    @abstractmethod
    def find_by_id(self, run_id: str) -> Run | None:
        """Return a run by id, or None if not found."""
        ...

    @abstractmethod
    def find_by_label(self, label: str) -> Run | None:
        """Return the most recent run with the given label, or None."""
        ...

    @abstractmethod
    def list_all(self) -> list[Run]:
        """Return all runs, most recent first."""
        ...

    @abstractmethod
    def delete(self, run_id: str) -> None:
        """Delete a run by id."""
        ...

    @abstractmethod
    def resolve_run_id(self, run_id: str | None, label: str | None) -> str:
        """Resolve run_id or label to a run UUID.

        Raises RunNotFoundError if neither provided or no match found.
        """
        ...

    @abstractmethod
    def resolve_label(self, run_id: str) -> str:
        """Resolve run_id to its label.

        Raises RunNotFoundError if no run found.
        """
        ...
