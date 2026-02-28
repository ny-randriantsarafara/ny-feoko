# Debt Cleanup & Documentation -- Design

Goal: make the Ambara codebase maintainable by a junior developer without AI agent assistance. Two phases: clean up tech debt first, then document the clean codebase.

## Phase 1: Tech Debt Cleanup

Service-by-service sweep in dependency order. Three tiers of work per service.

### Tier 1 -- Critical Fixes

| File | Issue | Fix |
|------|-------|-----|
| `transcript-editor/src/lib/word-diff.ts` L41 | Operator precedence bug in LCS comparison | Add parentheses: `(lcs[i+1]?.[j] ?? 0) >= (lcs[i]?.[j+1] ?? 0)` |
| `transcript-editor/src/lib/audio-split.ts` | `decodeAudioData` rejection unhandled | Wrap in try/catch, throw descriptive error |
| `transcript-editor/src/lib/wav.ts` | `decodeAudioData` rejection unhandled | Wrap in try/catch, throw descriptive error |
| `transcript-editor/src/components/ChapterSplitter.tsx` | `fetch()` result not checked before `.blob()` | Add `response.ok` check |
| `transcript-editor/src/components/ClipEditor.tsx` | Autosave failure silently swallowed | Surface error via toast or inline message |

### Tier 2 -- Structural Refactors

**transcript-editor (TypeScript/React)**

| Source file | LOC | Extraction |
|-------------|-----|------------|
| `runs/[runId]/page.tsx` | 531 | `useClipsData` (fetch, sort, select), `useAudioUrls` (signed URLs, preload), `useClipActions` (save, discard, merge), `useGuardedNavigation` (dirty guard) |
| `ChapterSplitter.tsx` | 627 | `useWaveSurferChapterSplit` (WaveSurfer init, regions, silence detection), extract split/upload logic into async helper |
| `ClipEditor.tsx` | 393 | `useClipEditorKeyboard` (all shortcuts), `useClipEditorAutosave` (debounce, status) |
| ClipEditor + ChapterSplitter | -- | Shared `PlaybackSpeedControls` component |
| ChapterSplitter | -- | Move `formatTime`/`parseTime` to `lib/format.ts` |

**Python services**

| Source file | LOC | Extraction |
|-------------|-----|------------|
| `clip-extraction/pipeline.py` | 308 | `domain/segment_grouping.py` (group_segments), `reporting.py` (summary), separate `vad_only.py` |
| `asr-training/train.py` | 292 | `callbacks.py` (TrainingProgressCallback), `metrics.py` (compute_metrics), `summary.py` (print_training_summary) |
| `pipeline/iterate.py` | 250 | Move `_format_duration` to shared utils |

### Tier 3 -- Cross-Service Patterns

| Pattern | Current state | Target |
|---------|--------------|--------|
| Pagination | Duplicated in dump.py, export.py, redraft.py | `db_sync/pagination.py` with `paginate_table()` |
| Device detection | Duplicated in asr-training/cli.py, pipeline/cli.py | `ny_feoko_shared/device.py` with `detect_device()` |
| Run resolution | `_resolve_run_id` in export.py, used by 3 modules | `db_sync/run_resolution.py` |
| Error strategy | `SystemExit` used as error mechanism in library code | Domain exceptions (RunNotFoundError, MissingConfigError, etc.) with CLI-level mapping |
| Magic numbers | 0.6, 0.8, 444, 448 scattered | Named constants in config modules |
| Missing tests | shared, yt-download, clip-extraction, parts of db-sync | Add tests alongside refactors |

### Service Order

1. **shared/** -- add subprocess error handling notes, tests for audio_io
2. **yt-download/** -- wrap subprocess calls in try/except, add tests
3. **clip-extraction/** -- split pipeline.py, extract constants, add tests
4. **db-sync/** -- pagination helper, domain exceptions, move _resolve_run_id, add tests
5. **asr-training/** -- split train.py, shared detect_device, constants, add tests
6. **pipeline/** -- unify _format_duration, fix `client: object` typing, add tests
7. **transcript-editor/** -- bug fix, hooks extraction, error handling, shared components

## Phase 2: Documentation

Three documentation layers, written after the debt cleanup.

### Layer 1: `docs/architecture.md`

- Project purpose and pipeline overview (ingest -> label -> iterate)
- System architecture diagram (mermaid): all 6 services, Supabase, data flow
- Service map table: name, language, purpose, external dependencies
- End-to-end data flow: YouTube URL -> clips -> corrections -> fine-tuned model
- Database schema overview: runs, clips, clip_edits with relationships
- Storage layout: Supabase `clips` bucket paths, local `data/` directory structure
- Configuration: `.env` files, required keys, Supabase setup

### Layer 2: Per-Service READMEs (`services/*/README.md`)

Template for each:
- **Purpose**: one-paragraph description
- **Setup**: install and configure
- **Usage**: CLI commands or how to run
- **Architecture**: module structure, key abstractions
- **Data flow**: inputs, outputs, external services
- **How to modify**: where to add features, what to watch out for

Services: shared, yt-download, clip-extraction, db-sync, asr-training, pipeline, transcript-editor.

### Layer 3: Updated Root `README.md`

- Keep current quick start
- Add "Project structure" section with annotated tree
- Add "For developers" section linking to architecture doc
- Link to per-service READMEs

## Key Decisions

- Debt cleanup before docs so we document clean code
- Service-by-service order follows dependency graph (shared -> leaf services -> orchestrators)
- No new dependencies for the cleanup
- Tests added alongside structural refactors, not as a separate pass
- Per-service READMEs follow a consistent template for discoverability
- Architecture doc uses mermaid diagrams (renderable in GitHub)
