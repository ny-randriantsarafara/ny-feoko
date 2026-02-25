"""Load and preprocess audiofolder datasets for Whisper fine-tuning."""

from __future__ import annotations

from pathlib import Path

from datasets import DatasetDict, load_dataset
from transformers import WhisperProcessor

from asr_training.config import TrainingConfig

SAMPLE_RATE = 16_000


def load_training_data(
    data_dir: Path,
    processor: WhisperProcessor,
    config: TrainingConfig,
) -> DatasetDict:
    """Load an audiofolder dataset and preprocess for Whisper.

    Expects data_dir to contain train/ and optionally test/ subdirectories,
    each with WAV files and a metadata.csv (columns: file_name, transcription).
    """
    ds = load_dataset("audiofolder", data_dir=str(data_dir))

    if not isinstance(ds, DatasetDict):
        ds = DatasetDict({"train": ds})

    if "test" not in ds:
        split = ds["train"].train_test_split(test_size=0.1, seed=42)
        ds = DatasetDict({"train": split["train"], "test": split["test"]})

    tokenizer = processor.tokenizer
    feature_extractor = processor.feature_extractor

    def preprocess(batch: dict) -> dict:
        audio_arrays = [sample["array"] for sample in batch["audio"]]
        sampling_rates = [sample["sampling_rate"] for sample in batch["audio"]]

        features = feature_extractor(
            audio_arrays,
            sampling_rate=sampling_rates[0],
            return_tensors="np",
        )

        labels = tokenizer(
            batch["transcription"],
            max_length=config.max_label_length,
            truncation=True,
        )

        return {
            "input_features": features.input_features,
            "labels": labels.input_ids,
        }

    ds = ds.map(
        preprocess,
        batched=True,
        batch_size=32,
        remove_columns=ds["train"].column_names,
    )

    return ds
