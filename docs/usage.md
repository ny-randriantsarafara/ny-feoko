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

For the transcript editor, install Node dependencies:

```bash
cd services/transcript-editor && npm install
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
```

Create `services/transcript-editor/.env.local` (for Next.js editor):

```env
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

## Quick workflow (recommended)

Three commands for the full cycle:

```bash
# 1. Ingest: download + extract + sync — all in one
./ambara ingest "https://youtube.com/watch?v=..." -l church-mass --device mps -v

# 2. Correct transcripts in the web editor
./ambara editor

# 3. Iterate: export + train + re-draft — all in one
./ambara iterate -l church-mass --device mps
```

Then repeat steps 2-3. Each iteration produces better drafts, making corrections faster.

`ingest` accepts a YouTube URL (downloads automatically) or a local file path:

```bash
./ambara ingest data/input/recording.wav -l session1 --device mps
```

For Colab training with GPU, use `--push-to-hub` to save the model:

```bash
./ambara iterate -l church-mass --device cuda --push-to-hub user/whisper-mg
```

## Full workflow (individual steps)

If you need more control, you can run each step separately:

```bash
# 1. Download audio from YouTube
./ambara download "https://youtube.com/watch?v=..." -l church-mass-jan

# 2. Extract clean speech clips (+ metadata.csv)
./ambara extract -i data/input/church-mass-jan.wav -o data/output/ --device mps -v -l jan-test

# 3. Sync run to Supabase (creates run, uploads clips, upserts metadata)
./ambara sync --dir data/output/20260222_201500_jan-test

# 4. Open transcript editor and label clips
./ambara editor
# Opens http://localhost:3000

# 5. Export corrected clips for training
./ambara export --label 20260222_201500_jan-test -o metadata.corrected.csv
```

## YouTube downloader

```bash
# Download and convert to 16kHz mono WAV
./ambara download "https://youtube.com/watch?v=..." -l church-mass

# Without label (uses video title as filename)
./ambara download "https://youtube.com/watch?v=..."
```

Output goes to `data/input/<label>.wav`.

## Clip extraction pipeline

### Quick start

```bash
# Fast VAD-only pass (no GPU models, just detects speech regions)
./ambara vad-only --input test.wav --output data/vad_segments.json

# Full pipeline (VAD → classify → transcribe → write clips)
./ambara extract --input test.wav --output data/output/ --device mps -v
```

### What the full pipeline does

```
Input WAV (any format, any length)
  │
  ▼  Chunked reading (300s chunks via ffmpeg, ~19MB RAM each)
  │
  ▼  Silero VAD — detects where speech exists
  │
  ▼  Segment grouping — merges adjacent speech into 5-30s clips
  │
  ▼  AST classifier — separates speech from singing/music
  │
  ▼  Whisper small — generates draft Malagasy transcripts
  │
  ▼  Output: clips/*.wav + metadata.csv
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

### metadata.csv columns

| Column | Description |
|--------|-------------|
| `file_name` | Relative path to the clip WAV |
| `source_file` | Original input file |
| `start_sec` | Start time in the original file |
| `end_sec` | End time in the original file |
| `duration_sec` | Clip duration |
| `speech_score` | Classifier confidence that this is speech (0-1) |
| `music_score` | Classifier confidence that this is music/singing (0-1) |
| `transcription` | Whisper's draft transcript (needs manual correction) |
| `whisper_avg_logprob` | Whisper confidence (higher = more confident) |
| `whisper_no_speech_prob` | Probability that the clip has no speech |
| `whisper_rejected` | `True` if Whisper itself wasn't confident |
| `corrected` | Legacy local-editor field (kept for compatibility) |
| `status` | Legacy local-editor field (kept for compatibility) |

## Using HuggingFace fine-tuned models

Instead of stock Whisper, you can test any community fine-tuned model from HuggingFace:

```bash
./ambara extract --input test.wav --output data/output/ --device mps \
    --whisper-hf "username/whisper-small-malagasy"
```

The `--whisper-hf` flag takes a HuggingFace model ID and overrides `--whisper-model`. The model is downloaded and cached automatically on first use. No authentication needed for public models.

## Tuning thresholds

### Too many singing/music clips getting through?

Raise the speech threshold:

```bash
./ambara extract --input test.wav --output data/output/ --device mps --speech-threshold 0.5
```

### Dropping valid quiet speech (prayers, soft-spoken segments)?

Lower VAD sensitivity:

```bash
./ambara extract --input test.wav --output data/output/ --device mps --vad-threshold 0.25
```

### All available options

```bash
./ambara extract --help
./ambara vad-only --help
```

## Supabase sync and export

### Sync an extraction run

```bash
./ambara sync --dir data/output/20260222_201500_jan-test
```

What it does:

1. Creates a `runs` row in Supabase
2. Uploads `clips/*.wav` to Storage (`clips/<run_id>/clips/*.wav`)
3. Upserts `metadata.csv` into `clips` table using `(run_id, file_name)` uniqueness
4. Preserves existing corrections when re-syncing

### Export corrected clips

By run ID:

```bash
./ambara export --run <run-uuid> -o metadata.corrected.csv
```

By run label:

```bash
./ambara export --label 20260222_201500_jan-test -o metadata.corrected.csv
```

Exports only `status = corrected`.

## Whisper fine-tuning

The training pipeline takes corrected clips from Supabase, fine-tunes Whisper, and uses the trained model to improve drafts for remaining clips.

```
Corrected clips in Supabase
  │
  ▼  export-training — copies WAVs + writes metadata.csv
  │
  ▼  data/training/<dataset>/  (HuggingFace audiofolder format)
  │
  ▼  train — fine-tunes Whisper small with Seq2SeqTrainer
  │
  ▼  models/whisper-mg-v1/model/  (saved model + processor)
  │
  ▼  re-draft — re-transcribes pending clips, updates Supabase
  │
  ▼  Editor — pending clips now have better drafts to correct
```

### Step 1: Export training data

Export corrected clips as a HuggingFace-compatible dataset:

```bash
./ambara export-training --label <run-label> -d data/output/<run-dir>
```

This copies WAV files and writes `metadata.csv` (with `file_name` and `transcription` columns) into `data/training/<date>_<label>/`, split into `train/` and `test/` subdirectories.

Options:

| Flag | Default | Description |
|------|---------|-------------|
| `--label` / `-l` | — | Run label in Supabase |
| `--run` | — | Run UUID (alternative to label) |
| `--source-dir` / `-d` | — | Local directory with `clips/` |
| `--output` / `-o` | `data/training` | Parent directory for the dataset |
| `--eval-split` | `0.1` | Fraction of clips for evaluation (0.0-0.5) |

### Step 2: Train

Fine-tune Whisper on the exported dataset:

```bash
./ambara train --data-dir data/training/<dataset> --device mps
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
./ambara re-draft --model models/whisper-mg-v1/model \
    -d data/output/<run-dir> --label <run-label>
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

**Typical Colab workflow:**

1. Set `ITERATE_LABEL` to your run label and `ITERATE_PUSH_TO_HUB` to your HF repo
2. Runtime > Run All
3. The notebook exports corrected clips, trains Whisper, and re-drafts pending clips
4. Open the editor locally, correct the improved drafts, and repeat

**Using the cloud-trained model locally:**

After training on Colab, use the HuggingFace repo ID directly:

```bash
./ambara iterate -l my-label --device mps
```

Or in extraction:

```bash
./ambara ingest data/input/new-audio.wav -l new-session --device mps --whisper-hf user/whisper-mg
```

### Using your fine-tuned model in extraction

The trained model works with the existing extraction pipeline:

```bash
./ambara extract --input new-audio.wav --output data/output/ --device mps \
    --whisper-hf models/whisper-mg-v1/model
```

For a model hosted on HuggingFace Hub:

```bash
./ambara extract --input new-audio.wav --output data/output/ --device mps \
    --whisper-hf your-username/whisper-small-malagasy
```

## Database management

### Delete a run

Remove a single run and all its clips, edit history, and storage files:

```bash
# By label
./ambara delete-run --label 20260222_201500_jan-test

# By UUID
./ambara delete-run --run <run-uuid>

# Skip confirmation
./ambara delete-run --label 20260222_201500_jan-test --yes
```

Shows clip count and corrected count before confirming.

### Reset everything

Wipe all runs, clips, edits, and storage objects. Irreversible:

```bash
./ambara reset
```

Prints totals (runs, clips, edits) and asks for confirmation. Pass `--yes` to skip:

```bash
./ambara reset --yes
```

### Clean up orphans

Find and remove orphaned data:

- **Empty runs**: runs with zero clips (e.g. sync was interrupted)
- **Orphan storage**: storage prefixes with no matching run in the database

```bash
./ambara cleanup

# Skip confirmation
./ambara cleanup --yes
```

Prints what it found before asking to proceed.

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
├── shared/                         # Shared models and audio utilities
│   └── ny_feoko_shared/
│       ├── audio_io.py             # ffmpeg chunked reader
│       └── models.py               # AudioSegment, ClipCandidate, ClipResult
├── services/
│   ├── yt-download/                # YouTube audio downloader
│   ├── clip-extraction/            # VAD + classifier + Whisper pipeline
│   ├── db-sync/                    # Supabase sync/export service
│   ├── transcript-editor/          # Next.js web UI for correcting transcripts
│   ├── asr-training/               # Whisper fine-tuning pipeline
│   └── mt-training/                # NLLB fine-tuning (placeholder)
├── data/
│   ├── input/                      # Downloaded WAV files
│   ├── output/                     # Extraction runs (gitignored)
│   └── training/                   # Exported training datasets (gitignored)
├── models/                         # Saved fine-tuned models (gitignored)
└── docs/
    ├── usage.md                    # You are here
    └── supabase/                   # SQL setup scripts
```
