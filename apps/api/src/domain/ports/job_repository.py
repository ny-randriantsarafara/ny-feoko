"""Abstract port for job persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from domain.entities.job import Job


class JobRepository(ABC):
    @abstractmethod
    def create(self, job_type: str, params: dict[str, Any]) -> str:
        """Create a new job and return its id."""
        ...

    @abstractmethod
    def update(
        self,
        job_id: str,
        *,
        status: str | None = None,
        progress: int | None = None,
        progress_message: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> None:
        """Update job fields."""
        ...

    @abstractmethod
    def fail(self, job_id: str, error: str) -> None:
        """Mark a job as failed with an error message."""
        ...

    @abstractmethod
    def find_by_id(self, job_id: str) -> Job | None:
        """Return a job by id, or None if not found."""
        ...

    @abstractmethod
    def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return the most recent jobs."""
        ...
