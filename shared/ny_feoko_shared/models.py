from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class AudioSegment:
    """A VAD-detected speech region in absolute file time (seconds)."""

    start_sec: float
    end_sec: float

    @property
    def duration(self) -> float:
        return self.end_sec - self.start_sec


@dataclass
class ClipCandidate:
    """Grouped VAD segments forming a 5-30s clip ready for classification."""

    segments: list[AudioSegment]
    audio: np.ndarray  # float32, 16kHz mono
    source_file: Path

    @property
    def start_sec(self) -> float:
        return self.segments[0].start_sec

    @property
    def end_sec(self) -> float:
        return self.segments[-1].end_sec

    @property
    def duration(self) -> float:
        return self.end_sec - self.start_sec


@dataclass
class ClipResult:
    """A classified and optionally transcribed clip."""

    candidate: ClipCandidate
    speech_score: float
    music_score: float
    accepted: bool
    whisper_text: str | None = None
    whisper_avg_logprob: float | None = None
    whisper_no_speech_prob: float | None = None
    whisper_rejected: bool = False
    clip_path: Path | None = None
