"""Abstract port for Voice Activity Detection."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from domain.entities.clip import AudioSegment


class VADPort(ABC):
    @abstractmethod
    def detect(self, audio: np.ndarray, sample_rate: int) -> list[AudioSegment]:
        """Return detected speech segments (times relative to audio start)."""
        ...
