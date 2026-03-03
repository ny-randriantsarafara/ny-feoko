# Training Service Logging Design

## Overview

Add structured logging to `apps/api/src/application/services/training.py` to provide debug-level observability for all training operations while preserving existing rich console output for interactive use.

## Goals

- Add Python logging to all functions in the training service
- Provide debug-level diagnostics: input shapes, memory usage, detailed timing
- Integrate with existing trace correlation via `TraceContextFilter`
- Keep rich console for human-readable interactive output

## Approach

Direct logging integration (matches existing patterns in `ingest_run.py` and `redraft_clips.py`).

## Design

### Logger Setup

Add module-level logger:

```python
import logging

logger = logging.getLogger(__name__)
```

### Function-level Logging

| Function | INFO | DEBUG |
|----------|------|-------|
| `fine_tune()` | Start (config summary), complete (final metrics) | Model/processor loaded, dataset stats, input shapes, fp16 status, memory, model saved |
| `push_to_hub()` | Start (model_dir, repo_id), complete | Model/processor loaded |
| `redraft_pending()` | Start (clip count, model, device), complete (counts, time) | Per-clip processing, skipped clips |
| `get_transcriptions()` | Start (clip count, model, device), complete (count, time) | Per-clip processing |
| `_load_training_data()` | - | Load start, split sizes, preprocessing timing |
| `_transcribe_clip()` | - | Audio loaded (duration, sample rate), inference timing |

### TrainerCallback

New `LoggingCallback` class for HuggingFace Trainer integration:

```python
from transformers import TrainerCallback

class LoggingCallback(TrainerCallback):
    def on_train_begin(self, args, state, control, **kwargs):
        logger.info("Training started: %d epochs, %d steps",
                    args.num_train_epochs, state.max_steps)

    def on_log(self, args, state, control, logs=None, **kwargs):
        logger.debug("Step %d: %s", state.global_step, logs)

    def on_evaluate(self, args, state, control, metrics=None, **kwargs):
        logger.info("Eval at step %d: WER=%.4f",
                    state.global_step, metrics.get("eval_wer", 0))

    def on_train_end(self, args, state, control, **kwargs):
        logger.info("Training complete: %d steps, best WER=%.4f",
                    state.global_step, state.best_metric or 0)
```

## Files Modified

- `apps/api/src/application/services/training.py`

## What Stays the Same

- `rich.console` for interactive CLI output
- Existing `TraceContextFilter` provides trace correlation
- No changes to function signatures or return values
