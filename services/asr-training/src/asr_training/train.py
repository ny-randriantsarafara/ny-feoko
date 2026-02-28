"""Whisper fine-tuning using HuggingFace Seq2SeqTrainer."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from transformers import (
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
    WhisperForConditionalGeneration,
    WhisperProcessor,
)

from asr_training.callbacks import TrainingProgressCallback
from asr_training.collator import WhisperDataCollator
from asr_training.config import TrainingConfig
from asr_training.dataset import load_training_data
from asr_training.metrics import make_compute_metrics

console = Console()


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
    compute_metrics = make_compute_metrics(processor)

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
        callbacks=[TrainingProgressCallback()],
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

    model_size_mb = sum(
        f.stat().st_size for f in model_dir.rglob("*") if f.is_file()
    ) / (1024 * 1024)
    console.print(
        f"[bold green]Model saved to {model_dir}[/] ({model_size_mb:.0f} MB)"
    )
    return model_dir


def push_to_hub(model_dir: Path, repo_id: str) -> None:
    """Push a saved model and processor to HuggingFace Hub."""
    processor = WhisperProcessor.from_pretrained(str(model_dir))
    model = WhisperForConditionalGeneration.from_pretrained(str(model_dir))

    processor.push_to_hub(repo_id)
    model.push_to_hub(repo_id)

    console.print(f"[bold green]Pushed to https://huggingface.co/{repo_id}[/]")
