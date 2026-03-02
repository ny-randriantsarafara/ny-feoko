"""Clip entities — audio clip metadata and pipeline data objects."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import numpy as np


class ClipStatus(str, Enum):
    PENDING = "pending"
    CORRECTED = "corrected"
    DISCARDED = "discarded"


@dataclass(frozen=True)
class Clip:
    id: str
    run_id: str
    file_name: str
    source_file: str | None
    start_sec: float | None
    end_sec: float | None
    duration_sec: float | None
    speech_score: float | None
    music_score: float | None
    draft_transcription: str | None
    corrected_transcription: str | None
    status: ClipStatus
    priority: float = 0.0


@dataclass(frozen=True)
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
    audio: np.ndarray
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
