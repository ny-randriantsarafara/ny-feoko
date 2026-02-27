"""Whisper fine-tuning using HuggingFace Seq2SeqTrainer."""

from __future__ import annotations

import time
from pathlib import Path

import evaluate
from rich.console import Console
from transformers import (
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
    TrainerCallback,
    TrainerControl,
    TrainerState,
    TrainingArguments,
    WhisperForConditionalGeneration,
    WhisperProcessor,
)

from asr_training.collator import WhisperDataCollator
from asr_training.config import TrainingConfig
from asr_training.dataset import load_training_data

console = Console()


class TrainingProgressCallback(TrainerCallback):
    """Callback that tracks training health and prints actionable guidance."""

    def __init__(self) -> None:
        self.best_wer: float | None = None
        self.best_wer_step: int = 0
        self.last_eval_losses: list[float] = []
        self.final_train_loss: float | None = None
        self.final_eval_loss: float | None = None
        self.final_wer: float | None = None
        self.overfitting_warned = False
        self.train_start_time: float = 0.0

    def on_train_begin(
        self,
        args: TrainingArguments,  # noqa: ARG002
        state: TrainerState,  # noqa: ARG002
        control: TrainerControl,  # noqa: ARG002
        **kwargs: object,  # noqa: ARG002
    ) -> None:
        self.train_start_time = time.monotonic()
        console.print()
        console.print("[bold]What to watch during training:[/]")
        console.print("  [dim]loss[/]      — should decrease over time")
        console.print("  [dim]eval_loss[/] — should also decrease; if it rises while loss drops, "
                       "the model is overfitting")
        console.print("  [dim]WER[/]       — Word Error Rate: 0 = perfect, 1 = random. "
                       "Below 0.5 is a good start for a low-resource language")
        console.print()

    def on_log(
        self,
        args: TrainingArguments,  # noqa: ARG002
        state: TrainerState,
        control: TrainerControl,  # noqa: ARG002
        logs: dict[str, float] | None = None,
        **kwargs: object,  # noqa: ARG002
    ) -> None:
        if logs is None:
            return
        step = state.global_step
        parts = [f"Step {step}"]
        if "loss" in logs:
            self.final_train_loss = logs["loss"]
            parts.append(f"loss={logs['loss']:.4f}")
        if "eval_loss" in logs:
            self.final_eval_loss = logs["eval_loss"]
            parts.append(f"eval_loss={logs['eval_loss']:.4f}")
            self.last_eval_losses.append(logs["eval_loss"])
            self._check_overfitting()
        if "eval_wer" in logs:
            wer = logs["eval_wer"]
            self.final_wer = wer
            parts.append(f"wer={wer:.4f}")
            if self.best_wer is None or wer < self.best_wer:
                self.best_wer = wer
                self.best_wer_step = step
        print(" | ".join(parts), flush=True)

    def on_train_end(
        self,
        args: TrainingArguments,  # noqa: ARG002
        state: TrainerState,  # noqa: ARG002
        control: TrainerControl,  # noqa: ARG002
        **kwargs: object,  # noqa: ARG002
    ) -> None:
        elapsed = time.monotonic() - self.train_start_time
        _print_training_summary(
            elapsed_sec=elapsed,
            final_train_loss=self.final_train_loss,
            final_eval_loss=self.final_eval_loss,
            best_wer=self.best_wer,
            best_wer_step=self.best_wer_step,
            final_wer=self.final_wer,
        )

    def _check_overfitting(self) -> None:
        if self.overfitting_warned or len(self.last_eval_losses) < 3:
            return
        recent = self.last_eval_losses[-3:]
        if recent[0] < recent[1] < recent[2]:
            console.print(
                "\n  [yellow]Warning: eval_loss has increased for 3 consecutive evaluations. "
                "This may indicate overfitting.[/]\n"
                "  [dim]Consider stopping early or reducing --epochs.[/]\n"
            )
            self.overfitting_warned = True


def _print_training_summary(
    *,
    elapsed_sec: float,
    final_train_loss: float | None,
    final_eval_loss: float | None,
    best_wer: float | None,
    best_wer_step: int,
    final_wer: float | None,
) -> None:
    from rich.panel import Panel
    from rich.table import Table

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("metric", style="dim")
    table.add_column("value")

    minutes = int(elapsed_sec // 60)
    secs = int(elapsed_sec % 60)
    table.add_row("Training time", f"{minutes}m {secs}s")

    if final_train_loss is not None:
        table.add_row("Final train loss", f"{final_train_loss:.4f}")
    if final_eval_loss is not None:
        table.add_row("Final eval loss", f"{final_eval_loss:.4f}")
    if best_wer is not None:
        table.add_row("Best WER", f"{best_wer:.4f}  (at step {best_wer_step})")
    if final_wer is not None and best_wer is not None and final_wer != best_wer:
        table.add_row("Final WER", f"{final_wer:.4f}")

    verdict_lines: list[str] = []
    if best_wer is not None:
        if best_wer < 0.3:
            verdict_lines.append("[green]WER is strong[/] — the model is learning Malagasy well.")
        elif best_wer < 0.6:
            verdict_lines.append(
                "[green]WER is reasonable[/] — drafts should be noticeably better. "
                "More corrected data will improve it further."
            )
        else:
            verdict_lines.append(
                "[yellow]WER is still high[/] — the model needs more training data. "
                "Correct more clips and iterate again."
            )

    if (
        final_eval_loss is not None
        and final_train_loss is not None
        and final_eval_loss > final_train_loss * 1.5
    ):
        verdict_lines.append(
            "[yellow]Possible overfitting[/] — eval_loss is much higher than train_loss. "
            "Try fewer [bold]--epochs[/] or more training data."
        )

    verdict = "\n".join(verdict_lines) if verdict_lines else "[green]Training complete.[/]"

    console.print()
    console.print(Panel(table, title="Training Results", border_style="blue"))
    console.print(Panel(verdict, title="Assessment", border_style="dim"))


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
