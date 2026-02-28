# yt-download

Downloads YouTube audio and converts it to 16kHz mono WAV, suitable for downstream clip extraction and ASR training.

## Setup

From the repo root:

```bash
make install
```

Requires: `yt-dlp`, `ffmpeg` (for post-processing). The venv includes dependencies from the root pyproject.toml.

## Usage

```bash
./ambara download <url> -l <label>
```

Examples:

```bash
./ambara download "https://youtube.com/watch?v=abc123" -l church-mass
./ambara download "https://youtube.com/watch?v=abc123" -o data/input
```

Options:

- `--output`, `-o`: Output directory (default: `data/input`)
- `--label`, `-l`: Filename label (defaults to sanitized video title)

## Architecture

- `src/yt_download/cli.py`: Typer CLI and `download_audio()`—calls `yt-dlp` with `--postprocessor-args "ffmpeg:-ac 1 -ar 16000"` to produce mono 16kHz WAV
- Sanitizes video title for a safe filename via `_sanitize()` and `_get_title()`

## Data Flow

Input: YouTube URL. Output: single WAV file (e.g. `data/input/church-mass.wav`). External: `yt-dlp` and `ffmpeg`. Uses `ny_feoko_shared.audio_io.probe_duration` to report duration.

## How to Modify

- Add CLI options in `cli.py` and pass through to `download_audio()`
- Change output format or sample rate by adjusting the `--postprocessor-args` string
- For new post-processors, extend `download_audio()` and keep the same return type `Path`
