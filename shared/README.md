# ny_feoko_shared

Shared utilities for audio I/O, data models, device detection, and formatting used across yt-download, clip-extraction, asr-training, and pipeline services.

## Setup

The package is installed in editable mode via the root `make install`. From the repo root:

```bash
make install
```

Dependencies: numpy, torch (for device detection). Used transitively by services that depend on `ny_feoko_shared`.

## Usage

Import modules as needed:

```python
from ny_feoko_shared.audio_io import probe_duration, load_audio_segment, stream_chunks
from ny_feoko_shared.models import AudioSegment, ClipCandidate, ClipResult
from ny_feoko_shared.device import detect_device
from ny_feoko_shared.formatting import format_duration
```

## Architecture

- `audio_io.py`: FFmpeg-based utilities—`probe_duration`, `load_audio_segment`, `stream_chunks` for chunked processing
- `models.py`: Data models—`AudioSegment` (VAD speech region), `ClipCandidate` (grouped segments + audio), `ClipResult` (classified/transcribed clip)
- `device.py`: `detect_device("auto")` returns cuda > mps > cpu
- `formatting.py`: `format_duration(seconds)` returns human-readable strings like "1h 2m 5s"

## Data Flow

Inputs: file paths, raw audio arrays, device strings. Outputs: duration floats, numpy arrays (float32 mono at 16kHz), model instances. No external services. Requires `ffmpeg` and `ffprobe` on the system.

## How to Modify

- Add new models in `models.py` if clip-extraction or db-sync need new fields
- Extend `audio_io.py` for new audio operations (keep ffmpeg-based for efficiency)
- Add formatting helpers in `formatting.py`
- Changes propagate to all services that import the package; run `make install` after edits
