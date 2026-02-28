# Debt Cleanup & Documentation -- Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the Ambara codebase maintainable by a junior developer without AI assistance by cleaning up tech debt across all services, then documenting the clean codebase.

**Architecture:** Two-phase approach. Phase 1 sweeps services in dependency order (shared -> leaf services -> orchestrators -> frontend), applying critical fixes, structural refactors, and cross-service pattern improvements. Phase 2 writes layered documentation: architecture overview, per-service READMEs, and an updated root README.

**Tech Stack:** Python 3.10+ (Typer, PyTorch, Supabase), TypeScript/Next.js 15/React 19, Tailwind CSS 4, Supabase (Postgres + Storage + Auth)

---

## Phase 1: Tech Debt Cleanup

### Task 1: shared/ -- Add Tests for audio_io

**Files:**
- Create: `shared/tests/test_audio_io.py`
- Read: `shared/ny_feoko_shared/audio_io.py`
- Read: `shared/ny_feoko_shared/models.py`

**Step 1: Write failing tests for probe_duration and stream_chunks**

```python
from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess

import pytest

from ny_feoko_shared.audio_io import probe_duration, stream_chunks


class TestProbeDuration:
    def test_returns_duration_from_ffprobe(self):
        mock_result = MagicMock()
        mock_result.stdout = "  12.345\n"
        with patch("ny_feoko_shared.audio_io.subprocess.run", return_value=mock_result) as mock_run:
            result = probe_duration(Path("/tmp/test.wav"))
            assert result == pytest.approx(12.345)
            mock_run.assert_called_once()

    def test_raises_on_ffprobe_failure(self):
        with patch(
            "ny_feoko_shared.audio_io.subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "ffprobe"),
        ):
            with pytest.raises(subprocess.CalledProcessError):
                probe_duration(Path("/tmp/test.wav"))


class TestStreamChunks:
    def test_yields_chunks_of_correct_duration(self):
        with patch("ny_feoko_shared.audio_io.probe_duration", return_value=30.0):
            with patch("ny_feoko_shared.audio_io.load_audio_segment") as mock_load:
                import numpy as np

                mock_load.return_value = np.zeros(16000 * 10, dtype=np.float32)
                chunks = list(stream_chunks(Path("/tmp/test.wav"), chunk_sec=10))
                assert len(chunks) == 3
                for start_sec, audio in chunks:
                    assert isinstance(start_sec, float)
                    assert len(audio) == 16000 * 10
```

**Step 2: Run tests to verify they fail or pass**

Run: `cd /Users/nrandriantsarafara/Works/sandbox/ny-feoko && python -m pytest shared/tests/test_audio_io.py -v`
Expected: Tests should pass with mocks (no actual ffmpeg needed).

**Step 3: Fix any failures, adjust tests if function signatures differ**

Review `audio_io.py` carefully and adjust mock paths and assertions if needed.

**Step 4: Commit**

```bash
git add shared/tests/
git commit -m "test(shared): add unit tests for audio_io probe_duration and stream_chunks"
```

---

### Task 2: yt-download/ -- Error Handling and Tests

**Files:**
- Modify: `services/yt-download/src/yt_download/cli.py`
- Create: `services/yt-download/tests/test_cli.py`

**Step 1: Write failing tests for _sanitize and _get_title**

```python
from unittest.mock import patch, MagicMock
import subprocess

import pytest

from yt_download.cli import _sanitize, _get_title


class TestSanitize:
    def test_replaces_special_characters(self):
        assert _sanitize("Hello World!") == "Hello_World"

    def test_strips_leading_trailing_underscores(self):
        assert _sanitize("__test__") == "test"

    def test_collapses_multiple_underscores(self):
        assert _sanitize("a   b") == "a_b"


class TestGetTitle:
    def test_returns_title_from_ytdlp(self):
        mock_result = MagicMock()
        mock_result.stdout = "My Video Title\n"
        with patch("yt_download.cli.subprocess.run", return_value=mock_result):
            assert _get_title("https://youtube.com/watch?v=abc") == "My Video Title"

    def test_raises_on_ytdlp_failure(self):
        with patch(
            "yt_download.cli.subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "yt-dlp"),
        ):
            with pytest.raises(subprocess.CalledProcessError):
                _get_title("https://youtube.com/watch?v=abc")
```

**Step 2: Run tests**

Run: `cd /Users/nrandriantsarafara/Works/sandbox/ny-feoko && python -m pytest services/yt-download/tests/test_cli.py -v`

**Step 3: Wrap subprocess calls in try/except with clear error messages**

In `cli.py`, wrap `_get_title` and `download_audio` subprocess calls:

```python
def _get_title(url: str) -> str:
    try:
        result = subprocess.run(
            ["yt-dlp", "--get-title", url],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Failed to fetch title for {url}: {exc.stderr}") from exc
    return result.stdout.strip()
```

Apply the same pattern to `download_audio`.

**Step 4: Move lazy import to top of file**

Move `from ny_feoko_shared.audio_io import probe_duration` to the top-level imports.

**Step 5: Run tests, verify all pass**

Run: `python -m pytest services/yt-download/tests/ -v`

**Step 6: Commit**

```bash
git add services/yt-download/
git commit -m "fix(yt-download): improve error handling for subprocess calls, add tests"
```

---

### Task 3: clip-extraction/ -- Split pipeline.py

**Files:**
- Modify: `services/clip-extraction/src/clip_extraction/pipeline.py`
- Create: `services/clip-extraction/src/clip_extraction/domain/segment_grouping.py`
- Create: `services/clip-extraction/src/clip_extraction/reporting.py`
- Create: `services/clip-extraction/tests/test_segment_grouping.py`

**Step 1: Write failing tests for group_segments**

```python
import numpy as np
import pytest

from clip_extraction.domain.segment_grouping import group_segments
from ny_feoko_shared.models import AudioSegment


class TestGroupSegments:
    def test_groups_adjacent_segments(self):
        segments = [
            AudioSegment(start_sec=0.0, end_sec=1.0),
            AudioSegment(start_sec=1.5, end_sec=2.5),
        ]
        audio = np.zeros(16000 * 3, dtype=np.float32)
        candidates = group_segments(segments, audio, audio_start_sec=0.0, sr=16000)
        assert len(candidates) == 1

    def test_splits_when_gap_too_large(self):
        segments = [
            AudioSegment(start_sec=0.0, end_sec=1.0),
            AudioSegment(start_sec=10.0, end_sec=11.0),
        ]
        audio = np.zeros(16000 * 12, dtype=np.float32)
        candidates = group_segments(segments, audio, audio_start_sec=0.0, sr=16000)
        assert len(candidates) == 2

    def test_empty_segments_returns_empty(self):
        audio = np.zeros(16000, dtype=np.float32)
        assert group_segments([], audio, audio_start_sec=0.0, sr=16000) == []
```

**Step 2: Run tests to verify they fail (module doesn't exist yet)**

Run: `python -m pytest services/clip-extraction/tests/test_segment_grouping.py -v`
Expected: ImportError

**Step 3: Extract group_segments into domain/segment_grouping.py**

Move the `group_segments` function from `pipeline.py` to `domain/segment_grouping.py`. Keep the same signature and logic. Update `pipeline.py` to import from the new location.

**Step 4: Run tests to verify they pass**

Run: `python -m pytest services/clip-extraction/tests/test_segment_grouping.py -v`

**Step 5: Extract _print_extraction_summary into reporting.py**

Move `_print_extraction_summary` from `pipeline.py` to `reporting.py`. Update import in `pipeline.py`.

**Step 6: Extract run_vad_only into its own module or keep as a separate function**

If `run_vad_only` is small enough, keep in `pipeline.py` but clearly separated. Otherwise extract to `vad_only.py`.

**Step 7: Extract magic numbers to constants**

At top of `pipeline.py` (or a `constants.py`):
```python
MUSIC_SCORE_WEIGHT = 0.8
NO_SPEECH_THRESHOLD = 0.6
```

**Step 8: Run all clip-extraction tests**

Run: `python -m pytest services/clip-extraction/tests/ -v`

**Step 9: Commit**

```bash
git add services/clip-extraction/
git commit -m "refactor(clip-extraction): split pipeline.py into focused modules, add tests for segment grouping"
```

---

### Task 4: db-sync/ -- Shared Pagination, Domain Exceptions, Run Resolution

**Files:**
- Create: `services/db-sync/src/db_sync/pagination.py`
- Create: `services/db-sync/src/db_sync/run_resolution.py`
- Create: `services/db-sync/src/db_sync/exceptions.py`
- Modify: `services/db-sync/src/db_sync/dump.py`
- Modify: `services/db-sync/src/db_sync/export.py`
- Modify: `services/db-sync/src/db_sync/manage.py`
- Modify: `services/db-sync/src/db_sync/cli.py`
- Create: `services/db-sync/tests/test_pagination.py`
- Create: `services/db-sync/tests/test_run_resolution.py`

**Step 1: Write failing test for paginate_table**

```python
from unittest.mock import MagicMock

from db_sync.pagination import paginate_table


class TestPaginateTable:
    def test_fetches_all_rows_in_pages(self):
        client = MagicMock()
        page1 = [{"id": str(i)} for i in range(1000)]
        page2 = [{"id": str(i)} for i in range(1000, 1500)]

        def fake_execute():
            result = MagicMock()
            if client.from_.call_count <= 1:
                result.data = page1
            else:
                result.data = page2
            return result

        table_mock = MagicMock()
        table_mock.select.return_value = table_mock
        table_mock.range.return_value = table_mock
        table_mock.execute = fake_execute
        client.from_.return_value = table_mock

        rows = paginate_table(client, "clips", columns="*")
        assert len(rows) == 1500

    def test_returns_empty_for_no_data(self):
        client = MagicMock()
        table_mock = MagicMock()
        table_mock.select.return_value = table_mock
        table_mock.range.return_value = table_mock
        result = MagicMock()
        result.data = []
        table_mock.execute.return_value = result
        client.from_.return_value = table_mock

        rows = paginate_table(client, "clips", columns="*")
        assert rows == []
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest services/db-sync/tests/test_pagination.py -v`

**Step 3: Implement paginate_table**

```python
# services/db-sync/src/db_sync/pagination.py
from typing import Any

PAGE_SIZE = 1000


def paginate_table(
    client: Any,
    table: str,
    columns: str = "*",
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    all_rows: list[dict[str, Any]] = []
    offset = 0

    while True:
        query = client.from_(table).select(columns)
        if filters:
            for key, value in filters.items():
                query = query.eq(key, value)
        result = query.range(offset, offset + PAGE_SIZE - 1).execute()
        batch = result.data or []
        all_rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    return all_rows
```

**Step 4: Run test to verify it passes**

**Step 5: Create domain exceptions**

```python
# services/db-sync/src/db_sync/exceptions.py

class RunNotFoundError(Exception):
    pass

class MissingConfigError(Exception):
    pass

class SyncError(Exception):
    pass
```

**Step 6: Extract _resolve_run_id and _resolve_label into run_resolution.py**

Move from `export.py`. Update imports in `export.py`, `cli.py`, and note that `asr-training/cli.py` and `pipeline/iterate.py` also import this (update in their respective tasks).

**Step 7: Replace SystemExit with domain exceptions in export.py, sync.py, manage.py, supabase_client.py**

Replace `raise SystemExit(...)` with the appropriate domain exception. Update `cli.py` to catch these and call `typer.Exit(code=1)` or `typer.BadParameter`.

**Step 8: Replace duplicated pagination in dump.py and export.py with paginate_table**

**Step 9: Run all db-sync tests**

Run: `python -m pytest services/db-sync/tests/ -v`

**Step 10: Commit**

```bash
git add services/db-sync/
git commit -m "refactor(db-sync): extract pagination, run resolution, and domain exceptions"
```

---

### Task 5: shared/ -- Add detect_device Utility

**Files:**
- Modify: `shared/ny_feoko_shared/__init__.py`
- Create: `shared/ny_feoko_shared/device.py`
- Create: `shared/tests/test_device.py`

**Step 1: Write failing test**

```python
from unittest.mock import patch

from ny_feoko_shared.device import detect_device


class TestDetectDevice:
    def test_returns_requested_device(self):
        assert detect_device("cpu") == "cpu"

    def test_auto_detects_mps_on_mac(self):
        with patch("ny_feoko_shared.device.torch") as mock_torch:
            mock_torch.cuda.is_available.return_value = False
            mock_torch.backends.mps.is_available.return_value = True
            assert detect_device("auto") == "mps"

    def test_auto_detects_cuda(self):
        with patch("ny_feoko_shared.device.torch") as mock_torch:
            mock_torch.cuda.is_available.return_value = True
            assert detect_device("auto") == "cuda"

    def test_auto_falls_back_to_cpu(self):
        with patch("ny_feoko_shared.device.torch") as mock_torch:
            mock_torch.cuda.is_available.return_value = False
            mock_torch.backends.mps.is_available.return_value = False
            assert detect_device("auto") == "cpu"
```

**Step 2: Run test, verify failure**

**Step 3: Implement detect_device**

```python
# shared/ny_feoko_shared/device.py
import torch


def detect_device(requested: str) -> str:
    if requested != "auto":
        return requested
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"
```

**Step 4: Run test, verify pass**

**Step 5: Update asr-training/cli.py and pipeline/cli.py to import from shared**

Replace the duplicated `_detect_device` functions with:
```python
from ny_feoko_shared.device import detect_device
```

**Step 6: Run affected tests**

Run: `python -m pytest services/asr-training/tests/ services/pipeline/tests/ shared/tests/ -v`

**Step 7: Commit**

```bash
git add shared/ services/asr-training/ services/pipeline/
git commit -m "refactor: extract shared detect_device utility, remove duplication"
```

---

### Task 6: asr-training/ -- Split train.py, Constants

**Files:**
- Modify: `services/asr-training/src/asr_training/train.py`
- Create: `services/asr-training/src/asr_training/callbacks.py`
- Create: `services/asr-training/src/asr_training/metrics.py`
- Modify: `services/asr-training/src/asr_training/config.py`
- Modify: `services/asr-training/src/asr_training/redraft.py`
- Modify: `services/asr-training/src/asr_training/cli.py`

**Step 1: Extract TrainingProgressCallback to callbacks.py**

Move the class from `train.py`. Update import in `train.py`.

**Step 2: Extract compute_metrics to metrics.py**

Move the function out of `fine_tune`. It needs `processor` passed as a parameter instead of captured via closure.

```python
# services/asr-training/src/asr_training/metrics.py
import evaluate
import numpy as np


def make_compute_metrics(processor):
    wer_metric = evaluate.load("wer")

    def compute_metrics(pred):
        pred_ids = pred.predictions
        label_ids = np.where(pred.label_ids != -100, pred.label_ids, processor.tokenizer.pad_token_id)
        pred_str = processor.batch_decode(pred_ids, skip_special_tokens=True)
        label_str = processor.batch_decode(label_ids, skip_special_tokens=True)
        return {"wer": wer_metric.compute(predictions=pred_str, references=label_str)}

    return compute_metrics
```

**Step 3: Add max_new_tokens constant to config.py**

```python
DECODER_MAX_TOKENS = 448
DECODER_MAX_TOKENS_WITH_MARGIN = 444  # 448 - 4 for decoder start tokens
```

Update `redraft.py` and `infrastructure/hf_transcriber.py` to import from config.

**Step 4: Update run_resolution import in cli.py**

Update to use `from db_sync.run_resolution import resolve_run_id` (from Task 4).

**Step 5: Replace duplicated pagination in redraft.py with paginate_table**

Import from `db_sync.pagination` and replace `_fetch_pending_clips`.

**Step 6: Run all asr-training tests**

Run: `python -m pytest services/asr-training/tests/ -v`

**Step 7: Commit**

```bash
git add services/asr-training/
git commit -m "refactor(asr-training): split train.py into callbacks/metrics modules, share constants"
```

---

### Task 7: pipeline/ -- Unify _format_duration, Fix Typing

**Files:**
- Modify: `services/pipeline/src/pipeline/ingest.py`
- Modify: `services/pipeline/src/pipeline/iterate.py`
- Modify: `shared/ny_feoko_shared/__init__.py`
- Create: `shared/ny_feoko_shared/formatting.py`
- Create: `shared/tests/test_formatting.py`

**Step 1: Write test for format_duration**

```python
from ny_feoko_shared.formatting import format_duration


class TestFormatDuration:
    def test_seconds_only(self):
        assert format_duration(45.0) == "45s"

    def test_minutes_and_seconds(self):
        assert format_duration(125.0) == "2m 5s"

    def test_hours_minutes_seconds(self):
        assert format_duration(3725.0) == "1h 2m 5s"

    def test_zero(self):
        assert format_duration(0) == "0s"
```

**Step 2: Run test, verify failure**

**Step 3: Implement format_duration in shared**

```python
# shared/ny_feoko_shared/formatting.py

def format_duration(seconds: float) -> str:
    total = int(seconds)
    if total < 60:
        return f"{total}s"
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    parts: list[str] = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0:
        parts.append(f"{secs}s")
    return " ".join(parts)
```

**Step 4: Run test, verify pass**

**Step 5: Replace _format_duration in ingest.py and iterate.py**

Replace both private implementations with `from ny_feoko_shared.formatting import format_duration`.

**Step 6: Fix `client: object` typing in iterate.py**

Replace `client: object` with proper Supabase client type or a Protocol. Use `# type: ignore` only if the Supabase client type is not easily importable.

**Step 7: Run pipeline tests**

Run: `python -m pytest services/pipeline/tests/ -v`

**Step 8: Commit**

```bash
git add shared/ services/pipeline/
git commit -m "refactor(pipeline): unify format_duration in shared, fix client typing"
```

---

### Task 8: transcript-editor/ -- Fix word-diff.ts Bug

**Files:**
- Modify: `services/transcript-editor/src/lib/word-diff.ts`

**Step 1: Fix operator precedence bug on line 41**

Change:
```typescript
} else if (lcs[i + 1]?.[j] ?? 0 >= (lcs[i]?.[j + 1] ?? 0)) {
```
To:
```typescript
} else if ((lcs[i + 1]?.[j] ?? 0) >= (lcs[i]?.[j + 1] ?? 0)) {
```

**Step 2: Verify TypeScript compiles**

Run: `cd services/transcript-editor && npx tsc --noEmit`

**Step 3: Commit**

```bash
git add services/transcript-editor/src/lib/word-diff.ts
git commit -m "fix(transcript-editor): fix operator precedence bug in word-diff LCS comparison"
```

---

### Task 9: transcript-editor/ -- Fix Error Handling in Lib Files

**Files:**
- Modify: `services/transcript-editor/src/lib/audio-split.ts`
- Modify: `services/transcript-editor/src/lib/wav.ts`

**Step 1: Wrap decodeAudioData in try/catch in audio-split.ts**

In the `splitWavAtBoundaries` function, wrap `audioContext.decodeAudioData(arrayBuffer)` in try/catch and throw a descriptive error:

```typescript
let audioBuffer: AudioBuffer;
try {
  audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
} catch {
  throw new Error("Failed to decode audio data. The file may be corrupted or in an unsupported format.");
}
```

Apply the same in `detectSilences` if `decodeAudioData` is used there.

**Step 2: Apply same fix in wav.ts blobToWav function**

**Step 3: Verify TypeScript compiles**

Run: `cd services/transcript-editor && npx tsc --noEmit`

**Step 4: Commit**

```bash
git add services/transcript-editor/src/lib/
git commit -m "fix(transcript-editor): add error handling for audio decoding in audio-split and wav"
```

---

### Task 10: transcript-editor/ -- Fix Error Handling in Components

**Files:**
- Modify: `services/transcript-editor/src/components/ChapterSplitter.tsx`
- Modify: `services/transcript-editor/src/components/ClipEditor.tsx`
- Modify: `services/transcript-editor/src/app/runs/[runId]/page.tsx`

**Step 1: Add response.ok check in ChapterSplitter handleSplit**

Find the `fetch(audioUrl)` call and add:
```typescript
const response = await fetch(audioUrl);
if (!response.ok) {
  throw new Error(`Failed to fetch audio: ${response.status}`);
}
```

**Step 2: Surface autosave errors in ClipEditor**

Replace the `.catch(() => setSaveStatus(""))` with proper error feedback. The component receives a toast callback or similar -- check the parent for the pattern and apply it.

**Step 3: Add error handling for supabase.auth.getUser() in runs page**

Wrap in try/catch and redirect to login on auth failure.

**Step 4: Add catch to getAudioUrl().then() call**

```typescript
getAudioUrl(selected).then(setCurrentAudioUrl).catch(() => {
  setCurrentAudioUrl("");
});
```

**Step 5: Verify TypeScript compiles**

Run: `cd services/transcript-editor && npx tsc --noEmit`

**Step 6: Commit**

```bash
git add services/transcript-editor/src/
git commit -m "fix(transcript-editor): improve error handling in ChapterSplitter, ClipEditor, and runs page"
```

---

### Task 11: transcript-editor/ -- Extract Custom Hooks from runs/[runId]/page.tsx

**Files:**
- Create: `services/transcript-editor/src/hooks/useClipsData.ts`
- Create: `services/transcript-editor/src/hooks/useAudioUrls.ts`
- Create: `services/transcript-editor/src/hooks/useClipActions.ts`
- Create: `services/transcript-editor/src/hooks/useGuardedNavigation.ts`
- Modify: `services/transcript-editor/src/app/runs/[runId]/page.tsx`

**Step 1: Extract useClipsData hook**

Create a hook that encapsulates:
- `fetchClips` function (Supabase query, sorting, localStorage selection)
- `clips` state
- `selectedId` / `setSelectedId`
- Filter state and `filteredClips` derivation

The hook signature:
```typescript
function useClipsData(runId: string, filter: StatusFilter) {
  // returns { clips, filteredClips, selectedId, setSelectedId, fetchClips }
}
```

**Step 2: Extract useAudioUrls hook**

Encapsulates:
- `getAudioUrl(clip)` -- signed URL creation
- `currentAudioUrl` state
- Preload logic for adjacent clips
- URL refresh on clip selection

```typescript
function useAudioUrls(runId: string, clips: Clip[], selectedId: string | null) {
  // returns { currentAudioUrl, refreshAudioUrl }
}
```

**Step 3: Extract useClipActions hook**

Encapsulates:
- `handleSave`
- `handleAutoSave`
- `handleDiscardWithUndo`
- `handleMergeBack`
- `handleBulkDiscard`

```typescript
function useClipActions(params: {
  clips: Clip[];
  selectedId: string | null;
  userId: string;
  runId: string;
  fetchClips: () => Promise<void>;
  setSelectedId: (id: string) => void;
  addToast: (toast: ToastData) => void;
}) {
  // returns { handleSave, handleAutoSave, handleDiscardWithUndo, handleMergeBack, handleBulkDiscard, editorDirtyRef }
}
```

**Step 4: Extract useGuardedNavigation hook**

Encapsulates:
- `guardedSetMode` (checks dirty state before mode switch)
- `guardedSelectClip` (checks dirty state before clip switch)

**Step 5: Update page.tsx to use the extracted hooks**

The page component should now primarily handle layout, mode switching UI, and composing the hooks together.

**Step 6: Verify TypeScript compiles**

Run: `cd services/transcript-editor && npx tsc --noEmit`

**Step 7: Manually test in browser**

Run the editor and verify:
- Clip selection works
- Audio plays
- Save/discard/merge work
- Mode switching works
- Autosave works

**Step 8: Commit**

```bash
git add services/transcript-editor/src/
git commit -m "refactor(transcript-editor): extract hooks from runs page (useClipsData, useAudioUrls, useClipActions, useGuardedNavigation)"
```

---

### Task 12: transcript-editor/ -- Extract Hooks from ClipEditor and ChapterSplitter

**Files:**
- Create: `services/transcript-editor/src/hooks/useClipEditorKeyboard.ts`
- Create: `services/transcript-editor/src/hooks/useClipEditorAutosave.ts`
- Create: `services/transcript-editor/src/hooks/useWaveSurferSplit.ts`
- Create: `services/transcript-editor/src/components/PlaybackSpeedControls.tsx`
- Modify: `services/transcript-editor/src/components/ClipEditor.tsx`
- Modify: `services/transcript-editor/src/components/ChapterSplitter.tsx`
- Modify: `services/transcript-editor/src/lib/format.ts`

**Step 1: Extract useClipEditorKeyboard hook**

Move all keyboard shortcut handling from ClipEditor into a dedicated hook.

**Step 2: Extract useClipEditorAutosave hook**

Move the debounce timer, save status, and flash state into a hook.

**Step 3: Create shared PlaybackSpeedControls component**

Both ClipEditor and ChapterSplitter have identical speed control UI. Extract into a shared component:

```typescript
interface PlaybackSpeedControlsProps {
  readonly speed: number;
  readonly onSpeedChange: (speed: number) => void;
}
```

**Step 4: Move formatTime/parseTime to lib/format.ts**

Extract from ChapterSplitter and add to the existing `format.ts` file alongside `formatDuration`.

**Step 5: Extract useWaveSurferSplit hook from ChapterSplitter**

Move WaveSurfer initialization, region management, and silence detection into a hook.

**Step 6: Update ClipEditor and ChapterSplitter to use new hooks/components**

**Step 7: Verify TypeScript compiles**

Run: `cd services/transcript-editor && npx tsc --noEmit`

**Step 8: Manually test in browser**

Verify all editor modes (transcribe, split, record) still work correctly.

**Step 9: Commit**

```bash
git add services/transcript-editor/src/
git commit -m "refactor(transcript-editor): extract editor hooks and shared PlaybackSpeedControls"
```

---

## Phase 2: Documentation

### Task 13: Write docs/architecture.md

**Files:**
- Create: `docs/architecture.md`

**Step 1: Write architecture document**

Include these sections:
1. **Overview** -- Ambara's purpose, the three-stage pipeline vision (Listener -> Translator -> Speaker)
2. **System Architecture** -- Mermaid diagram showing all services, Supabase, and data flow
3. **Service Map** -- Table: service name, language, purpose, external deps
4. **End-to-End Data Flow** -- Detailed walkthrough of ingest -> label -> iterate cycle
5. **Database Schema** -- Tables (runs, clips, clip_edits), relationships, key fields
6. **Storage Layout** -- Supabase `clips` bucket paths, local `data/` directory structure
7. **Configuration** -- Required `.env` files, environment variables, Supabase setup steps
8. **CLI Reference** -- All `./ambara` commands with brief descriptions

**Step 2: Commit**

```bash
git add docs/architecture.md
git commit -m "docs: add architecture overview with pipeline diagram and service map"
```

---

### Task 14: Write Per-Service READMEs

**Files:**
- Create: `shared/README.md`
- Create: `services/yt-download/README.md`
- Create: `services/clip-extraction/README.md`
- Create: `services/db-sync/README.md`
- Create: `services/asr-training/README.md`
- Create: `services/pipeline/README.md`
- Create: `services/transcript-editor/README.md`

**Step 1: Write each README following this template**

For each service:
```markdown
# [Service Name]

[One-paragraph description of what this service does and why it exists.]

## Setup

[How to install dependencies and configure.]

## Usage

[CLI commands or how to run. Include examples.]

## Architecture

[Module structure. Key abstractions. Where the important logic lives.]

## Data Flow

[What goes in, what comes out, what external services it talks to.]

## How to Modify

[Where to add new features. What to watch out for. Key files to understand first.]
```

**Step 2: Commit all READMEs**

```bash
git add shared/README.md services/*/README.md
git commit -m "docs: add per-service READMEs with setup, usage, architecture, and modification guides"
```

---

### Task 15: Update Root README.md

**Files:**
- Modify: `README.md`

**Step 1: Add project structure section**

Add an annotated directory tree with one-line descriptions.

**Step 2: Add "For Developers" section**

Link to `docs/architecture.md` and per-service READMEs. Include a brief "how to contribute" paragraph.

**Step 3: Keep existing quick start**

Update if any commands have changed, but preserve the existing structure.

**Step 4: Commit**

```bash
git add README.md
git commit -m "docs: update root README with project structure and developer links"
```

---

## Summary

| Task | Service | Type | Estimated Steps |
|------|---------|------|-----------------|
| 1 | shared | Tests | 4 |
| 2 | yt-download | Error handling + tests | 6 |
| 3 | clip-extraction | Structural refactor + tests | 9 |
| 4 | db-sync | Pattern extraction + exceptions | 10 |
| 5 | shared | Shared utility | 7 |
| 6 | asr-training | Structural refactor | 7 |
| 7 | pipeline | Shared utility + typing | 8 |
| 8 | transcript-editor | Bug fix | 3 |
| 9 | transcript-editor | Error handling (libs) | 4 |
| 10 | transcript-editor | Error handling (components) | 6 |
| 11 | transcript-editor | Hooks extraction (runs page) | 8 |
| 12 | transcript-editor | Hooks extraction (editor/splitter) | 9 |
| 13 | docs | Architecture doc | 2 |
| 14 | docs | Per-service READMEs | 2 |
| 15 | docs | Root README update | 4 |

Total: 15 tasks, ~89 steps.
