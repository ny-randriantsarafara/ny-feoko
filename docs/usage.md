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

For the transcript editor, also install Node dependencies:

```bash
cd services/transcript-editor && npm install
```

## Full workflow

```bash
# 1. Download audio from YouTube
./ambara download "https://youtube.com/watch?v=..." -l church-mass-jan

# 2. Extract clean speech clips
./ambara extract -i data/input/church-mass-jan.wav -o data/output/ --device mps -v -l jan-test

# 3. Correct transcripts in the web editor
./ambara editor --dir data/output/20260222_201500_jan-test

# 4. Train (coming soon — services/asr-training/)
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
| `corrected` | `true` after manual review in the editor |
| `status` | `pending`, `corrected`, or `discarded` |

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

## Transcript editor

A web app for correcting draft transcripts. Listen to each clip, fix the text, move on.

### Start the editor

```bash
./ambara editor --dir data/output/20260222_201500_jan-test
# Opens http://localhost:3000
```

### Interface

- **Left sidebar**: all clips, color-coded (grey=pending, green=corrected, red=discarded) with a progress bar
- **Main area**: audio player + text area for editing the transcription

### Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| `Space` | Play / pause audio |
| `Ctrl+Enter` | Save transcription and go to next clip |
| `Ctrl+←` / `Ctrl+→` | Previous / next clip |
| `Ctrl+R` | Replay audio from start |
| `Ctrl+D` | Discard clip (mark as bad, skip for training) |

Every save writes directly back to `metadata.csv`.

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
│   ├── transcript-editor/          # Next.js web UI for correcting transcripts
│   ├── asr-training/               # Whisper fine-tuning (placeholder)
│   └── mt-training/                # NLLB fine-tuning (placeholder)
├── data/
│   ├── input/                      # Downloaded WAV files
│   └── output/                     # Extraction runs (gitignored)
└── docs/                           # You are here
```
