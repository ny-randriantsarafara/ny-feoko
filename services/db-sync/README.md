# db-sync

Syncs local clip extraction runs to Supabase (metadata + audio clips) and exports corrected data for training or CSV output.

## Setup

From the repo root:

```bash
make install
```

Set environment variables (in `.env` at repo root or exported):

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

## Usage

```bash
./ambara sync -d data/output/20250101_some-run
./ambara export -l some-run -o metadata.corrected.csv
./ambara export-training -l some-run -d data/output/20250101_some-run -o data/training --eval-split 0.1
./ambara dump -o data/backups/dump.sql
./ambara delete-run -l some-run
./ambara reset -y
./ambara cleanup -y
```

## Architecture

- `supabase_client.py`: `get_client()` creates a Supabase client from env
- `sync.py`: `sync_run()` creates a run, uploads clips to storage bucket `clips`, upserts metadata from `metadata.csv`
- `export.py`: `export_corrected()` (CSV), `export_training()` (HuggingFace-style train/test with WAV + metadata.csv)
- `run_resolution.py`: Resolves run by label or UUID; used by export, delete, iterate
- `manage.py`: `delete_run()`, `reset_all()`, `cleanup()`; `dump.py` for SQL backup
- `cli.py`: Typer commands for all operations

## Data Flow

Input: extraction run directory (`metadata.csv` + `clips/*.wav`). Output: Supabase tables (`runs`, `clips`, `clip_edits`), storage bucket objects, or local CSV/dataset. External: Supabase (PostgreSQL + Storage). Reads `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` from env.

## How to Modify

- Add columns: update `CSV_TO_DB_COLUMNS` in `sync.py` and DB schema; update export columns in `export.py`
- New export format: add a function in `export.py` and a CLI command in `cli.py`
- Storage structure: change `sync.py` upload paths; ensure transcript-editor and asr-training paths match
- Run resolution: extend `run_resolution.py` for new lookup strategies (e.g. by source path)
