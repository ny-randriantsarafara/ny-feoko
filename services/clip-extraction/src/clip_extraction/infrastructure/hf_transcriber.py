"""HuggingFace Whisper adapter for testing community fine-tuned models."""

from __future__ import annotations

import torch
import numpy as np
from transformers import WhisperForConditionalGeneration, WhisperProcessor

from clip_extraction.domain.ports import TranscriberPort


class HuggingFaceTranscriber(TranscriberPort):
    """Load any Whisper model from a HuggingFace repo ID.

    Usage:
        transcriber = HuggingFaceTranscriber("openai/whisper-small", device="mps")
        transcriber = HuggingFaceTranscriber("username/whisper-small-malagasy", device="mps")
    """

    def __init__(self, model_id: str, device: str = "mps", language: str = "mg"):
        self.processor = WhisperProcessor.from_pretrained(model_id)
        self.model = WhisperForConditionalGeneration.from_pretrained(model_id)
        self.model.to(device).eval()
        self.device = device
        self.language = language

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> dict:
        inputs = self.processor(
            audio,
            sampling_rate=sample_rate,
            return_tensors="pt",
        )
        input_features = inputs.input_features.to(self.device)

        forced_decoder_ids = self.processor.get_decoder_prompt_ids(
            language=self.language,
            task="transcribe",
        )

        with torch.no_grad():
            predicted_ids = self.model.generate(
                input_features,
                forced_decoder_ids=forced_decoder_ids,
                max_new_tokens=448,
            )

        text = self.processor.batch_decode(predicted_ids, skip_special_tokens=True)[0].strip()

        # HF generate doesn't return logprobs directly — mark as unavailable
        return {
            "text": text,
            "language": self.language,
            "avg_logprob": 0.0,
            "no_speech_prob": 0.0,
        }
