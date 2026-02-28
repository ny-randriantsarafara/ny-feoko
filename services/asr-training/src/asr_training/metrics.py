"""Metrics for Whisper fine-tuning evaluation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import evaluate

if TYPE_CHECKING:
    from transformers import EvalPrediction, WhisperProcessor


def make_compute_metrics(processor: WhisperProcessor):
    """Create a compute_metrics function that captures the processor.

    Args:
        processor: WhisperProcessor for tokenizer access.

    Returns:
        A callable suitable for Seq2SeqTrainer(compute_metrics=...).
    """
    wer_metric = evaluate.load("wer")

    def compute_metrics(pred) -> dict[str, float]:  # noqa: ANN001
        pred_ids = pred.predictions
        label_ids = pred.label_ids
        label_ids[label_ids == -100] = processor.tokenizer.pad_token_id

        decoded_preds = processor.tokenizer.batch_decode(
            pred_ids, skip_special_tokens=True
        )
        decoded_labels = processor.tokenizer.batch_decode(
            label_ids, skip_special_tokens=True
        )

        wer = wer_metric.compute(
            predictions=decoded_preds, references=decoded_labels
        )
        return {"wer": wer}

    return compute_metrics
