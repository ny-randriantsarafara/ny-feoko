# Ambara — Usage Guide

## First-time setup

```bash
# After cloning the repo:
make setup
```

This creates a `.venv`, upgrades pip, and installs all local packages.

If you already have the venv and just need to reinstall packages:

```bash
make install
```

For the web editor, install Node dependencies:

```bash
cd apps/web && npm install
```

## Supabase setup (one-time)

Create your Supabase project and keep these values:

- Project URL
- Anon key
- Service role key

Then run SQL scripts in Supabase SQL editor, in order:

1. `docs/supabase/001_schema.sql`
2. `docs/supabase/002_rls.sql`
3. `docs/supabase/003_storage.sql`

Also create a private storage bucket named `clips` in Supabase Storage.

### Environment variables

Create root `.env` (for Python sync/export):

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
HF_TOKEN=your-huggingface-token
```

`HF_TOKEN` is required on the backend/server side for any web/API job that needs
HuggingFace authentication (for example: pulling private `whisper_hf` models during
ingest, loading private `model_path` repos during redraft, or `push_to_hub` during train).

Create `apps/web/.env.local` (for Next.js editor):

```env
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
API_URL=http://localhost:8000
```

## Quick workflow (recommended)

The main commands for the full cycle:

```bash
# 1. Ingest: download + extract + sync — all in one
./ambara ingest "https://youtube.com/watch?v=..." -l church-mass --device mps

# 2. Correct transcripts in the web editor
./ambara editor

# 3. Export corrected clips as training data
./ambara export --run-id <uuid>

# 4. Train Whisper on the corrected clips
./ambara train -d data/output/<dataset> --device mps

# 5. Re-draft pending clips with the improved model
./ambara redraft --run-id <uuid> --model models/whisper-mg-v1/model --device mps
```

Then repeat steps 2-5. Each iteration produces better drafts, making corrections faster.

`ingest` accepts a YouTube URL (downloads automatically) or a local file path:

```bash
./ambara ingest data/input/recording.wav -l session1 --device mps
```

For Colab training with GPU, use `--push-to-hub` to save the model:

```bash
./ambara train -d data/output/<dataset> --device cuda --push-to-hub user/whisper-mg
```

## Full workflow (individual steps)

If you need more control, you can run each step separately:

```bash
# 1. Ingest downloads, extracts, and syncs automatically
./ambara ingest "https://youtube.com/watch?v=..." -l church-mass-jan --device mps

# 2. Open transcript editor and label clips
./ambara editor
# Opens http://localhost:3000

# 3. Export corrected clips for training (by run ID)
./ambara export --run-id <run-uuid>

# 4. Train Whisper on the exported dataset
./ambara train -d data/output/<dataset> --device mps

# 5. Re-draft pending clips with the fine-tuned model
./ambara redraft --run-id <run-uuid> --model models/whisper-mg-v1/model --device mps
```

## Ingest pipeline details

The `ingest` command runs the full extraction pipeline:

```
Input WAV (any format, any length) or YouTube URL
  |
  v  Download (if URL)
  |
  v  Chunked reading (300s chunks via ffmpeg, ~19MB RAM each)
  |
  v  Silero VAD — detects where speech exists
  |
  v  Segment grouping — merges adjacent speech into 5-30s clips
  |
  v  AST classifier — separates speech from singing/music
  |
  v  Whisper small — generates draft Malagasy transcripts
  |
  v  Output: clips/*.wav + metadata.csv
  |
  v  Sync to Supabase
```

### Output structure

Each run gets a timestamped directory:

```
data/output/
├── 20260222_201500_whisper-small/
│   ├── clips/
│   │   ├── clip_00001.wav    # 16kHz mono, 5-30 seconds
│   │   ├── clip_00002.wav
│   │   └── ...
│   └── metadata.csv
├── 20260222_203000_hf-mg-v2/
│   ├── clips/
│   └── metadata.csv
```

Use `--label` / `-l` to name runs for easy comparison.

### Tuning thresholds

**Too many singing/music clips getting through?** Raise the speech threshold:

```bash
./ambara ingest audio.wav -l test --device mps --speech-threshold 0.5
```

**Dropping valid quiet speech?** Lower VAD sensitivity:

```bash
./ambara ingest audio.wav -l test --device mps --vad-threshold 0.25
```

### Using HuggingFace fine-tuned models

Instead of stock Whisper, use a fine-tuned model:

```bash
./ambara ingest audio.wav -l test --device mps \
    --whisper-hf "username/whisper-small-malagasy"
```

The `--whisper-hf` flag takes a HuggingFace model ID and overrides `--whisper-model`.

## Whisper fine-tuning

The training pipeline takes corrected clips from Supabase, fine-tunes Whisper, and uses the trained model to improve drafts for remaining clips.

```
Corrected clips in Supabase
  |
  v  export — downloads WAVs + writes metadata
  |
  v  data/output/<dataset>/  (HuggingFace audiofolder format)
  |
  v  train — fine-tunes Whisper small with Seq2SeqTrainer
  |
  v  models/whisper-mg-v1/model/  (saved model + processor)
  |
  v  redraft — re-transcribes pending clips, updates Supabase
  |
  v  Editor — pending clips now have better drafts to correct
```

### Step 1: Export training data

Export corrected clips as a HuggingFace-compatible dataset:

```bash
./ambara export --run-id <run-uuid>
```

This downloads WAV files from Supabase Storage and writes `metadata.csv` (with `file_name` and `transcription` columns) into `data/output/<date>/`, split into `train/` and `test/` subdirectories.

Options:

| Flag | Default | Description |
|------|---------|-------------|
| `--run-id` | — | Run UUID(s) to export (can specify multiple) |
| `--output` / `-o` | `data/output` | Parent directory for the dataset |
| `--eval-split` | `0.1` | Fraction of clips for evaluation (0.0-0.5) |

### Step 2: Train

Fine-tune Whisper on the exported dataset:

```bash
./ambara train -d data/output/<dataset> --device mps
```

The model and processor are saved to `models/whisper-mg-v1/model/` by default.

Options:

| Flag | Default | Description |
|------|---------|-------------|
| `--data-dir` / `-d` | — | Path to exported dataset |
| `--output-dir` / `-o` | `models/whisper-mg-v1` | Where to save the model |
| `--device` | `auto` | `auto`, `mps`, `cuda`, or `cpu` |
| `--base-model` | `openai/whisper-small` | HuggingFace model to fine-tune |
| `--epochs` | `10` | Training epochs |
| `--batch-size` | `4` | Per-device batch size |
| `--lr` | `1e-5` | Learning rate |
| `--push-to-hub` | — | HuggingFace repo ID to push to |

### Step 3: Re-draft pending clips

Use the fine-tuned model to re-transcribe pending clips:

```bash
./ambara redraft --run-id <run-uuid> --model models/whisper-mg-v1/model --device mps
```

This updates `draft_transcription` in Supabase for all clips with `status = 'pending'`. The corrected clips and their transcriptions are left untouched.

### Step 4: Continue correcting

Open the editor and correct the remaining clips. The drafts will be better now:

```bash
./ambara editor
```

### Device notes

- **Apple Silicon (MPS)**: works out of the box. Training ~100 clips takes a few hours. fp16 is disabled (not supported on MPS).
- **CUDA GPU**: faster. fp16 is enabled automatically. Use `--device cuda`.
- **CPU**: slowest, but works anywhere. Use `--device cpu`.

### Tuning training

For small datasets (~100 clips), the defaults work well. If you have more data or want to experiment:

- Lower `--lr` (e.g. `5e-6`) if training loss is unstable
- Increase `--epochs` if the model hasn't converged
- Increase `--batch-size` if you have enough GPU memory

### Training on Google Colab

For faster training with a free GPU, use the Colab notebook:

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ny-randriantsarafara/ny-feoko/blob/main/notebooks/ambara_colab.ipynb)

The notebook is fully automated — edit the config cell at the top, then **Runtime > Run All**.

**How it works:**

- Clips are downloaded from Supabase Storage automatically — no manual uploads
- Trained models are pushed to HuggingFace Hub — no Google Drive needed for data
- Google Drive is only used for the `.env` file (Supabase credentials)

**Before your first run:**

1. Place your `.env` file at `My Drive/ambara/.env` (with `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`)
2. Create a [HuggingFace write token](https://huggingface.co/settings/tokens) and set `HF_TOKEN` in the config cell
3. Ingest your audio locally first (`./ambara ingest ...`) so clips are in Supabase

For web/API-triggered jobs (not notebook CLI runs), set `HF_TOKEN` in the backend
environment so the server can access private HuggingFace models and push-to-hub.

**Typical Colab workflow:**

1. Set `TRAIN_RUN_IDS` to your run UUIDs and `TRAIN_PUSH_TO_HUB` to your HF repo
2. Runtime > Run All
3. The notebook exports corrected clips, trains Whisper, and re-drafts pending clips
4. Open the editor locally, correct the improved drafts, and repeat

**Using the cloud-trained model locally:**

After training on Colab, use the HuggingFace repo ID directly:

```bash
./ambara ingest data/input/new-audio.wav -l new-session --device mps --whisper-hf user/whisper-mg
```

## Database management

### Delete a run

Remove a single run and all its clips, edit history, and storage files:

```bash
# By UUID
./ambara delete-run --run-id <run-uuid>

# Skip confirmation
./ambara delete-run --run-id <run-uuid> --yes
```

Shows clip count and corrected count before confirming.

### Purge API cache

Clear API in-memory model cache and Python bytecode cache files under `apps/api/`:

```bash
./ambara purge-api-cache
```

Use this when you want the next ingest request to reload ML models from scratch, or to clean stale `__pycache__`/`.pyc` files in the API package.

## Transcript editor (Supabase)

A web app for correcting draft transcripts from Supabase.

### Start the editor

```bash
./ambara editor
# Opens http://localhost:3000
```

### Auth flow

1. Open `/login`
2. Enter your email
3. Use magic link from inbox
4. Select a run in the run list page
5. Correct clips in `/runs/[runId]`

### Interface

- **Run list**: shows all runs with correction progress
- **Left sidebar**: clips in the selected run, color-coded by status
- **Main area**: audio player, Whisper draft reference, corrected transcription editor

### Keyboard shortcuts

Shortcuts are displayed based on your platform. On macOS, use the Command key (⌘); on other platforms, use Ctrl.

| Action | macOS | Windows/Linux |
|--------|-------|---------------|
| Play / pause audio | `Space` | `Space` |
| Save transcription and go to next clip | `⌘Enter` | `Ctrl+Enter` |
| Previous / next clip | `⌘←` / `⌘→` | `Ctrl+←` / `Ctrl+→` |
| Replay audio from start | `⌘R` | `Ctrl+R` |
| Discard clip (mark as bad, skip for training) | `⌘D` | `Ctrl+D` |

## Project structure

```
ny-feoko/
├── ambara                          # CLI wrapper script
├── Makefile                        # setup, install, lint, test
├── apps/
│   ├── api/                        # Python backend (CLI + REST API)
│   │   └── src/
│   │       ├── domain/             # Entities, ports, exceptions
│   │       ├── application/        # Use cases and services
│   │       ├── infra/              # Supabase repos, ML clients
│   │       └── ports/              # CLI and REST entry points
│   └── web/                        # Next.js frontend
│       └── src/
│           ├── app/                # Pages: runs, editor, ingest, training
│           ├── components/         # UI components
│           ├── hooks/              # React hooks
│           └── lib/                # Utilities
├── data/
│   ├── input/                      # Downloaded WAV files
│   └── output/                     # Extraction runs and training datasets (gitignored)
├── models/                         # Saved fine-tuned models (gitignored)
├── notebooks/                      # Colab notebooks for GPU training
└── docs/
    ├── architecture.md             # System design overview
    ├── usage.md                    # You are here
    └── supabase/                   # SQL setup scripts
```
