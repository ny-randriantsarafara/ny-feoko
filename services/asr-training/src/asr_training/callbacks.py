"""Training callbacks for Whisper fine-tuning."""

from __future__ import annotations

import time

from rich.console import Console
from transformers import (
    TrainerCallback,
    TrainerControl,
    TrainerState,
    TrainingArguments,
)

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
        console.print(
            "  [dim]eval_loss[/] — should also decrease; if it rises while loss drops, "
            "the model is overfitting"
        )
        console.print(
            "  [dim]WER[/]       — Word Error Rate: 0 = perfect, 1 = random. "
            "Below 0.5 is a good start for a low-resource language"
        )
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
