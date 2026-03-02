# API Integration Design: CLI-Free Pipeline from the Transcript Editor

**Goal:** Make the transcript editor the single interface for the entire Ambara pipeline — no CLI needed for ingest, extract, re-draft, or export.

**Approach:** FastAPI worker (Python) + Next.js proxy routes + Supabase `jobs` table for status tracking.

---

## Architecture

```
┌─────────────────────────────────┐
│  transcript-editor (Next.js)    │
│  - Ingest page (URL + label)    │
│  - Jobs status on home page     │
│  - Training page (export+Colab) │
│  - Existing clip editor         │
└──────────┬──────────────────────┘
           │ /api/* proxy routes
┌──────────▼──────────────────────┐
│  Next.js API Routes             │
│  POST /api/ingest               │
│  POST /api/redraft              │
│  POST /api/export               │
│  GET  /api/jobs/[jobId]         │
└──────────┬──────────────────────┘
           │ HTTP (WORKER_URL)
┌──────────▼──────────────────────┐
│  FastAPI Worker (services/api/) │
│  - Loads ML models once         │
│  - Runs ingest/redraft jobs     │
│  - Updates jobs table           │
│  - ThreadPoolExecutor (1 worker)│
└─────────────────────────────────┘
```

The Next.js app handles lightweight orchestration. A separate Python FastAPI process handles heavy ML work. They communicate via HTTP. Job status lives in Supabase.

---

## 1. Supabase `jobs` Table

```sql
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
```

Uses the existing `set_updated_at` trigger. `params` and `result` are JSONB so each job type stores its own shape without schema changes.

---

## 2. FastAPI Worker (`services/api/`)

### Structure

```
services/api/
├── pyproject.toml
├── src/api/
│   ├── __init__.py
│   ├── app.py                  # FastAPI app factory
│   ├── config.py               # Settings (Supabase creds, device, paths)
│   ├── jobs.py                 # Job creation, status update helpers
│   ├── models_cache.py         # Singleton model loader
│   └── routes/
│       ├── __init__.py
│       ├── ingest.py           # POST /ingest
│       ├── redraft.py          # POST /redraft
│       ├── export.py           # POST /export
│       └── jobs.py             # GET /jobs/{id}
```

### Model Caching

`models_cache.py` loads VAD, ASTClassifier, and Whisper once at startup (or on first request) and reuses them across jobs. Avoids the 30-60s cold start per request.

### Background Execution

`POST /ingest` and `POST /redraft` create a job row (status=`queued`), spawn work in a `ThreadPoolExecutor(max_workers=1)`, and return the `job_id` immediately. One ML job at a time since they are GPU-bound; additional requests queue.

### Ingest Flow

```
1. POST /ingest { url, label }
2. Create job row (queued), return { job_id }
3. Background thread:
   a. status=running, progress=0,  "Downloading from YouTube..."
   b. download_audio(url, ...)
   c. progress=20, "Loading models..."
   d. Load/reuse cached models
   e. progress=30, "Extracting clips..."
   f. run_pipeline(...)
   g. progress=80, "Syncing to Supabase..."
   h. sync_run(...)
   i. status=done, progress=100, result={ run_id, clip_count }
```

### Export Flow

`POST /export` is synchronous — runs fast enough to return the result directly.

---

## 3. Next.js API Routes (Thin Proxies)

| Route | Method | Forwards to |
|---|---|---|
| `/api/ingest` | POST | `WORKER_URL/ingest` |
| `/api/redraft` | POST | `WORKER_URL/redraft` |
| `/api/export` | POST | `WORKER_URL/export` |
| `/api/jobs/[jobId]` | GET | `WORKER_URL/jobs/{jobId}` |

Why proxy instead of calling FastAPI directly from the browser:
- Worker URL might not be publicly accessible
- Auth stays in one place (Supabase session check in Next.js middleware)
- Frontend code never needs to know about `WORKER_URL`

Configuration: `WORKER_URL=http://localhost:8000` in `.env.local`.

---

## 4. Frontend UI

### Ingest Page (`/ingest`)

- YouTube URL text input
- Label text input (auto-generated from URL if blank)
- "Ingest" button
- Progress card (polled every 3s via `GET /api/jobs/:id`)
- On completion: link to the new run

Accessible from the home page header alongside "New Reading Session".

### Jobs Dashboard (home page)

Active/recent jobs appear at the top of the existing home page, above the run list:
- Type, status badge, progress bar + message, timestamp
- Completed jobs auto-dismiss or can be dismissed manually

### Training Page (`/training`)

- "Export Training Data" button
- Colab instructions and notebook link
- Status of last export

---

## 5. CLI Changes

New command: `./ambara api` starts the FastAPI worker.

```bash
api)
    cd services/api
    .venv/bin/uvicorn api.app:create_app --factory --reload --port 8000
    ;;
```

Dev workflow:
```bash
./ambara editor   # Terminal 1
./ambara api      # Terminal 2
```

Existing CLI commands remain unchanged. The API is an additional interface.

`make install` updated to install `services/api` (editable).

---

## 6. Error Handling

1. **Worker not running:** Next.js proxy returns clear error message. UI shows toast.
2. **Job failure:** Thread catches exceptions, sets `status=failed` with `result.error`. UI shows error + retry button.
3. **Duplicate ingest:** Allowed (creates new run, same as CLI).
4. **Model loading failure:** Job fails with descriptive error in `result.error`.
5. **Concurrent jobs:** `max_workers=1`, additional requests queue with `queued` status.

---

## 7. Deployment

- **Dev:** Both processes run locally (`./ambara editor` + `./ambara api`)
- **Prod:** Next.js on Vercel/Cloudflare, FastAPI on GPU machine (or Modal)
- **Training:** Stays on Colab (free GPU)
- **Remote-ready:** Change `WORKER_URL` to point to remote machine — zero code changes

---

## Scope Exclusions

- No job cancellation (can add later)
- No WebSocket/SSE progress (polling is sufficient)
- No automatic Colab triggering (manual with instructions)
- No multi-user job isolation (single-user for now)
