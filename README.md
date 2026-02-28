# Ambara

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/ny-randriantsarafara/ny-feoko/blob/main/notebooks/ambara_colab.ipynb)

Malagasy to French voice translator. Takes Malagasy speech in, gives French speech out.

The name comes from the Malagasy word *mambara* — "to express" or "to declare."

## Why this exists

Malagasy is spoken by 25+ million people but barely supported by existing translation tools. Google Translate handles it poorly. Most speech recognition models have never heard it. This project aims to change that by fine-tuning open-source AI models on real Malagasy audio.

The starting point: hundreds of hours of church recordings in Malagasy, which need to be cleaned up, transcribed, and used to train better models.

## How it works

Three models chained together:

1. **Listener** — OpenAI Whisper (fine-tuned) converts Malagasy speech to text
2. **Translator** — Meta NLLB-200 converts Malagasy text to French
3. **Speaker** — Piper TTS reads the French text aloud

This repo contains the data pipeline and training tools to get there.

## What's in the repo

| Service | What it does |
|---------|-------------|
| `pipeline` | Composite commands: `ingest` (download + extract + sync) and `iterate` (export + train + re-draft) |
| `yt-download` | Downloads YouTube audio as 16kHz mono WAV |
| `clip-extraction` | Splits long recordings into clean 5-30s speech clips, filtering out singing and music |
| `transcript-editor` | Web UI for correcting draft transcripts |
| `db-sync` | Syncs clips to Supabase, exports training data |
| `asr-training` | Whisper fine-tuning on Malagasy + re-drafting |
| `mt-training` | NLLB translation fine-tuning (in progress) |

## Quick start

```bash
# First time setup
make setup

# Ingest: download + extract + sync to Supabase — one command
./ambara ingest "https://youtube.com/watch?v=..." -l my-recording --device mps -v

# Correct the transcripts in the web editor
cd services/transcript-editor && npm install && cd ../..
./ambara editor

# Iterate: export + train + re-draft — one command
./ambara iterate -l my-recording --device mps
```

Repeat `editor` + `iterate` — each round produces better drafts.

## Requirements

- Python 3.14+
- ffmpeg
- Node.js 18+ (for the transcript editor)
- ~6GB RAM for the full extraction pipeline
- Mac with Apple Silicon, or a machine with CUDA GPU

## The data problem

Malagasy is a low-resource language. There's not much training data out there. The approach here:

1. Download audio from YouTube (church services, sermons, talks)
2. Use VAD + audio classification to isolate speech from singing/music
3. Run Whisper for draft transcripts (they're rough — Whisper barely knows Malagasy)
4. Manually correct the transcripts in the web editor
5. Use the corrected data to fine-tune Whisper so it actually understands Malagasy
6. Repeat — each round of fine-tuning produces better drafts, which are faster to correct

The initial focus is on the Merina dialect (spoken in Antananarivo and the central highlands).

## Current status

- [x] Monorepo setup
- [x] YouTube audio downloader
- [x] Clip extraction pipeline (VAD + speech/music classifier + Whisper)
- [x] Transcript correction web UI
- [x] Whisper fine-tuning pipeline
- [ ] NLLB translation fine-tuning
- [ ] End-to-end voice translation
- [ ] Web app for live translation

## Project structure

```
ny-feoko/
├── ambara                     # CLI entry point
├── shared/                    # Shared Python utilities (audio I/O, models)
├── services/
│   ├── yt-download/           # YouTube audio download
│   ├── clip-extraction/       # VAD + classify + transcribe -> clips
│   ├── db-sync/               # Supabase sync and export
│   ├── asr-training/          # Whisper fine-tuning
│   ├── pipeline/              # Ingest and iterate orchestration
│   └── transcript-editor/     # Next.js web UI for transcript correction
├── data/                      # Input, output, training data (gitignored)
├── docs/                      # Architecture and usage documentation
├── notebooks/                 # Colab training notebook
└── scripts/                   # Bible scraping and ingestion
```

## For developers

- [docs/architecture.md](docs/architecture.md) — Full architecture overview, data flow, and configuration
- [docs/usage.md](docs/usage.md) — Detailed usage guide: CLI options, editor shortcuts, threshold tuning
- Each service has its own README with setup, usage, and modification guides:
  - [services/yt-download](services/yt-download/README.md)
  - [services/clip-extraction](services/clip-extraction/README.md)
  - [services/db-sync](services/db-sync/README.md)
  - [services/asr-training](services/asr-training/README.md)
  - [services/pipeline](services/pipeline/README.md)
  - [services/transcript-editor](services/transcript-editor/README.md)

## License

MIT
