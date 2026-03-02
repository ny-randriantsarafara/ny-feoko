"""Silero VAD adapter."""

from __future__ import annotations

import numpy as np
import torch

from domain.entities.clip import AudioSegment
from domain.ports.vad import VADPort


class SileroVAD(VADPort):
    def __init__(self, threshold: float = 0.35) -> None:
        self.model, utils = torch.hub.load(
            "snakers4/silero-vad",
            "silero_vad",
            force_reload=False,
            trust_repo=True,
        )
        self.get_speech_timestamps = utils[0]
        self.threshold = threshold
        self.model.to("cpu")

    def detect(self, audio: np.ndarray, sample_rate: int) -> list[AudioSegment]:
        tensor = torch.from_numpy(audio).float()
        timestamps = self.get_speech_timestamps(
            tensor,
            self.model,
            threshold=self.threshold,
            sampling_rate=sample_rate,
            min_speech_duration_ms=500,
            min_silence_duration_ms=300,
        )
        return [
            AudioSegment(
                start_sec=t["start"] / sample_rate,
                end_sec=t["end"] / sample_rate,
            )
            for t in timestamps
        ]
