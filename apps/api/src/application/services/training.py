"""Whisper fine-tuning and re-drafting service."""

from __future__ import annotations

import logging
import time

from dataclasses import dataclass
from pathlib import Path

import soundfile as sf
import torch
from datasets import DatasetDict, load_dataset
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
)
from transformers import (
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
    TrainerCallback,
    WhisperForConditionalGeneration,
    WhisperProcessor,
)

from infra.telemetry.gpu import get_gpu_memory_info, format_gpu_memory

console = Console()
logger = logging.getLogger(__name__)

SAMPLE_RATE = 16_000
DECODER_MAX_TOKENS = 448
DECODER_MAX_TOKENS_WITH_MARGIN = 444


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


class RichProgressCallback(TrainerCallback):
    """Training callback with Rich progress bar and GPU monitoring."""

    def __init__(self, gpu_log_interval: int = 50):
        self.gpu_log_interval = gpu_log_interval
        self.progress: Progress | None = None
        self.task_id = None
        self.last_loss = 0.0
        self.last_wer = 0.0

    def on_train_begin(self, args, state, control, **kwargs):
        gpu_info = get_gpu_memory_info()
        logger.info(format_gpu_memory(gpu_info))
        logger.info(
            "Training started: %d epochs, %d total steps",
            args.num_train_epochs,
            state.max_steps,
        )

        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]Training"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("loss={task.fields[loss]:.3f}"),
            TextColumn("wer={task.fields[wer]:.2f}"),
            TextColumn("VRAM={task.fields[vram]}"),
            TimeRemainingColumn(),
            console=console,
        )
        self.progress.start()
        self.task_id = self.progress.add_task(
            "train",
            total=state.max_steps,
            loss=0.0,
            wer=0.0,
            vram="--",
        )

    def on_log(self, args, state, control, logs=None, **kwargs):
        if logs:
            self.last_loss = logs.get("loss", self.last_loss)
            logger.debug("Step %d: %s", state.global_step, logs)

        # Update progress bar
        if self.progress and self.task_id is not None:
            vram_str = "--"
            if state.global_step % self.gpu_log_interval == 0:
                gpu_info = get_gpu_memory_info()
                if gpu_info.get("available"):
                    vram_str = f"{gpu_info['used_gb']:.1f}GB"
                    logger.debug(format_gpu_memory(gpu_info))

            self.progress.update(
                self.task_id,
                completed=state.global_step,
                loss=self.last_loss,
                wer=self.last_wer,
                vram=vram_str,
            )

    def on_evaluate(self, args, state, control, metrics=None, **kwargs):
        if metrics:
            self.last_wer = metrics.get("eval_wer", 0)
            logger.info("Eval at step %d: WER=%.4f", state.global_step, self.last_wer)

    def on_train_end(self, args, state, control, **kwargs):
        if self.progress:
            self.progress.stop()
        logger.info(
            "Training complete: %d steps, best WER=%.4f",
            state.global_step,
            state.best_metric or 0,
        )
        gpu_info = get_gpu_memory_info()
        logger.info("Final %s", format_gpu_memory(gpu_info))


def fine_tune(
    config: TrainingConfig,
    data_dir: Path,
    output_dir: Path,
    device: str,
) -> Path:
    """Fine-tune a Whisper model and save it to output_dir. Returns model path."""
    logger.info(
        "Fine-tuning started: model=%s, epochs=%d, batch_size=%d, device=%s",
        config.base_model,
        config.epochs,
        config.batch_size,
        device,
    )
    start_time = time.perf_counter()

    processor = WhisperProcessor.from_pretrained(
        config.base_model, language=config.language, task=config.task
    )
    model = WhisperForConditionalGeneration.from_pretrained(config.base_model)
    model.generation_config.language = config.language
    model.generation_config.task = config.task
    model.generation_config.forced_decoder_ids = None

    logger.debug("Model and processor loaded from %s", config.base_model)
    if device.startswith("cuda") and torch.cuda.is_available():
        logger.debug(
            "GPU memory allocated: %.2f MB",
            torch.cuda.memory_allocated() / 1024 / 1024,
        )

    dataset = _load_training_data(data_dir, processor, config)

    logger.debug(
        "Dataset loaded: train=%d samples, test=%d samples",
        len(dataset["train"]),
        len(dataset["test"]),
    )

    collator = _WhisperDataCollator(processor=processor)
    compute_metrics = _make_compute_metrics(processor)

    use_fp16 = config.use_fp16(device)
    training_args = Seq2SeqTrainingArguments(
        output_dir=str(output_dir / "checkpoints"),
        per_device_train_batch_size=config.batch_size,
        per_device_eval_batch_size=config.batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        learning_rate=config.learning_rate,
        warmup_ratio=config.warmup_ratio,
        weight_decay=config.weight_decay,
        num_train_epochs=config.epochs,
        fp16=use_fp16,
        eval_strategy="steps",
        eval_steps=config.eval_steps,
        save_strategy="steps",
        save_steps=config.save_steps,
        logging_steps=config.logging_steps,
        save_total_limit=3,
        load_best_model_at_end=True,
        metric_for_best_model="wer",
        greater_is_better=False,
        predict_with_generate=True,
        generation_max_length=config.max_label_length,
        report_to="none",
        use_cpu=device == "cpu",
    )

    logger.debug("Training config: fp16=%s, use_cpu=%s", use_fp16, device == "cpu")

    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset["train"],
        eval_dataset=dataset["test"],
        data_collator=collator,
        compute_metrics=compute_metrics,
        processing_class=processor.feature_extractor,
        callbacks=[RichProgressCallback(gpu_log_interval=50)],
    )

    trainer.train()

    model_dir = output_dir / "model"
    model_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(model_dir))
    processor.save_pretrained(str(model_dir))

    elapsed = time.perf_counter() - start_time
    logger.info("Fine-tuning complete in %.2fs, model saved to %s", elapsed, model_dir)
    logger.debug("Model and processor saved to %s", model_dir)

    return model_dir


def push_to_hub(model_dir: Path, repo_id: str) -> None:
    """Push a saved model and processor to HuggingFace Hub."""
    logger.info("Pushing model to HuggingFace Hub: %s -> %s", model_dir, repo_id)
    processor = WhisperProcessor.from_pretrained(str(model_dir))
    model = WhisperForConditionalGeneration.from_pretrained(str(model_dir))
    logger.debug("Model and processor loaded from %s", model_dir)
    processor.push_to_hub(repo_id)
    model.push_to_hub(repo_id)
    logger.info("Push complete: %s", repo_id)


def redraft_pending(
    model_path: str,
    source_dir: Path,
    pending_clips: list[dict[str, str]],
    device: str,
    language: str = "mg",
) -> tuple[int, int]:
    """Re-transcribe clips and return (updated_count, skipped_count).

    Note: this function does NOT write to the database. It returns transcriptions
    and the caller (use-case) handles persistence.
    """
    logger.info(
        "Redraft started: %d clips, model=%s, device=%s",
        len(pending_clips),
        model_path,
        device,
    )
    start_time = time.perf_counter()

    processor = WhisperProcessor.from_pretrained(model_path)
    model = WhisperForConditionalGeneration.from_pretrained(model_path)
    model.to(device).eval()
    logger.debug("Model loaded and moved to %s", device)

    forced_decoder_ids = processor.get_decoder_prompt_ids(language=language, task="transcribe")

    updated = 0
    skipped = 0
    results: list[tuple[str, str]] = []

    for clip in pending_clips:
        file_name = clip["file_name"]
        wav_path = source_dir / file_name

        if not wav_path.exists():
            logger.debug("Skipped missing file: %s", wav_path)
            skipped += 1
            continue

        text = _transcribe_clip(wav_path, processor, model, device, forced_decoder_ids)
        results.append((clip["id"], text))
        updated += 1
        logger.debug("Processed clip %s: %d chars", file_name, len(text))

    elapsed = time.perf_counter() - start_time
    logger.info(
        "Redraft complete in %.2fs: %d updated, %d skipped",
        elapsed,
        updated,
        skipped,
    )
    return updated, skipped


def get_transcriptions(
    model_path: str,
    source_dir: Path,
    pending_clips: list[dict[str, str]],
    device: str,
    language: str = "mg",
) -> list[tuple[str, str]]:
    """Transcribe clips and return list of (clip_id, text) pairs."""
    logger.info(
        "Transcription started: %d clips, model=%s, device=%s",
        len(pending_clips),
        model_path,
        device,
    )
    start_time = time.perf_counter()

    processor = WhisperProcessor.from_pretrained(model_path)
    model = WhisperForConditionalGeneration.from_pretrained(model_path)
    model.to(device).eval()
    logger.debug("Model loaded and moved to %s", device)

    forced_decoder_ids = processor.get_decoder_prompt_ids(language=language, task="transcribe")

    results: list[tuple[str, str]] = []
    for clip in pending_clips:
        wav_path = source_dir / clip["file_name"]
        if not wav_path.exists():
            logger.debug("Skipped missing file: %s", wav_path)
            continue
        text = _transcribe_clip(wav_path, processor, model, device, forced_decoder_ids)
        logger.debug("Transcribed clip %s: %d chars", clip["file_name"], len(text))
        results.append((clip["id"], text))

    elapsed = time.perf_counter() - start_time
    logger.info(
        "Transcription complete in %.2fs: %d clips processed",
        elapsed,
        len(results),
    )
    return results


def _transcribe_clip(
    wav_path: Path,
    processor: WhisperProcessor,
    model: WhisperForConditionalGeneration,
    device: str,
    forced_decoder_ids: list[tuple[int, int]],
) -> str:
    audio, sr = sf.read(str(wav_path), dtype="float32")
    if sr != SAMPLE_RATE:
        raise RuntimeError(f"Expected {SAMPLE_RATE}Hz audio, got {sr}Hz in {wav_path}")

    duration = len(audio) / sr
    logger.debug("Audio loaded: %s, duration=%.2fs, sr=%d", wav_path.name, duration, sr)
    inference_start = time.perf_counter()

    inputs = processor(audio, sampling_rate=SAMPLE_RATE, return_tensors="pt")
    input_features = inputs.input_features.to(device)

    with torch.no_grad():
        predicted_ids = model.generate(
            input_features,
            forced_decoder_ids=forced_decoder_ids,
            max_new_tokens=DECODER_MAX_TOKENS_WITH_MARGIN,
        )

    inference_time = time.perf_counter() - inference_start
    logger.debug("Inference complete in %.3fs", inference_time)

    return processor.batch_decode(predicted_ids, skip_special_tokens=True)[0].strip()


def _load_training_data(
    data_dir: Path,
    processor: WhisperProcessor,
    config: TrainingConfig,
) -> DatasetDict:
    logger.debug("Loading training data from %s", data_dir)
    load_start = time.perf_counter()

    ds = load_dataset("audiofolder", data_dir=str(data_dir))

    if not isinstance(ds, DatasetDict):
        ds = DatasetDict({"train": ds})

    if "test" not in ds:
        split = ds["train"].train_test_split(test_size=0.1, seed=42)
        ds = DatasetDict({"train": split["train"], "test": split["test"]})

    logger.debug(
        "Dataset split: train=%d, test=%d",
        len(ds["train"]),
        len(ds["test"]),
    )

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

    elapsed = time.perf_counter() - load_start
    logger.debug("Dataset preprocessing complete in %.2fs", elapsed)

    return ds


@dataclass
class _WhisperDataCollator:
    processor: WhisperProcessor

    def __call__(self, features: list[dict]) -> dict[str, torch.Tensor]:
        input_features = [{"input_features": f["input_features"]} for f in features]
        batch = self.processor.feature_extractor.pad(input_features, return_tensors="pt")

        label_features = [{"input_ids": f["labels"]} for f in features]
        labels_batch = self.processor.tokenizer.pad(label_features, return_tensors="pt")

        labels = labels_batch["input_ids"]
        labels = labels.masked_fill(labels_batch.attention_mask.eq(0), -100)

        batch["labels"] = labels
        return batch


def _make_compute_metrics(processor: WhisperProcessor):  # noqa: ANN202
    import evaluate

    wer_metric = evaluate.load("wer")

    def compute_metrics(pred) -> dict[str, float]:  # noqa: ANN001
        pred_ids = pred.predictions
        label_ids = pred.label_ids
        label_ids[label_ids == -100] = processor.tokenizer.pad_token_id

        decoded_preds = processor.tokenizer.batch_decode(pred_ids, skip_special_tokens=True)
        decoded_labels = processor.tokenizer.batch_decode(label_ids, skip_special_tokens=True)

        wer = wer_metric.compute(predictions=decoded_preds, references=decoded_labels)
        return {"wer": wer}

    return compute_metrics
