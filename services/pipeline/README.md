# pipeline

High-level orchestrator for the ingest and iterate workflows. Composes yt-download, clip-extraction, db-sync, and asr-training into single commands.

## Setup

From the repo root:

```bash
make install
```

Requires all downstream services (yt-download, clip-extraction, db-sync, asr-training) and their dependencies. Supabase env vars for sync/iterate.

## Usage

```bash
./ambara ingest <input_path_or_url> -l <label>
./ambara iterate -l <label>
```

Examples:

```bash
./ambara ingest "https://youtube.com/watch?v=abc" -l church-mass --device mps
./ambara ingest data/input/recording.wav -l session1 -v
./ambara iterate -l church-mass --device cuda --epochs 15
./ambara iterate -l church-mass --push-to-hub user/whisper-mg
```

## Architecture

- `ingest.py`: `ingest()` — download (if URL) → extract → sync. Uses `yt_download`, `clip_extraction`, `db_sync`
- `iterate.py`: `iterate()` — export training data → train Whisper → re-draft pending clips. Uses `db_sync.export`, `asr_training.train`, `asr_training.redraft`
- `cli.py`: Typer commands `ingest` and `iterate`; forwards device, model, and training options

## Data Flow

Ingest: audio file or YouTube URL → WAV (if URL) → extraction run dir → Supabase. Iterate: run label → export dir → training → re-draft in Supabase. External: Supabase, HuggingFace (optional), yt-dlp for URLs. All I/O goes through the underlying services; pipeline only orchestrates.

## How to Modify

- Add pipeline steps: extend `ingest()` or `iterate()`; keep step boundaries clear for timing and error handling
- New composite command: add a module (e.g. `batch_ingest.py`) and a CLI command in `cli.py`; add to `ambara` script
- Change defaults: adjust parameters in `ingest.py` / `iterate.py` or pass through from CLI
- Customize timing output: modify `_print_ingest_summary` and `_print_iterate_summary`
