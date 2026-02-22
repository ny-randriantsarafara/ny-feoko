"""Whisper adapter for Malagasy draft transcription."""

from __future__ import annotations

import numpy as np
import whisper

from clip_extraction.domain.ports import TranscriberPort


class WhisperTranscriber(TranscriberPort):
    def __init__(self, model_name: str = "small", device: str = "mps"):
        self.model = whisper.load_model(model_name, device=device)

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> dict:
        result = self.model.transcribe(
            audio,
            language="mg",
            task="transcribe",
            fp16=False,
            temperature=0.0,
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
            logprob_threshold=-1.0,
        )
        segments = result.get("segments", [])
        avg_logprob = (
            sum(s["avg_logprob"] for s in segments) / len(segments)
            if segments
            else -float("inf")
        )
        no_speech_prob = (
            max(s["no_speech_prob"] for s in segments)
            if segments
            else 1.0
        )
        return {
            "text": result["text"].strip(),
            "language": result.get("language", "mg"),
            "avg_logprob": avg_logprob,
            "no_speech_prob": no_speech_prob,
        }
