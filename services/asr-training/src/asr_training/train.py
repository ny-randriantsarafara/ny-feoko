"""Whisper fine-tuning using HuggingFace Seq2SeqTrainer."""

from __future__ import annotations

from pathlib import Path

import evaluate
from rich.console import Console
from transformers import (
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
    TrainerCallback,
    WhisperForConditionalGeneration,
    WhisperProcessor,
)

from asr_training.collator import WhisperDataCollator
from asr_training.config import TrainingConfig
from asr_training.dataset import load_training_data

console = Console()


class ColabProgressCallback(TrainerCallback):
    """Callback to print training progress for Colab visibility."""

    def on_log(self, args, state, control, logs=None, **kwargs):  # noqa: ANN001, ARG002
        if logs is None:
            return
        step = state.global_step
        parts = [f"Step {step}"]
        if "loss" in logs:
            parts.append(f"loss={logs['loss']:.4f}")
        if "eval_loss" in logs:
            parts.append(f"eval_loss={logs['eval_loss']:.4f}")
        if "eval_wer" in logs:
            parts.append(f"wer={logs['eval_wer']:.4f}")
        print(" | ".join(parts), flush=True)


def fine_tune(
    config: TrainingConfig,
    data_dir: Path,
    output_dir: Path,
    device: str,
) -> Path:
    """Fine-tune a Whisper model and save it to output_dir.

    Returns the path to the saved model.
    """
    console.print(f"Loading base model [bold]{config.base_model}[/]...")
    processor = WhisperProcessor.from_pretrained(
        config.base_model, language=config.language, task=config.task
    )
    model = WhisperForConditionalGeneration.from_pretrained(config.base_model)
    model.generation_config.language = config.language
    model.generation_config.task = config.task
    model.generation_config.forced_decoder_ids = None

    console.print(f"Loading dataset from [bold]{data_dir}[/]...")
    dataset = load_training_data(data_dir, processor, config)
    console.print(
        f"  train: {len(dataset['train'])} samples, "
        f"test: {len(dataset['test'])} samples"
    )

    collator = WhisperDataCollator(processor=processor)
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

    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset["train"],
        eval_dataset=dataset["test"],
        data_collator=collator,
        compute_metrics=compute_metrics,
        processing_class=processor.feature_extractor,
        callbacks=[ColabProgressCallback()],
    )

    console.print(
        f"Starting training on [bold]{device}[/] "
        f"(fp16={use_fp16}, epochs={config.epochs})..."
    )
    trainer.train()

    model_dir = output_dir / "model"
    model_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(model_dir))
    processor.save_pretrained(str(model_dir))

    console.print(f"[bold green]Model saved to {model_dir}[/]")
    return model_dir


def push_to_hub(model_dir: Path, repo_id: str) -> None:
    """Push a saved model and processor to HuggingFace Hub."""
    processor = WhisperProcessor.from_pretrained(str(model_dir))
    model = WhisperForConditionalGeneration.from_pretrained(str(model_dir))

    processor.push_to_hub(repo_id)
    model.push_to_hub(repo_id)

    console.print(f"[bold green]Pushed to https://huggingface.co/{repo_id}[/]")
