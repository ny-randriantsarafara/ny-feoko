"""Abstract port for audio classification (speech vs music)."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class ClassifierPort(ABC):
    @abstractmethod
    def classify(self, audio: np.ndarray, sample_rate: int) -> tuple[float, float]:
        """Return (speech_score, music_score) in [0, 1]."""
        ...
