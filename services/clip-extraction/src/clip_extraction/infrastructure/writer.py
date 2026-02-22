"""Write clips to WAV files and metadata to CSV."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import soundfile as sf

from ny_feoko_shared.models import ClipResult


class ClipWriter:
    def __init__(self, output_dir: Path, sample_rate: int = 16000):
        self.clips_dir = output_dir / "clips"
        self.clips_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_path = output_dir / "metadata.csv"
        self.sample_rate = sample_rate
        self._rows: list[dict] = []
        self._counter = 0

    def write_clip(self, result: ClipResult) -> Path:
        self._counter += 1
        clip_name = f"clip_{self._counter:05d}.wav"
        clip_path = self.clips_dir / clip_name

        sf.write(str(clip_path), result.candidate.audio, self.sample_rate, subtype="PCM_16")
        result.clip_path = clip_path

        self._rows.append({
            "file_name": f"clips/{clip_name}",
            "source_file": str(result.candidate.source_file),
            "start_sec": round(result.candidate.start_sec, 2),
            "end_sec": round(result.candidate.end_sec, 2),
            "duration_sec": round(result.candidate.duration, 2),
            "speech_score": round(result.speech_score, 3),
            "music_score": round(result.music_score, 3),
            "transcription": result.whisper_text or "",
            "whisper_avg_logprob": round(result.whisper_avg_logprob, 3) if result.whisper_avg_logprob is not None else "",
            "whisper_no_speech_prob": round(result.whisper_no_speech_prob, 3) if result.whisper_no_speech_prob is not None else "",
            "whisper_rejected": result.whisper_rejected,
        })
        return clip_path

    def flush_metadata(self) -> None:
        if not self._rows:
            return
        df = pd.DataFrame(self._rows)
        df.to_csv(self.metadata_path, index=False)
