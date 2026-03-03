# Training Service Logging Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add structured logging with debug-level diagnostics to the training service while preserving rich console output.

**Architecture:** Direct logging integration using Python's logging module with a module-level logger. Add a TrainerCallback for HuggingFace Trainer integration. Logs inherit trace correlation from existing `TraceContextFilter`.

**Tech Stack:** Python logging, HuggingFace transformers TrainerCallback, torch (for memory stats)

---

### Task 1: Add Logger Setup and Imports

**Files:**
- Modify: `apps/api/src/application/services/training.py:1-19`

**Step 1: Add logging import and logger**

Add after line 4 (`from __future__ import annotations`):

```python
import logging
import time
```

Add after line 19 (`console = Console()`):

```python
logger = logging.getLogger(__name__)
```

**Step 2: Verify no syntax errors**

Run: `python -m py_compile apps/api/src/application/services/training.py`
Expected: No output (success)

**Step 3: Commit**

```bash
git add apps/api/src/application/services/training.py
git commit -m "feat(training): add logger setup"
```

---

### Task 2: Add LoggingCallback Class

**Files:**
- Modify: `apps/api/src/application/services/training.py`

**Step 1: Add TrainerCallback import**

Update the transformers import to include TrainerCallback:

```python
from transformers import (
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
    TrainerCallback,
    WhisperForConditionalGeneration,
    WhisperProcessor,
)
```

**Step 2: Add LoggingCallback class after TrainingConfig**

Add after the `TrainingConfig` class (after line 44):

```python
class LoggingCallback(TrainerCallback):
    """Emit structured logs during training for observability."""

    def on_train_begin(self, args, state, control, **kwargs):
        logger.info(
            "Training started: %d epochs, %d total steps",
            args.num_train_epochs,
            state.max_steps,
        )

    def on_log(self, args, state, control, logs=None, **kwargs):
        if logs:
            logger.debug("Step %d: %s", state.global_step, logs)

    def on_evaluate(self, args, state, control, metrics=None, **kwargs):
        if metrics:
            wer = metrics.get("eval_wer", 0)
            logger.info("Eval at step %d: WER=%.4f", state.global_step, wer)

    def on_train_end(self, args, state, control, **kwargs):
        logger.info(
            "Training complete: %d steps, best WER=%.4f",
            state.global_step,
            state.best_metric or 0,
        )
```

**Step 3: Verify no syntax errors**

Run: `python -m py_compile apps/api/src/application/services/training.py`
Expected: No output (success)

**Step 4: Commit**

```bash
git add apps/api/src/application/services/training.py
git commit -m "feat(training): add LoggingCallback for trainer integration"
```

---

### Task 3: Add Logging to fine_tune()

**Files:**
- Modify: `apps/api/src/application/services/training.py` (fine_tune function)

**Step 1: Add logging at function start**

At the beginning of `fine_tune()` (after the docstring):

```python
    logger.info(
        "Fine-tuning started: model=%s, epochs=%d, batch_size=%d, device=%s",
        config.base_model,
        config.epochs,
        config.batch_size,
        device,
    )
    start_time = time.perf_counter()
```

**Step 2: Add logging after model load**

After loading model and processor (after `model.generation_config.forced_decoder_ids = None`):

```python
    logger.debug("Model and processor loaded from %s", config.base_model)
    if device.startswith("cuda") and torch.cuda.is_available():
        logger.debug(
            "GPU memory allocated: %.2f MB",
            torch.cuda.memory_allocated() / 1024 / 1024,
        )
```

**Step 3: Add logging after dataset load**

After `dataset = _load_training_data(...)`:

```python
    logger.debug(
        "Dataset loaded: train=%d samples, test=%d samples",
        len(dataset["train"]),
        len(dataset["test"]),
    )
```

**Step 4: Add logging for training config**

After creating `training_args`:

```python
    logger.debug("Training config: fp16=%s, use_cpu=%s", use_fp16, device == "cpu")
```

**Step 5: Register LoggingCallback with trainer**

Modify the `Seq2SeqTrainer` instantiation to include callbacks:

```python
    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset["train"],
        eval_dataset=dataset["test"],
        data_collator=collator,
        compute_metrics=compute_metrics,
        processing_class=processor.feature_extractor,
        callbacks=[LoggingCallback()],
    )
```

**Step 6: Add logging at function end**

After saving the model (before `return model_dir`):

```python
    elapsed = time.perf_counter() - start_time
    logger.info("Fine-tuning complete in %.2fs, model saved to %s", elapsed, model_dir)
    logger.debug("Model and processor saved to %s", model_dir)
```

**Step 7: Verify no syntax errors**

Run: `python -m py_compile apps/api/src/application/services/training.py`
Expected: No output (success)

**Step 8: Commit**

```bash
git add apps/api/src/application/services/training.py
git commit -m "feat(training): add logging to fine_tune()"
```

---

### Task 4: Add Logging to push_to_hub()

**Files:**
- Modify: `apps/api/src/application/services/training.py` (push_to_hub function)

**Step 1: Add logging to push_to_hub**

Replace the function body:

```python
def push_to_hub(model_dir: Path, repo_id: str) -> None:
    """Push a saved model and processor to HuggingFace Hub."""
    logger.info("Pushing model to HuggingFace Hub: %s -> %s", model_dir, repo_id)
    processor = WhisperProcessor.from_pretrained(str(model_dir))
    model = WhisperForConditionalGeneration.from_pretrained(str(model_dir))
    logger.debug("Model and processor loaded from %s", model_dir)
    processor.push_to_hub(repo_id)
    model.push_to_hub(repo_id)
    logger.info("Push complete: %s", repo_id)
```

**Step 2: Verify no syntax errors**

Run: `python -m py_compile apps/api/src/application/services/training.py`
Expected: No output (success)

**Step 3: Commit**

```bash
git add apps/api/src/application/services/training.py
git commit -m "feat(training): add logging to push_to_hub()"
```

---

### Task 5: Add Logging to redraft_pending()

**Files:**
- Modify: `apps/api/src/application/services/training.py` (redraft_pending function)

**Step 1: Add logging at function start**

At the beginning of `redraft_pending()` (after the docstring):

```python
    logger.info(
        "Redraft started: %d clips, model=%s, device=%s",
        len(pending_clips),
        model_path,
        device,
    )
    start_time = time.perf_counter()
```

**Step 2: Add logging after model load**

After `model.to(device).eval()`:

```python
    logger.debug("Model loaded and moved to %s", device)
```

**Step 3: Add logging for skipped clips**

Inside the loop, when a clip is skipped:

```python
        if not wav_path.exists():
            logger.debug("Skipped missing file: %s", wav_path)
            skipped += 1
            continue
```

**Step 4: Add logging for processed clips**

After processing each clip (after `updated += 1`):

```python
        logger.debug("Processed clip %s: %d chars", file_name, len(text))
```

**Step 5: Add logging at function end**

Before `return updated, skipped`:

```python
    elapsed = time.perf_counter() - start_time
    logger.info(
        "Redraft complete in %.2fs: %d updated, %d skipped",
        elapsed,
        updated,
        skipped,
    )
```

**Step 6: Verify no syntax errors**

Run: `python -m py_compile apps/api/src/application/services/training.py`
Expected: No output (success)

**Step 7: Commit**

```bash
git add apps/api/src/application/services/training.py
git commit -m "feat(training): add logging to redraft_pending()"
```

---

### Task 6: Add Logging to get_transcriptions()

**Files:**
- Modify: `apps/api/src/application/services/training.py` (get_transcriptions function)

**Step 1: Add logging at function start**

At the beginning of `get_transcriptions()` (after the docstring):

```python
    logger.info(
        "Transcription started: %d clips, model=%s, device=%s",
        len(pending_clips),
        model_path,
        device,
    )
    start_time = time.perf_counter()
```

**Step 2: Add logging after model load**

After `model.to(device).eval()`:

```python
    logger.debug("Model loaded and moved to %s", device)
```

**Step 3: Add logging for skipped and processed clips**

Inside the loop:

```python
        if not wav_path.exists():
            logger.debug("Skipped missing file: %s", wav_path)
            continue
        text = _transcribe_clip(wav_path, processor, model, device, forced_decoder_ids)
        logger.debug("Transcribed clip %s: %d chars", clip["file_name"], len(text))
        results.append((clip["id"], text))
```

**Step 4: Add logging at function end**

Before `return results`:

```python
    elapsed = time.perf_counter() - start_time
    logger.info(
        "Transcription complete in %.2fs: %d clips processed",
        elapsed,
        len(results),
    )
```

**Step 5: Verify no syntax errors**

Run: `python -m py_compile apps/api/src/application/services/training.py`
Expected: No output (success)

**Step 6: Commit**

```bash
git add apps/api/src/application/services/training.py
git commit -m "feat(training): add logging to get_transcriptions()"
```

---

### Task 7: Add Logging to _load_training_data()

**Files:**
- Modify: `apps/api/src/application/services/training.py` (_load_training_data function)

**Step 1: Add logging at function start**

At the beginning of `_load_training_data()`:

```python
    logger.debug("Loading training data from %s", data_dir)
    load_start = time.perf_counter()
```

**Step 2: Add logging after dataset load**

After loading and splitting the dataset (after the `if "test" not in ds` block):

```python
    logger.debug(
        "Dataset split: train=%d, test=%d",
        len(ds["train"]),
        len(ds["test"]),
    )
```

**Step 3: Add logging at function end**

Before `return ds`:

```python
    elapsed = time.perf_counter() - load_start
    logger.debug("Dataset preprocessing complete in %.2fs", elapsed)
```

**Step 4: Verify no syntax errors**

Run: `python -m py_compile apps/api/src/application/services/training.py`
Expected: No output (success)

**Step 5: Commit**

```bash
git add apps/api/src/application/services/training.py
git commit -m "feat(training): add logging to _load_training_data()"
```

---

### Task 8: Add Logging to _transcribe_clip()

**Files:**
- Modify: `apps/api/src/application/services/training.py` (_transcribe_clip function)

**Step 1: Add logging after audio load**

After loading audio (after the sample rate check):

```python
    duration = len(audio) / sr
    logger.debug("Audio loaded: %s, duration=%.2fs, sr=%d", wav_path.name, duration, sr)
    inference_start = time.perf_counter()
```

**Step 2: Add logging after inference**

After the `with torch.no_grad()` block, before the return:

```python
    inference_time = time.perf_counter() - inference_start
    logger.debug("Inference complete in %.3fs", inference_time)
```

**Step 3: Verify no syntax errors**

Run: `python -m py_compile apps/api/src/application/services/training.py`
Expected: No output (success)

**Step 4: Commit**

```bash
git add apps/api/src/application/services/training.py
git commit -m "feat(training): add logging to _transcribe_clip()"
```

---

### Task 9: Run Tests and Final Verification

**Files:**
- Test: `apps/api/tests/application/test_use_cases.py`

**Step 1: Run existing tests**

Run: `cd apps/api && python -m pytest tests/ -v --tb=short`
Expected: All tests pass

**Step 2: Verify logging works with a quick import test**

Run: `cd apps/api && python -c "from application.services.training import logger; print('Logger:', logger.name)"`
Expected: `Logger: application.services.training`

**Step 3: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "feat(training): complete logging implementation"
```

---

## Summary

This plan adds structured logging to all functions in `training.py`:
- Module-level logger with trace correlation
- LoggingCallback for HuggingFace Trainer
- INFO logs for operation start/end with key metrics
- DEBUG logs for detailed diagnostics (memory, timing, per-clip)
- Preserves existing rich console output
