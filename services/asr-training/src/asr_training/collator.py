"""Data collator for Whisper sequence-to-sequence training."""

from __future__ import annotations

from dataclasses import dataclass

import torch
from transformers import WhisperProcessor


@dataclass
class WhisperDataCollator:
    """Pad input features and labels to the longest sample in the batch.

    Label padding tokens are replaced with -100 so the loss function ignores them.
    """

    processor: WhisperProcessor

    def __call__(self, features: list[dict]) -> dict[str, torch.Tensor]:
        input_features = [{"input_features": f["input_features"]} for f in features]
        batch = self.processor.feature_extractor.pad(
            input_features, return_tensors="pt"
        )

        label_features = [{"input_ids": f["labels"]} for f in features]
        labels_batch = self.processor.tokenizer.pad(
            label_features, return_tensors="pt"
        )

        labels = labels_batch["input_ids"]
        labels = labels.masked_fill(
            labels_batch.attention_mask.eq(0), -100
        )

        batch["labels"] = labels
        return batch
