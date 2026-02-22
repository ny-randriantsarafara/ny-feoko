"""Abstract ports for the clip extraction pipeline."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from ny_feoko_shared.models import AudioSegment


class VADPort(ABC):
    @abstractmethod
    def detect(self, audio: np.ndarray, sample_rate: int) -> list[AudioSegment]:
        """Return detected speech segments (times relative to audio start)."""
        ...


class ClassifierPort(ABC):
    @abstractmethod
    def classify(self, audio: np.ndarray, sample_rate: int) -> tuple[float, float]:
        """Return (speech_score, music_score) in [0, 1]."""
        ...


class TranscriberPort(ABC):
    @abstractmethod
    def transcribe(self, audio: np.ndarray, sample_rate: int) -> dict:
        """Return dict with keys: text, language, avg_logprob, no_speech_prob."""
        ...
