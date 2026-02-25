"""Training configuration with sensible defaults for Whisper fine-tuning."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TrainingConfig:
    base_model: str = "openai/whisper-small"
    language: str = "mg"
    task: str = "transcribe"

    epochs: int = 10
    batch_size: int = 4
    gradient_accumulation_steps: int = 2
    learning_rate: float = 1e-5
    warmup_ratio: float = 0.1
    weight_decay: float = 0.01

    eval_steps: int = 50
    save_steps: int = 100
    logging_steps: int = 10

    max_label_length: int = 448

    @staticmethod
    def use_fp16(device: str) -> bool:
        return device.startswith("cuda")
