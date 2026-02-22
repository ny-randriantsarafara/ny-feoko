# Ambara

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
| `yt-download` | Downloads YouTube audio as 16kHz mono WAV |
| `clip-extraction` | Splits long recordings into clean 5-30s speech clips, filtering out singing and music |
| `transcript-editor` | Web UI for correcting draft transcripts |
| `asr-training` | Whisper fine-tuning on Malagasy (in progress) |
| `mt-training` | NLLB translation fine-tuning (in progress) |

## Quick start

```bash
# First time setup
make setup

# Download a YouTube video
./ambara download "https://youtube.com/watch?v=..." -l my-recording

# Extract speech clips from it
./ambara extract -i data/input/my-recording.wav -o data/output/ --device mps -v

# Correct the transcripts
cd services/transcript-editor && npm install && cd ../..
./ambara editor --dir data/output/20260222_201500_my-recording
```

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
- [ ] Whisper fine-tuning pipeline
- [ ] NLLB translation fine-tuning
- [ ] End-to-end voice translation
- [ ] Web app for live translation

## Project structure

```
ny-feoko/
├── ambara                 # CLI entry point for everything
├── shared/                # Shared Python utilities
├── services/
│   ├── yt-download/       # YouTube → WAV
│   ├── clip-extraction/   # Long audio → clean speech clips
│   ├── transcript-editor/ # Next.js app for correcting transcripts
│   ├── asr-training/      # Whisper fine-tuning (placeholder)
│   └── mt-training/       # NLLB fine-tuning (placeholder)
├── data/
│   ├── input/             # Downloaded WAV files
│   └── output/            # Extracted clips + metadata
└── docs/
    └── usage.md           # Detailed usage guide
```

## Docs

See [docs/usage.md](docs/usage.md) for the full guide — all CLI options, keyboard shortcuts for the editor, threshold tuning, and how to use HuggingFace models.

## License

MIT
