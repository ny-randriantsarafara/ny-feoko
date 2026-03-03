# CLI Observability for Colab

## Problem

When CLI commands fail in Colab notebooks, errors are hidden behind generic `CalledProcessError`. Existing logging (`logger.info/debug`) isn't configured for CLI, making debugging difficult.

## Solution

Add verbose logging with Rich progress bars to all CLI commands. Notebook always runs in debug mode.

## User Experience

### Colab output (verbose by default)

```
$ python -m ports.cli.app train -d data/output -v

[12:34:56] INFO     Starting training: model=openai/whisper-medium, epochs=10
[12:34:57] INFO     GPU: Tesla T4, VRAM: 1.2GB / 15.0GB (8%)
[12:34:58] INFO     Dataset loaded: train=450 samples, test=50 samples

Training ━━━━━━━━━━━━━━━━━━━━ 100/500 steps  20%  loss=0.342  wer=0.45  VRAM=8.2GB
```

### On error (always visible)

```
[12:35:02] ERROR    CUDA out of memory. Tried to allocate 512 MiB...
           ERROR    Suggestion: Reduce --batch-size to 1 or 2 for whisper-medium
```

## Components

1. **CLI flag**: `--verbose/-v` on all commands
   - Default: INFO level
   - Verbose: DEBUG level

2. **Rich logging handler**: Console output with timestamps and colors

3. **Rich progress bar**: For training steps showing:
   - Step count and percentage
   - Loss and WER metrics
   - VRAM usage (every 50 steps)

4. **GPU reporter**: Log VRAM at start + periodically during training

5. **Error hints**: Catch common errors (OOM, missing files) and suggest fixes

6. **Notebook default**: `run_cli()` helper always passes `-v` flag

## Files to Modify

| File | Change |
|------|--------|
| `ports/cli/app.py` | Add `-v` callback, configure logging at startup |
| `application/services/training.py` | Enhance `LoggingCallback` with Rich progress + GPU stats |
| `infra/telemetry/logging.py` | Add `configure_cli_logging()` for Rich console output |
| `notebooks/ambara_steps.ipynb` | Update `run_cli()` to always pass `-v` |

## What Stays the Same

- Existing `logger.info/debug` calls throughout codebase
- No new dependencies (Rich already installed)
- CLI interface (just adds optional flag)
