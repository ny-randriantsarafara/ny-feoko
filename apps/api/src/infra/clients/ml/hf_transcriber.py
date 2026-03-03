"""HuggingFace Whisper adapter for fine-tuned models."""

from __future__ import annotations

from typing import Any

import numpy as np
import torch
from transformers import WhisperForConditionalGeneration, WhisperProcessor

from domain.ports.transcriber import TranscriberPort

DECODER_MAX_TOKENS = 448
WHISPER_DECODER_START_TOKEN_COUNT = 2


class HuggingFaceTranscriber(TranscriberPort):
    def __init__(
        self, model_id: str, device: str = "mps", language: str = "mg"
    ) -> None:
        self.processor = WhisperProcessor.from_pretrained(model_id)
        self.model = WhisperForConditionalGeneration.from_pretrained(model_id)
        self.model.to(device).eval()
        self.device = device
        self.language = language

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> dict[str, Any]:
        inputs = self.processor(
            audio, sampling_rate=sample_rate, return_tensors="pt"
        )
        input_features = inputs.input_features.to(self.device)

        forced_decoder_ids = self.processor.get_decoder_prompt_ids(
            language=self.language, task="transcribe"
        )
        max_new_tokens = self._resolve_max_new_tokens(forced_decoder_ids)

        with torch.no_grad():
            predicted_ids = self.model.generate(
                input_features,
                forced_decoder_ids=forced_decoder_ids,
                max_new_tokens=max_new_tokens,
            )

        text = self.processor.batch_decode(
            predicted_ids, skip_special_tokens=True
        )[0].strip()

        return {
            "text": text,
            "language": self.language,
            "avg_logprob": 0.0,
            "no_speech_prob": 0.0,
        }

    def _resolve_max_new_tokens(self, forced_decoder_ids: list[tuple[int, int]]) -> int:
        max_target_positions = getattr(self.model.config, "max_target_positions", None)
        if not isinstance(max_target_positions, int):
            return DECODER_MAX_TOKENS

        decoder_input_len = len(forced_decoder_ids) + WHISPER_DECODER_START_TOKEN_COUNT
        available_budget = max_target_positions - decoder_input_len
        return max(1, min(DECODER_MAX_TOKENS, available_budget))
