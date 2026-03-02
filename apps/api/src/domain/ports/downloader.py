"""Abstract port for downloading audio from external sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class AudioDownloader(ABC):
    @abstractmethod
    def download(self, url: str, dest_dir: Path, label: str) -> Path:
        """Download audio from a URL and return the local file path."""
        ...
