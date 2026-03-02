"""Abstract port for audio file storage."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class AudioStorage(ABC):
    @abstractmethod
    def upload(self, run_id: str, file_name: str, file_path: Path) -> None:
        """Upload an audio file to remote storage."""
        ...

    @abstractmethod
    def download(self, run_id: str, file_name: str, dest_path: Path) -> None:
        """Download an audio file from remote storage to a local path."""
        ...

    @abstractmethod
    def list_files(self, run_id: str) -> list[str]:
        """List all file names stored for a run."""
        ...

    @abstractmethod
    def remove_prefix(self, prefix: str) -> None:
        """Remove all objects under a given prefix."""
        ...
