"""Silero VAD adapter tuned for church audio."""

from __future__ import annotations

import torch
import numpy as np

from ny_feoko_shared.models import AudioSegment
from clip_extraction.domain.ports import VADPort


class SileroVAD(VADPort):
    def __init__(self, threshold: float = 0.35, device: str = "cpu"):
        self.model, utils = torch.hub.load(
            "snakers4/silero-vad",
            "silero_vad",
            force_reload=False,
            trust_repo=True,
        )
        self.get_speech_timestamps = utils[0]
        self.threshold = threshold
        # Silero VAD works best on CPU
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
