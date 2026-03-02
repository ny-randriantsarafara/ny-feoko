"""Abstract port for audio transcription."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np


class TranscriberPort(ABC):
    @abstractmethod
    def transcribe(self, audio: np.ndarray, sample_rate: int) -> dict[str, Any]:
        """Return dict with keys: text, language, avg_logprob, no_speech_prob."""
        ...
