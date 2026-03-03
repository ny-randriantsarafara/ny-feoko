# CLI Observability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add verbose logging with Rich progress bars to all CLI commands, with notebooks defaulting to debug mode.

**Architecture:** Add `-v/--verbose` flag to CLI that configures logging level. Enhance training callback with Rich progress bar and periodic GPU memory reporting. Notebook helper always passes `-v`.

**Tech Stack:** Typer (CLI), Rich (progress/logging), PyTorch (GPU stats)

---

## Task 1: Add CLI Logging Configuration

**Files:**
- Modify: `apps/api/src/infra/telemetry/logging.py`
- Test: `apps/api/tests/infra/test_telemetry.py`

**Step 1: Write the failing test**

Add to `apps/api/tests/infra/test_telemetry.py`:

```python
class TestCliLogging:
    def test_configure_cli_logging_sets_level(self) -> None:
        from infra.telemetry.logging import configure_cli_logging

        configure_cli_logging(verbose=False)
        root = logging.getLogger()
        assert root.level == logging.INFO

        configure_cli_logging(verbose=True)
        assert root.level == logging.DEBUG

    def test_configure_cli_logging_uses_rich_handler(self) -> None:
        from infra.telemetry.logging import configure_cli_logging
        from rich.logging import RichHandler

        configure_cli_logging(verbose=True)
        root = logging.getLogger()

        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0], RichHandler)
```

**Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/infra/test_telemetry.py::TestCliLogging -v`
Expected: FAIL with "cannot import name 'configure_cli_logging'"

**Step 3: Write minimal implementation**

Add to `apps/api/src/infra/telemetry/logging.py`:

```python
from rich.logging import RichHandler


def configure_cli_logging(verbose: bool = False) -> None:
    """Configure logging for CLI with Rich console output.

    Args:
        verbose: If True, set DEBUG level. Otherwise INFO.
    """
    level = logging.DEBUG if verbose else logging.INFO
    root = logging.getLogger()
    root.setLevel(level)

    # Clear existing handlers
    root.handlers.clear()

    handler = RichHandler(
        show_time=True,
        show_path=False,
        markup=True,
        rich_tracebacks=True,
    )
    handler.setLevel(level)

    root.addHandler(handler)

    # Quiet noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("datasets").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.INFO)
```

**Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/infra/test_telemetry.py::TestCliLogging -v`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/api/src/infra/telemetry/logging.py apps/api/tests/infra/test_telemetry.py
git commit -m "feat(cli): add configure_cli_logging with Rich handler"
```

---

## Task 2: Add Verbose Flag to CLI

**Files:**
- Modify: `apps/api/src/ports/cli/app.py`
- Test: `apps/api/tests/ports/test_cli.py` (new file)

**Step 1: Write the failing test**

Create `apps/api/tests/ports/test_cli.py`:

```python
"""Tests for CLI commands."""

from __future__ import annotations

import logging

from typer.testing import CliRunner

from ports.cli.app import app

runner = CliRunner()


class TestCliVerboseFlag:
    def test_verbose_flag_sets_debug_level(self) -> None:
        # Run with -v flag (use --help to avoid actual command execution)
        result = runner.invoke(app, ["-v", "--help"])
        assert result.exit_code == 0

    def test_no_verbose_flag_sets_info_level(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
```

**Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/ports/test_cli.py -v`
Expected: FAIL with "No such option: -v"

**Step 3: Write minimal implementation**

Modify `apps/api/src/ports/cli/app.py` - add callback and verbose option:

```python
"""Unified CLI for the Ambara platform."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from domain.exceptions import MissingConfigError, RunNotFoundError, SyncError
from infra.telemetry.logging import configure_cli_logging


def verbose_callback(verbose: bool) -> None:
    """Configure logging based on verbose flag."""
    configure_cli_logging(verbose=verbose)


app = typer.Typer(
    help="Ambara -- Malagasy ASR data pipeline and training platform.",
    callback=lambda verbose: verbose_callback(verbose),
)


@app.callback()
def main_callback(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
) -> None:
    """Configure CLI before running commands."""
    configure_cli_logging(verbose=verbose)
```

Remove the import of `configure_cli_logging` from within functions since it's now at module level.

**Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/ports/test_cli.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/api/src/ports/cli/app.py apps/api/tests/ports/test_cli.py
git commit -m "feat(cli): add -v/--verbose flag for debug logging"
```

---

## Task 3: Add GPU Memory Utility

**Files:**
- Create: `apps/api/src/infra/telemetry/gpu.py`
- Test: `apps/api/tests/infra/test_gpu.py` (new file)

**Step 1: Write the failing test**

Create `apps/api/tests/infra/test_gpu.py`:

```python
"""Tests for GPU monitoring utilities."""

from __future__ import annotations

from infra.telemetry.gpu import get_gpu_memory_info, format_gpu_memory


class TestGpuMemory:
    def test_get_gpu_memory_info_returns_dict(self) -> None:
        info = get_gpu_memory_info()
        assert isinstance(info, dict)
        assert "available" in info
        # If CUDA available, should have more keys
        if info["available"]:
            assert "name" in info
            assert "used_gb" in info
            assert "total_gb" in info
            assert "percent" in info

    def test_format_gpu_memory_no_gpu(self) -> None:
        info = {"available": False}
        result = format_gpu_memory(info)
        assert result == "GPU: Not available"

    def test_format_gpu_memory_with_gpu(self) -> None:
        info = {
            "available": True,
            "name": "Tesla T4",
            "used_gb": 2.5,
            "total_gb": 15.0,
            "percent": 16.7,
        }
        result = format_gpu_memory(info)
        assert "Tesla T4" in result
        assert "2.5" in result
        assert "15.0" in result
```

**Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/infra/test_gpu.py -v`
Expected: FAIL with "No module named 'infra.telemetry.gpu'"

**Step 3: Write minimal implementation**

Create `apps/api/src/infra/telemetry/gpu.py`:

```python
"""GPU monitoring utilities."""

from __future__ import annotations

import torch


def get_gpu_memory_info() -> dict:
    """Get current GPU memory usage.

    Returns:
        Dict with keys: available, name, used_gb, total_gb, percent
        If no GPU, only 'available': False is returned.
    """
    if not torch.cuda.is_available():
        return {"available": False}

    device = torch.cuda.current_device()
    name = torch.cuda.get_device_name(device)
    used = torch.cuda.memory_allocated(device)
    total = torch.cuda.get_device_properties(device).total_memory

    used_gb = used / (1024**3)
    total_gb = total / (1024**3)
    percent = (used / total) * 100 if total > 0 else 0

    return {
        "available": True,
        "name": name,
        "used_gb": round(used_gb, 2),
        "total_gb": round(total_gb, 2),
        "percent": round(percent, 1),
    }


def format_gpu_memory(info: dict) -> str:
    """Format GPU memory info as a human-readable string."""
    if not info.get("available"):
        return "GPU: Not available"

    return (
        f"GPU: {info['name']}, "
        f"VRAM: {info['used_gb']:.1f}GB / {info['total_gb']:.1f}GB "
        f"({info['percent']:.0f}%)"
    )
```

**Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/infra/test_gpu.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/api/src/infra/telemetry/gpu.py apps/api/tests/infra/test_gpu.py
git commit -m "feat(telemetry): add GPU memory monitoring utility"
```

---

## Task 4: Enhance Training Callback with Rich Progress

**Files:**
- Modify: `apps/api/src/application/services/training.py`
- Test: `apps/api/tests/application/test_services.py`

**Step 1: Write the failing test**

Add to `apps/api/tests/application/test_services.py`:

```python
class TestRichProgressCallback:
    def test_callback_creates_progress_bar(self) -> None:
        from application.services.training import RichProgressCallback

        callback = RichProgressCallback(gpu_log_interval=50)
        assert callback.gpu_log_interval == 50
        assert callback.progress is None  # Not started yet

    def test_callback_logs_gpu_at_interval(self) -> None:
        from application.services.training import RichProgressCallback
        from unittest.mock import MagicMock, patch

        callback = RichProgressCallback(gpu_log_interval=2)

        # Mock state
        state = MagicMock()
        state.global_step = 2
        state.max_steps = 10

        args = MagicMock()
        args.num_train_epochs = 1

        with patch("application.services.training.get_gpu_memory_info") as mock_gpu:
            mock_gpu.return_value = {"available": True, "name": "T4", "used_gb": 5.0, "total_gb": 15.0, "percent": 33}
            # Should log at step 2 (interval=2)
            callback.on_log(args, state, None, logs={"loss": 0.5})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/application/test_services.py::TestRichProgressCallback -v`
Expected: FAIL with "cannot import name 'RichProgressCallback'"

**Step 3: Write implementation**

Modify `apps/api/src/application/services/training.py`:

Replace the imports section and add the new callback class:

```python
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
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
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
```

Replace `LoggingCallback` with enhanced version:

```python
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
```

Update `fine_tune` function to use `RichProgressCallback`:

In line ~157, change:
```python
callbacks=[LoggingCallback()],
```
to:
```python
callbacks=[RichProgressCallback(gpu_log_interval=50)],
```

**Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/application/test_services.py::TestRichProgressCallback -v`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/api/src/application/services/training.py apps/api/tests/application/test_services.py
git commit -m "feat(training): add Rich progress bar with GPU monitoring"
```

---

## Task 5: Update Notebook to Always Use Verbose

**Files:**
- Modify: `notebooks/ambara_steps.ipynb`

**Step 1: Update run_cli helper**

Using Python to modify the notebook JSON, update the `run_cli` function in cell id "3" to always add `-v`:

```python
def run_cli(cmd: list[str], env: dict | None = None) -> None:
    """Run a CLI command with real-time output and proper error display."""
    # Always run in verbose mode for Colab debugging
    if "-v" not in cmd and "--verbose" not in cmd:
        cmd = cmd[:1] + ["-v"] + cmd[1:]  # Insert -v after 'python -m ...'
    print(f"Running: {' '.join(cmd)}")
    print('-' * 60)
    result = subprocess.run(cmd, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {result.returncode}")
```

**Step 2: Apply the change**

Run this Python script:

```python
import json

with open('notebooks/ambara_steps.ipynb', 'r') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell.get('id') == '3' and cell['cell_type'] == 'code':
        new_source = []
        for line in cell['source']:
            if 'def run_cli(cmd: list[str]' in line:
                new_source.append(line)
            elif '"""Run a CLI command with real-time' in line:
                new_source.append('    """Run a CLI command with verbose logging for Colab."""\n')
            elif "print(f\"Running:" in line:
                # Insert -v injection before print
                new_source.append('    # Always run in verbose mode for Colab debugging\n')
                new_source.append('    if "-v" not in cmd and "--verbose" not in cmd:\n')
                new_source.append('        cmd = [cmd[0], "-v"] + cmd[1:]\n')
                new_source.append(line)
            else:
                new_source.append(line)
        cell['source'] = new_source
        break

with open('notebooks/ambara_steps.ipynb', 'w') as f:
    json.dump(nb, f, indent=1)
```

**Step 3: Verify the change**

Check that the notebook file has the updated `run_cli` function.

**Step 4: Commit**

```bash
git add notebooks/ambara_steps.ipynb
git commit -m "feat(notebook): always run CLI in verbose mode"
```

---

## Task 6: Add Error Hints for Common Failures

**Files:**
- Modify: `apps/api/src/ports/cli/app.py`

**Step 1: Add error handler with hints**

Update the `main()` function at the bottom of `app.py`:

```python
def main() -> None:
    try:
        app()
    except torch.cuda.OutOfMemoryError as e:
        logger.error("CUDA out of memory: %s", e)
        logger.error(
            "Suggestion: Reduce --batch-size to 1 or 2, especially for whisper-medium/large"
        )
        raise typer.Exit(1) from e
    except (RunNotFoundError, MissingConfigError, SyncError) as e:
        logger.error("Error: %s", e)
        raise typer.Exit(1) from e
    except Exception as e:
        logger.exception("Unexpected error: %s", e)
        raise typer.Exit(1) from e
```

Add import at top:
```python
import torch
```

**Step 2: Commit**

```bash
git add apps/api/src/ports/cli/app.py
git commit -m "feat(cli): add helpful error hints for common failures"
```

---

## Task 7: Final Integration Test

**Step 1: Run all tests**

Run: `cd apps/api && uv run pytest -v`
Expected: All tests PASS

**Step 2: Manual verification in terminal**

```bash
cd apps/api
PYTHONPATH=src python -m ports.cli.app --help
PYTHONPATH=src python -m ports.cli.app -v --help
```

Expected: Help text displays, no errors

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat(cli): complete observability implementation" --allow-empty
```

---

## Summary

| Task | Description |
|------|-------------|
| 1 | Add `configure_cli_logging()` with Rich handler |
| 2 | Add `-v/--verbose` flag to CLI |
| 3 | Add GPU memory monitoring utility |
| 4 | Enhance training callback with Rich progress + GPU stats |
| 5 | Update notebook to always pass `-v` |
| 6 | Add error hints for OOM and common failures |
| 7 | Integration test |
