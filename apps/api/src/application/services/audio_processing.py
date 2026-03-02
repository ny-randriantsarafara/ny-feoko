"""FFmpeg-based audio I/O utilities for chunked processing."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator

import numpy as np


def probe_duration(file_path: str) -> float:
    """Get audio file duration in seconds using ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        file_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)
    return float(info["format"]["duration"])


def load_audio_segment(
    file_path: str,
    start_sec: float,
    duration_sec: float,
    sample_rate: int = 16000,
) -> np.ndarray:
    """Load a segment of audio as float32 mono at given sample rate via ffmpeg."""
    cmd = [
        "ffmpeg", "-nostdin",
        "-ss", str(start_sec),
        "-t", str(duration_sec),
        "-i", file_path,
        "-f", "f32le",
        "-ac", "1",
        "-ar", str(sample_rate),
        "-",
    ]
    result = subprocess.run(cmd, capture_output=True, check=True)
    return np.frombuffer(result.stdout, dtype=np.float32)


def stream_chunks(
    file_path: str,
    chunk_duration_sec: int = 300,
    overlap_sec: int = 2,
    sample_rate: int = 16000,
) -> Iterator[tuple[float, np.ndarray]]:
    """Yield (chunk_start_sec, audio_array) for each chunk of the file."""
    total_sec = probe_duration(file_path)
    pos = 0.0

    while pos < total_sec:
        read_start = max(0.0, pos - overlap_sec) if pos > 0 else 0.0
        read_duration = chunk_duration_sec + (overlap_sec if pos > 0 else 0)
        read_duration = min(read_duration, total_sec - read_start)

        audio = load_audio_segment(file_path, read_start, read_duration, sample_rate)
        yield read_start, audio

        pos += chunk_duration_sec


def format_duration(seconds: float) -> str:
    """Format a duration in seconds as human-readable (e.g. '1h 2m 5s')."""
    total = int(seconds)
    if total < 60:
        return f"{total}s"
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    parts: list[str] = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0:
        parts.append(f"{secs}s")
    return " ".join(parts)


def detect_device(requested: str) -> str:
    """Resolve device string; when 'auto', pick cuda > mps > cpu."""
    if requested != "auto":
        return requested
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"
