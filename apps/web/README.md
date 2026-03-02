# transcript-editor

Next.js web app for correcting clip transcripts. Loads runs and clips from Supabase, streams audio from storage, and saves corrections back to the database.

## Setup

From the repo root:

```bash
make install
./ambara editor
```

Starts the dev server at http://localhost:3000. Requires Supabase URL and keys; auth uses Supabase Auth. Set `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` (or rely on `.env` at repo root).

## Usage

```bash
./ambara editor
```

Then open http://localhost:3000. Routes:

- `/`: Run list, stats, filter by type and search
- `/login`: Sign in
- `/read`: New reading session setup
- `/runs/[runId]`: Clip editor—transcribe, split, record modes; bulk discard; session stats

## Architecture

- `app/`: `page.tsx` (run list), `runs/[runId]/page.tsx` (clip editor), `read/` (reading session), `login/`, `auth/callback/`
- `components/`: `ClipEditor`, `ClipList`, `ChapterSplitter`, `ChunkRecorder`, `Waveform`, `RunCard`, `SessionStats`, `Toast`
- `hooks/`: `useClipsData`, `useClipActions`, `useAudioUrls`, `useClipEditorAutosave`, `useClipEditorKeyboard`, `useGuardedNavigation`, `useAudioRecorder`
- `lib/`: `supabase/` (client, server, types), `format.ts`, `wav.ts`, `chunking.ts`, `word-diff.ts`, `audio-split.ts`

## Data Flow

Input: Supabase `runs` and `clips` tables; audio from `clips` storage bucket. Output: `clip_edits` and updated `clips` (status, corrected_transcription, paragraphs). Auth via Supabase Auth. No file system access; all data from Supabase.

## How to Modify

- New route: add under `app/` (Next.js App Router); protect with middleware if needed
- New editor mode: add tab and component (e.g. in `runs/[runId]/page.tsx`); extend `useClipActions` for new save logic
- Schema changes: update `lib/supabase/types.ts` and components that read/write clips
- UI tweaks: edit components in `components/`; shared styles in layout or globals
- Add bulk actions: extend `ClipList` and `useClipActions` (e.g. bulk correct, export)
