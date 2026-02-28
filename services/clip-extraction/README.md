# clip-extraction

Turns long audio into 5–30 second speech clips using VAD (Silero), speech vs music classification (ASTClassifier), and transcription (Whisper). Produces WAV clips and `metadata.csv` for downstream correction and training.

## Setup

From the repo root:

```bash
make install
```

Requires: `ffmpeg`, PyTorch, Silero VAD, openai-whisper or transformers for Whisper. Device is chosen via `--device` (mps, cuda, cpu).

## Usage

```bash
./ambara extract -i <input.wav> -o data/output
./ambara vad-only -i <input.wav> -o data/vad_segments.json
```

Examples:

```bash
./ambara extract -i data/input/recording.wav -o data/output --whisper-model small --device mps -v
./ambara extract -i data/input/recording.wav --whisper-hf username/whisper-small-mg
./ambara vad-only -i data/input/recording.wav -o vad_output.json
```

Key options: `--whisper-model`, `--whisper-hf`, `--vad-threshold`, `--speech-threshold`, `--chunk-duration`, `--device`, `--label`.

## Architecture

- `domain/ports.py`: Abstract ports—`VADPort`, `ClassifierPort`, `TranscriberPort`—define the pipeline interface
- `domain/segment_grouping.py`: `group_segments()` merges adjacent VAD segments into 5–30s clip candidates (min_duration, max_duration, max_gap)
- `pipeline.py`: Orchestrates chunk → VAD → group → classify → transcribe → write; `run_pipeline()` and `run_vad_only()`
- `infrastructure/`: Silero VAD, ASTClassifier, WhisperTranscriber / HuggingFaceTranscriber, ClipWriter
- `cli.py`: Typer commands `run` and `vad-only`

## Data Flow

Input: WAV/MP3 (or any ffmpeg-readable) file. Output: timestamped run dir under `data/output` with `clips/*.wav` and `metadata.csv`. Uses `ny_feoko_shared.audio_io.stream_chunks` for chunked streaming, `models.ClipCandidate` and `ClipResult` for pipeline data. No external APIs except model downloads.

## How to Modify

- Swap VAD/classifier/transcriber: implement the corresponding port in `infrastructure/` and wire it in `cli.py`
- Tune clip length: adjust `min_duration`, `max_duration`, `max_gap` in `domain/segment_grouping.py`
- Add metadata columns: extend `ClipWriter.write_clip()` in `infrastructure/writer.py` and the `ClipResult` model if needed
- Add a new pipeline step: extend `pipeline.py` and keep the same port abstractions
