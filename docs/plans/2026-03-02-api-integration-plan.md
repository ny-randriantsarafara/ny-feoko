# API Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the transcript editor the single interface for the Ambara pipeline by adding a FastAPI worker and Next.js proxy routes.

**Architecture:** FastAPI worker (Python, `services/api/`) handles ML-heavy jobs. Next.js API routes proxy requests. Supabase `jobs` table tracks background work. Frontend gets ingest page, jobs dashboard, and training page.

**Tech Stack:** FastAPI, uvicorn, ThreadPoolExecutor, Next.js 15 App Router, Supabase, Tailwind CSS 4

---

### Task 1: Supabase `jobs` Table Migration

**Files:**
- Create: `docs/supabase/007_jobs.sql`

**Step 1: Write the migration SQL**

```sql
-- Background job tracking for the API worker.

create table if not exists jobs (
  id uuid primary key default gen_random_uuid(),
  type text not null check (type in ('ingest', 'redraft', 'export')),
  status text not null default 'queued'
    check (status in ('queued', 'running', 'done', 'failed')),
  progress integer not null default 0,
  progress_message text,
  params jsonb not null default '{}',
  result jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists jobs_set_updated_at on jobs;
create trigger jobs_set_updated_at
before update on jobs
for each row execute function set_updated_at();

create index if not exists jobs_status_created_idx
  on jobs (status, created_at desc);
```

**Step 2: Run the migration in Supabase SQL editor**

Run the SQL above in the Supabase dashboard SQL editor. Verify the table exists:
```sql
select * from jobs limit 1;
```

**Step 3: Commit**

```bash
git add docs/supabase/007_jobs.sql
git commit -m "feat: add jobs table migration for background job tracking"
```

---

### Task 2: TypeScript Types for Jobs Table

**Files:**
- Modify: `services/transcript-editor/src/lib/supabase/types.ts`

**Step 1: Add the `jobs` table type to the Database interface**

Add the `jobs` table definition inside `Database["public"]["Tables"]`, after `clip_edits`. Follow the exact pattern used by `runs`, `clips`, and `clip_edits`.

Row type:
```typescript
jobs: {
  Row: {
    id: string;
    type: "ingest" | "redraft" | "export";
    status: "queued" | "running" | "done" | "failed";
    progress: number;
    progress_message: string | null;
    params: Record<string, unknown>;
    result: Record<string, unknown> | null;
    created_at: string;
    updated_at: string;
  };
  Insert: {
    id?: string;
    type: "ingest" | "redraft" | "export";
    status?: "queued" | "running" | "done" | "failed";
    progress?: number;
    progress_message?: string | null;
    params?: Record<string, unknown>;
    result?: Record<string, unknown> | null;
    created_at?: string;
    updated_at?: string;
  };
  Update: {
    id?: string;
    type?: "ingest" | "redraft" | "export";
    status?: "queued" | "running" | "done" | "failed";
    progress?: number;
    progress_message?: string | null;
    params?: Record<string, unknown>;
    result?: Record<string, unknown> | null;
    created_at?: string;
    updated_at?: string;
  };
  Relationships: [];
};
```

**Step 2: Verify no lint errors**

Run: `cd services/transcript-editor && npx tsc --noEmit`
Expected: no errors related to the types file

**Step 3: Commit**

```bash
git add services/transcript-editor/src/lib/supabase/types.ts
git commit -m "feat: add jobs table TypeScript types"
```

---

### Task 3: FastAPI Worker — Project Scaffolding

**Files:**
- Create: `services/api/pyproject.toml`
- Create: `services/api/src/api/__init__.py`
- Create: `services/api/src/api/app.py`
- Create: `services/api/src/api/config.py`
- Modify: `Makefile` (add `services/api/` to install target)

**Step 1: Create `pyproject.toml`**

Follow the exact pattern from `services/pipeline/pyproject.toml`:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "ambara-api"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "ny-feoko-shared",
    "pipeline",
    "clip-extraction",
    "db-sync",
    "asr-training",
    "yt-download",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "python-dotenv>=1",
    "supabase>=2",
]

[tool.hatch.build.targets.wheel]
packages = ["src/api"]
```

**Step 2: Create `src/api/__init__.py`**

Empty file.

**Step 3: Create `src/api/config.py`**

```python
"""API worker configuration, loaded from environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_service_role_key: str
    device: str
    input_dir: Path
    output_dir: Path
    whisper_model: str


def load_settings() -> Settings:
    _load_env()
    return Settings(
        supabase_url=_require("SUPABASE_URL"),
        supabase_service_role_key=_require("SUPABASE_SERVICE_ROLE_KEY"),
        device=os.environ.get("AMBARA_DEVICE", "cpu"),
        input_dir=Path(os.environ.get("AMBARA_INPUT_DIR", "data/input")),
        output_dir=Path(os.environ.get("AMBARA_OUTPUT_DIR", "data/output")),
        whisper_model=os.environ.get("AMBARA_WHISPER_MODEL", "small"),
    )


def _require(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def _load_env() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    dotenv_path = repo_root / ".env"
    if dotenv_path.exists():
        load_dotenv(dotenv_path)
```

**Step 4: Create `src/api/app.py`**

```python
"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI

from api.config import load_settings


def create_app() -> FastAPI:
    settings = load_settings()
    app = FastAPI(title="Ambara API Worker")
    app.state.settings = settings
    return app
```

**Step 5: Add to Makefile**

Add `$(PIP) install -e services/api/` to both the `install` and `colab-install` targets, after `services/pipeline/`.

**Step 6: Install and verify**

Run: `make install`
Expected: all packages install without errors

Run: `.venv/bin/python -c "from api.app import create_app; print(create_app().title)"`
Expected: `Ambara API Worker`

**Step 7: Commit**

```bash
git add services/api/ Makefile
git commit -m "feat: scaffold FastAPI worker service"
```

---

### Task 4: FastAPI Worker — Job Management Module

**Files:**
- Create: `services/api/src/api/jobs.py`

**Step 1: Write the jobs module**

This module creates and updates job rows in Supabase. It's used by all route handlers.

```python
"""Job lifecycle management — create, update, and query jobs in Supabase."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from supabase import Client


@dataclass(frozen=True)
class JobUpdate:
    status: str | None = None
    progress: int | None = None
    progress_message: str | None = None
    result: dict[str, Any] | None = None


def create_job(
    client: Client,
    job_type: str,
    params: dict[str, Any],
) -> str:
    row = client.table("jobs").insert({
        "type": job_type,
        "status": "queued",
        "params": params,
    }).execute()
    return row.data[0]["id"]


def update_job(client: Client, job_id: str, update: JobUpdate) -> None:
    payload: dict[str, Any] = {}
    if update.status is not None:
        payload["status"] = update.status
    if update.progress is not None:
        payload["progress"] = update.progress
    if update.progress_message is not None:
        payload["progress_message"] = update.progress_message
    if update.result is not None:
        payload["result"] = update.result
    if payload:
        client.table("jobs").update(payload).eq("id", job_id).execute()


def fail_job(client: Client, job_id: str, error: str) -> None:
    update_job(client, job_id, JobUpdate(
        status="failed",
        result={"error": error},
    ))


def get_job(client: Client, job_id: str) -> dict[str, Any] | None:
    result = (
        client.table("jobs")
        .select("*")
        .eq("id", job_id)
        .limit(1)
        .execute()
    )
    if result.data:
        return result.data[0]
    return None


def list_recent_jobs(client: Client, limit: int = 20) -> list[dict[str, Any]]:
    result = (
        client.table("jobs")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data
```

**Step 2: Write tests**

Create: `services/api/tests/__init__.py` (empty)
Create: `services/api/tests/test_jobs.py`

Test the `JobUpdate` dataclass defaults and the `update_job` payload construction. For Supabase calls, test at integration level later.

```python
from api.jobs import JobUpdate


def test_job_update_defaults():
    update = JobUpdate()
    assert update.status is None
    assert update.progress is None
    assert update.progress_message is None
    assert update.result is None


def test_job_update_with_values():
    update = JobUpdate(status="running", progress=50, progress_message="Extracting...")
    assert update.status == "running"
    assert update.progress == 50
    assert update.progress_message == "Extracting..."
    assert update.result is None
```

**Step 3: Run tests**

Run: `.venv/bin/pytest services/api/tests/ -v`
Expected: 2 tests pass

**Step 4: Commit**

```bash
git add services/api/src/api/jobs.py services/api/tests/
git commit -m "feat: add job lifecycle management module"
```

---

### Task 5: FastAPI Worker — Model Cache

**Files:**
- Create: `services/api/src/api/models_cache.py`

**Step 1: Write the models cache singleton**

```python
"""Singleton cache for ML models — loaded once, reused across jobs."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from clip_extraction.domain.ports import ClassifierPort, TranscriberPort, VADPort

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_instance: ModelCache | None = None


@dataclass
class ModelCache:
    vad: VADPort
    classifier: ClassifierPort
    transcriber: TranscriberPort


def get_models(
    device: str,
    *,
    vad_threshold: float = 0.35,
    whisper_model: str = "small",
    whisper_hf: str = "",
) -> ModelCache:
    global _instance
    if _instance is not None:
        return _instance

    with _lock:
        if _instance is not None:
            return _instance

        logger.info("Loading ML models (first request)...")
        _instance = _load_models(
            device,
            vad_threshold=vad_threshold,
            whisper_model=whisper_model,
            whisper_hf=whisper_hf,
        )
        logger.info("ML models loaded and cached.")
        return _instance


def _load_models(
    device: str,
    *,
    vad_threshold: float,
    whisper_model: str,
    whisper_hf: str,
) -> ModelCache:
    from clip_extraction.infrastructure.classifier import ASTClassifier
    from clip_extraction.infrastructure.vad import SileroVAD

    vad = SileroVAD(threshold=vad_threshold)
    classifier = ASTClassifier(device=device)

    if whisper_hf:
        from clip_extraction.infrastructure.hf_transcriber import HuggingFaceTranscriber
        transcriber = HuggingFaceTranscriber(model_id=whisper_hf, device=device)
    else:
        from clip_extraction.infrastructure.transcriber import WhisperTranscriber
        transcriber = WhisperTranscriber(model_name=whisper_model, device=device)

    return ModelCache(vad=vad, classifier=classifier, transcriber=transcriber)
```

**Step 2: Commit**

```bash
git add services/api/src/api/models_cache.py
git commit -m "feat: add singleton ML model cache for API worker"
```

---

### Task 6: FastAPI Worker — Ingest Route

**Files:**
- Create: `services/api/src/api/routes/__init__.py`
- Create: `services/api/src/api/routes/ingest.py`
- Modify: `services/api/src/api/app.py` (register router)

**Step 1: Create `routes/__init__.py`**

Empty file.

**Step 2: Write the ingest route**

```python
"""POST /ingest — download YouTube audio, extract clips, sync to Supabase."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import APIRouter, Request
from pydantic import BaseModel

from api.config import Settings
from api.jobs import JobUpdate, create_job, fail_job, update_job
from api.models_cache import get_models
from db_sync.supabase_client import get_client

logger = logging.getLogger(__name__)

router = APIRouter()

_executor = ThreadPoolExecutor(max_workers=1)


class IngestRequest(BaseModel):
    url: str
    label: str
    whisper_model: str = "small"
    whisper_hf: str = ""
    vad_threshold: float = 0.35
    speech_threshold: float = 0.35


class IngestResponse(BaseModel):
    job_id: str


@router.post("/ingest", response_model=IngestResponse)
def start_ingest(body: IngestRequest, request: Request) -> IngestResponse:
    settings: Settings = request.app.state.settings
    client = get_client()

    job_id = create_job(client, "ingest", body.model_dump())
    _executor.submit(
        _run_ingest, job_id, body, settings,
    )
    return IngestResponse(job_id=job_id)


def _run_ingest(job_id: str, body: IngestRequest, settings: Settings) -> None:
    client = get_client()
    try:
        update_job(client, job_id, JobUpdate(
            status="running", progress=0,
            progress_message="Downloading from YouTube...",
        ))

        wav_path = _download(body.url, body.label, settings.input_dir)

        update_job(client, job_id, JobUpdate(
            progress=20, progress_message="Loading models...",
        ))

        models = get_models(
            settings.device,
            vad_threshold=body.vad_threshold,
            whisper_model=body.whisper_model,
            whisper_hf=body.whisper_hf,
        )

        update_job(client, job_id, JobUpdate(
            progress=30, progress_message="Extracting clips...",
        ))

        run_dir = _extract(wav_path, settings, models, body)

        update_job(client, job_id, JobUpdate(
            progress=80, progress_message="Syncing to Supabase...",
        ))

        run_id = _sync(client, run_dir, body.label)

        update_job(client, job_id, JobUpdate(
            status="done", progress=100,
            progress_message="Complete",
            result={"run_id": run_id, "run_dir": str(run_dir)},
        ))

    except Exception:
        logger.exception("Ingest job %s failed", job_id)
        fail_job(client, job_id, str(Exception))


def _download(url: str, label: str, input_dir: Path) -> Path:
    from yt_download.cli import download_audio
    return download_audio(url, input_dir, label)


def _extract(
    wav_path: Path,
    settings: Settings,
    models: ModelCache,
    body: IngestRequest,
) -> Path:
    from clip_extraction.pipeline import run_pipeline

    result = run_pipeline(
        input_file=str(wav_path),
        output_dir=str(settings.output_dir),
        vad=models.vad,
        classifier=models.classifier,
        transcriber=models.transcriber,
        speech_threshold=body.speech_threshold,
        run_label=body.label,
    )
    if result is None:
        raise RuntimeError("Extraction returned no output directory")
    return result


def _sync(client: Client, run_dir: Path, label: str) -> str:
    from db_sync.sync import sync_run

    sync_run(client, run_dir, label)

    from db_sync.run_resolution import resolve_label_to_run_id
    # The sync just created the run; get its ID from the label
    result = (
        client.table("runs")
        .select("id")
        .eq("label", label)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0]["id"]
```

Note: The `_run_ingest` except clause should capture the actual exception, not the `Exception` class. Fix: `except Exception as exc:` and `fail_job(client, job_id, str(exc))`.

Also add the missing import for `ModelCache` and `Client`:
```python
from api.models_cache import ModelCache, get_models
from supabase import Client
```

**Step 3: Register the router in `app.py`**

Update `create_app()` to include:
```python
from api.routes.ingest import router as ingest_router
app.include_router(ingest_router)
```

**Step 4: Verify the app starts**

Run: `.venv/bin/uvicorn api.app:create_app --factory --port 8000 &`
Run: `curl http://localhost:8000/docs`
Expected: FastAPI docs page loads, shows `/ingest` endpoint

Kill the server after verifying.

**Step 5: Commit**

```bash
git add services/api/src/api/routes/ services/api/src/api/app.py
git commit -m "feat: add POST /ingest route to API worker"
```

---

### Task 7: FastAPI Worker — Jobs Route

**Files:**
- Create: `services/api/src/api/routes/jobs.py`
- Modify: `services/api/src/api/app.py` (register router)

**Step 1: Write the jobs route**

```python
"""GET /jobs/{job_id} — poll job status. GET /jobs — list recent jobs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from api.jobs import get_job, list_recent_jobs
from db_sync.supabase_client import get_client

router = APIRouter()


@router.get("/jobs/{job_id}")
def get_job_status(job_id: str) -> dict[str, Any]:
    client = get_client()
    job = get_job(client, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/jobs")
def list_jobs(limit: int = 20) -> list[dict[str, Any]]:
    client = get_client()
    return list_recent_jobs(client, limit)
```

**Step 2: Register in `app.py`**

```python
from api.routes.jobs import router as jobs_router
app.include_router(jobs_router)
```

**Step 3: Commit**

```bash
git add services/api/src/api/routes/jobs.py services/api/src/api/app.py
git commit -m "feat: add GET /jobs routes to API worker"
```

---

### Task 8: FastAPI Worker — Redraft Route

**Files:**
- Create: `services/api/src/api/routes/redraft.py`
- Modify: `services/api/src/api/app.py` (register router)

**Step 1: Write the redraft route**

```python
"""POST /redraft — re-transcribe pending clips with a fine-tuned model."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import APIRouter, Request
from pydantic import BaseModel

from api.config import Settings
from api.jobs import JobUpdate, create_job, fail_job, update_job
from db_sync.supabase_client import get_client

logger = logging.getLogger(__name__)

router = APIRouter()

_executor = ThreadPoolExecutor(max_workers=1)


class RedraftRequest(BaseModel):
    label: str
    model_path: str
    device: str | None = None
    language: str = "mg"


class RedraftResponse(BaseModel):
    job_id: str


@router.post("/redraft", response_model=RedraftResponse)
def start_redraft(body: RedraftRequest, request: Request) -> RedraftResponse:
    settings: Settings = request.app.state.settings
    client = get_client()

    job_id = create_job(client, "redraft", body.model_dump())
    _executor.submit(_run_redraft, job_id, body, settings)
    return RedraftResponse(job_id=job_id)


def _run_redraft(job_id: str, body: RedraftRequest, settings: Settings) -> None:
    client = get_client()
    try:
        update_job(client, job_id, JobUpdate(
            status="running", progress=0,
            progress_message="Resolving run...",
        ))

        from db_sync.export import _resolve_run_id
        run_id = _resolve_run_id(client, run_id=None, label=body.label)

        update_job(client, job_id, JobUpdate(
            progress=10, progress_message="Locating source audio...",
        ))

        from pipeline.iterate import _ensure_source_dir
        source_dir = _ensure_source_dir(client, run_id, body.label)

        update_job(client, job_id, JobUpdate(
            progress=20, progress_message="Loading model and re-drafting...",
        ))

        from asr_training.redraft import redraft_pending
        device = body.device or settings.device
        updated = redraft_pending(
            client=client,
            model_path=body.model_path,
            source_dir=source_dir,
            run_id=run_id,
            device=device,
            language=body.language,
        )

        update_job(client, job_id, JobUpdate(
            status="done", progress=100,
            progress_message="Complete",
            result={"run_id": run_id, "clips_updated": updated},
        ))

    except Exception as exc:
        logger.exception("Redraft job %s failed", job_id)
        fail_job(client, job_id, str(exc))
```

**Step 2: Register in `app.py`**

```python
from api.routes.redraft import router as redraft_router
app.include_router(redraft_router)
```

**Step 3: Commit**

```bash
git add services/api/src/api/routes/redraft.py services/api/src/api/app.py
git commit -m "feat: add POST /redraft route to API worker"
```

---

### Task 9: FastAPI Worker — Export Route

**Files:**
- Create: `services/api/src/api/routes/export.py`
- Modify: `services/api/src/api/app.py` (register router)

**Step 1: Write the export route**

```python
"""POST /export — export corrected clips as a training dataset."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from api.config import Settings
from db_sync.supabase_client import get_client

router = APIRouter()


class ExportRequest(BaseModel):
    label: str
    eval_split: float = 0.1


@router.post("/export")
def export_training(body: ExportRequest, request: Request) -> dict[str, Any]:
    settings: Settings = request.app.state.settings
    client = get_client()

    from db_sync.export import _resolve_run_id
    run_id = _resolve_run_id(client, run_id=None, label=body.label)

    from pipeline.iterate import _ensure_source_dir
    source_dir = _ensure_source_dir(client, run_id, body.label)

    from db_sync.export import export_training as do_export
    training_dir = Path("data/training")

    dataset_dir = do_export(
        client,
        run_id=run_id,
        label=None,
        source_dir=source_dir,
        output=training_dir,
        eval_split=body.eval_split,
        overwrite=True,
    )

    return {
        "run_id": run_id,
        "dataset_dir": str(dataset_dir) if dataset_dir else None,
    }
```

**Step 2: Register in `app.py`**

```python
from api.routes.export import router as export_router
app.include_router(export_router)
```

**Step 3: Commit**

```bash
git add services/api/src/api/routes/export.py services/api/src/api/app.py
git commit -m "feat: add POST /export route to API worker"
```

---

### Task 10: CLI — Add `./ambara api` Command

**Files:**
- Modify: `ambara`

**Step 1: Add the `api` command**

Add a new case to the `ambara` bash script, after the `editor)` case:

```bash
  api)
    shift
    echo "Starting API worker at http://localhost:8000"
    cd "$ROOT"
    exec "$ROOT/.venv/bin/uvicorn" api.app:create_app --factory --reload --port 8000 "$@"
    ;;
```

Also add to the help text, after the `editor` line:
```
echo "  api          Start the API worker for the transcript editor"
```

**Step 2: Verify**

Run: `./ambara api --help` (should show uvicorn help)

**Step 3: Commit**

```bash
git add ambara
git commit -m "feat: add ./ambara api command to start FastAPI worker"
```

---

### Task 11: Next.js — API Proxy Routes

**Files:**
- Create: `services/transcript-editor/src/app/api/ingest/route.ts`
- Create: `services/transcript-editor/src/app/api/redraft/route.ts`
- Create: `services/transcript-editor/src/app/api/export/route.ts`
- Create: `services/transcript-editor/src/app/api/jobs/[jobId]/route.ts`
- Create: `services/transcript-editor/src/app/api/jobs/route.ts`

**Step 1: Create a shared proxy helper**

Create: `services/transcript-editor/src/lib/worker-proxy.ts`

```typescript
const WORKER_URL = process.env.WORKER_URL ?? "http://localhost:8000";

export async function proxyToWorker(
  path: string,
  options: RequestInit = {},
): Promise<Response> {
  const url = `${WORKER_URL}${path}`;

  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
    });

    return new Response(response.body, {
      status: response.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    return Response.json(
      {
        error: "API worker is not reachable. Start it with: ./ambara api",
      },
      { status: 502 },
    );
  }
}
```

**Step 2: POST /api/ingest**

```typescript
import { proxyToWorker } from "@/lib/worker-proxy";

export async function POST(request: Request) {
  const body = await request.json();
  return proxyToWorker("/ingest", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
```

**Step 3: POST /api/redraft**

Same pattern, proxying to `/redraft`.

**Step 4: POST /api/export**

Same pattern, proxying to `/export`.

**Step 5: GET /api/jobs/[jobId]**

```typescript
import { proxyToWorker } from "@/lib/worker-proxy";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ jobId: string }> },
) {
  const { jobId } = await params;
  return proxyToWorker(`/jobs/${jobId}`);
}
```

**Step 6: GET /api/jobs**

```typescript
import { proxyToWorker } from "@/lib/worker-proxy";

export async function GET() {
  return proxyToWorker("/jobs");
}
```

**Step 7: Add `WORKER_URL` to `.env.example`**

Append: `WORKER_URL=http://localhost:8000`

**Step 8: Verify no lint errors**

Run: `cd services/transcript-editor && npx tsc --noEmit`

**Step 9: Commit**

```bash
git add services/transcript-editor/src/app/api/ services/transcript-editor/src/lib/worker-proxy.ts services/transcript-editor/.env.example
git commit -m "feat: add Next.js API proxy routes to FastAPI worker"
```

---

### Task 12: Frontend — Job Polling Hook

**Files:**
- Create: `services/transcript-editor/src/hooks/useJobPolling.ts`

**Step 1: Write the hook**

```typescript
import { useCallback, useEffect, useRef, useState } from "react";
import type { Tables } from "@/lib/supabase/types";

type Job = Tables<"jobs">;

interface UseJobPollingOptions {
  readonly jobId: string | null;
  readonly intervalMs?: number;
  readonly enabled?: boolean;
}

interface UseJobPollingResult {
  readonly job: Job | null;
  readonly loading: boolean;
  readonly error: string | null;
}

export function useJobPolling({
  jobId,
  intervalMs = 3000,
  enabled = true,
}: UseJobPollingOptions): UseJobPollingResult {
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchJob = useCallback(async () => {
    if (!jobId) return;

    try {
      const response = await fetch(`/api/jobs/${jobId}`);
      if (!response.ok) {
        const data = await response.json();
        setError(data.error ?? "Failed to fetch job status");
        return;
      }
      const data: Job = await response.json();
      setJob(data);
      setError(null);

      if (data.status === "done" || data.status === "failed") {
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      }
    } catch {
      setError("Failed to connect to API");
    }
  }, [jobId]);

  useEffect(() => {
    if (!jobId || !enabled) return;

    setLoading(true);
    fetchJob().finally(() => setLoading(false));

    intervalRef.current = setInterval(fetchJob, intervalMs);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [jobId, intervalMs, enabled, fetchJob]);

  return { job, loading, error };
}
```

**Step 2: Commit**

```bash
git add services/transcript-editor/src/hooks/useJobPolling.ts
git commit -m "feat: add useJobPolling hook for background job status"
```

---

### Task 13: Frontend — Ingest Page

**Files:**
- Create: `services/transcript-editor/src/app/ingest/page.tsx`
- Create: `services/transcript-editor/src/components/JobProgressCard.tsx`

**Step 1: Create `JobProgressCard` component**

A reusable card that shows job status, progress bar, and message. Used on the ingest page and the home page jobs dashboard.

Props: `job: Tables<"jobs">`, optional `onViewRun: (runId: string) => void`

Shows:
- Status badge (queued=gray, running=blue, done=green, failed=red)
- Progress bar (0-100%)
- Progress message text
- If done and result has `run_id`: "View Run" link
- If failed and result has `error`: error message

Follow the existing component patterns: `"use client"`, Tailwind classes matching the dark theme, `readonly` props.

**Step 2: Create Ingest page**

A form page at `/ingest` with:
- Page title "Ingest Audio"
- YouTube URL input (required)
- Label input (optional, placeholder shows it's auto-generated)
- "Start Ingest" submit button (disabled while a job is active)
- On submit: POST to `/api/ingest`, get `job_id`, start polling with `useJobPolling`
- Show `JobProgressCard` below the form when a job is active
- On completion: show link to `/runs/{runId}`
- Back link to `/`

Follow the existing page patterns from `page.tsx` and `read/page.tsx`.

**Step 3: Verify the page renders**

Run: `cd services/transcript-editor && npx next dev &`
Navigate to `http://localhost:3000/ingest`
Expected: form renders without errors

**Step 4: Commit**

```bash
git add services/transcript-editor/src/app/ingest/ services/transcript-editor/src/components/JobProgressCard.tsx
git commit -m "feat: add ingest page with YouTube URL form and job progress"
```

---

### Task 14: Frontend — Jobs Dashboard on Home Page

**Files:**
- Create: `services/transcript-editor/src/hooks/useRecentJobs.ts`
- Modify: `services/transcript-editor/src/app/page.tsx`

**Step 1: Create `useRecentJobs` hook**

Polls `GET /api/jobs` every 5 seconds while any job is running. Returns `{ jobs, loading, error }`. Stops polling when all jobs are terminal (done/failed) or the list is empty.

**Step 2: Add jobs section to home page**

In `page.tsx`, between the stats bar and the type tabs, add a jobs section:
- Only shown when there are active (queued/running) jobs or recently completed ones
- Renders a list of `JobProgressCard` components
- "View all" link (or just show the last 5)

**Step 3: Add "New Ingest" button to the header**

Add a button next to "New Reading Session" that navigates to `/ingest`.

**Step 4: Verify**

Check the home page still renders correctly with no jobs.

**Step 5: Commit**

```bash
git add services/transcript-editor/src/hooks/useRecentJobs.ts services/transcript-editor/src/app/page.tsx
git commit -m "feat: add jobs dashboard to home page with ingest button"
```

---

### Task 15: Frontend — Training Page

**Files:**
- Create: `services/transcript-editor/src/app/training/page.tsx`

**Step 1: Create the training page**

A simple page at `/training` with:
- Title "Training"
- A run/label selector (dropdown or text input)
- "Export Training Data" button that calls `POST /api/export`
- Shows the result (dataset path, clip counts)
- Section with Colab instructions:
  - Link to the Colab notebook (from `notebooks/`)
  - Steps: 1) Export training data above, 2) Open Colab, 3) Configure settings, 4) Run training
- Back link to `/`

**Step 2: Add "Training" link to home page header**

Add alongside "New Reading Session" and "New Ingest".

**Step 3: Verify**

Navigate to `http://localhost:3000/training` — page renders.

**Step 4: Commit**

```bash
git add services/transcript-editor/src/app/training/ services/transcript-editor/src/app/page.tsx
git commit -m "feat: add training page with export and Colab instructions"
```

---

### Task 16: Update Empty State on Home Page

**Files:**
- Modify: `services/transcript-editor/src/app/page.tsx`

**Step 1: Update the empty state message**

Replace the current empty state that says "Sync your first extraction with: `./ambara sync --dir data/output/your-run`" with a message that directs users to the ingest page:

"No runs yet. Ingest your first audio to get started." with a link/button to `/ingest`.

**Step 2: Commit**

```bash
git add services/transcript-editor/src/app/page.tsx
git commit -m "feat: update empty state to point to ingest page instead of CLI"
```

---

### Task 17: End-to-End Verification

**Step 1: Start both processes**

Terminal 1: `./ambara editor`
Terminal 2: `./ambara api`

**Step 2: Verify API worker health**

```bash
curl http://localhost:8000/docs
curl http://localhost:8000/jobs
```

Expected: docs page loads, empty jobs list returns `[]`

**Step 3: Verify Next.js proxy**

```bash
curl http://localhost:3000/api/jobs
```

Expected: proxied response, `[]`

**Step 4: Verify UI pages**

- Home page loads at `/`
- Ingest page loads at `/ingest`
- Training page loads at `/training`
- Jobs section on home page shows "No active jobs" or is hidden

**Step 5: Test ingest flow (with a short YouTube video)**

- Go to `/ingest`
- Enter a short YouTube URL (< 1 min)
- Enter a label
- Click "Start Ingest"
- Watch progress update
- When done, click link to see the new run in the editor

**Step 6: Document results and commit any fixes**

```bash
git add -A
git commit -m "fix: end-to-end verification fixes"
```
