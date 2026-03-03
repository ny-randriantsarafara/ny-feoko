# Model Selection and HuggingFace Auth Consistency Design

## Problem

The web ingest flow currently does not let users choose a transcription model, while CLI and notebook paths already expose model options. HuggingFace authentication is also inconsistent across entry points. This creates drift between CLI, REST, web, and notebook behavior and increases maintenance risk.

## Goals

1. Add model selection to the web ingest experience with the same behavior as CLI/REST.
2. Support HuggingFace authentication for web-triggered ingest and training workflows.
3. Make ingest and training input handling consistent across CLI, REST, and notebook.
4. Improve maintainability with clean code, predictable validation, and no dead paths.

## Non-Goals

1. No compatibility shim for old REST payloads (breaking changes allowed).
2. No new product workflows beyond ingest/training/redraft consistency.
3. No redesign of core use-case orchestration.

## Design Decisions

1. Create shared request schemas in the application layer under `apps/api/src/application/types/`.
2. Keep use cases as orchestrators and services as reusable domain/technical logic.
3. Use a centralized HuggingFace auth helper in API code, driven by `HF_TOKEN` from environment.
4. Refactor model caching to be keyed by effective model configuration, not a single global instance.
5. Make the backend the source of truth for defaults and validation; web and notebook mirror backend contracts.

## Architecture

### Shared Request Schemas (`application/types`)

Add canonical, typed request schemas for:

- ingest inputs (`url`, `label`, `whisper_model`, `whisper_hf`, `vad_threshold`, `speech_threshold`)
- training/export/redraft inputs (`run_ids`, `base_model`, `push_to_hub`, `device`, etc.)

Each schema will provide:

- defaults in one place
- validation rules (ranges, required fields, format checks)
- normalization helpers (for example `""` to unset)

CLI and REST adapt raw inputs into these schemas before calling use cases.

### HuggingFace Auth Service

Add a reusable helper (for example `apps/api/src/infra/clients/ml/hf_auth.py`) that:

- reads `HF_TOKEN` from environment
- performs login once per process
- surfaces explicit errors for missing/invalid credentials

Integration points:

- ingest path when `whisper_hf` is used (private model pull)
- training path when pushing to hub (`--push-to-hub`)

### Model Cache Refactor

Replace single-instance cache behavior with configuration-keyed cache entries.

Key dimensions include:

- device
- whisper source (`whisper_model` vs `whisper_hf`)
- thresholds that influence model behavior

This prevents silent reuse of stale or wrong model instances when users switch model settings across jobs.

## Components and Data Flow

### CLI

`apps/api/src/ports/cli/app.py`:

1. Parse arguments.
2. Build `application/types` schema instances.
3. Use normalized values to call existing use cases/services.

### REST API

`apps/api/src/ports/rest/routes/*.py`:

1. Parse JSON payload.
2. Build same `application/types` schema instances.
3. Call same use cases as CLI.

Because breaking changes are allowed, payloads can be simplified to canonical schema field names.

### Web

`apps/web/src/app/ingest/page.tsx` will expose:

- Whisper model dropdown (`tiny/base/small/medium/large` as supported)
- optional `whisper_hf` input that overrides stock Whisper selection

Web API routes continue to proxy payloads to backend, with field names aligned to canonical request schemas.

### Notebook

Notebook configuration cells remain command-driven through CLI, but names/defaults align with canonical schema fields to keep behavior predictable across interfaces.

## Error Handling

Validation and auth failures become explicit and early:

- invalid thresholds or malformed request values fail before long-running jobs start
- missing or invalid `HF_TOKEN` errors are returned with clear remediation hints
- private-model access and push-to-hub errors are surfaced as first-class failures

Channel-specific behavior:

- CLI: rich error output and debug context
- REST: structured JSON error response
- notebook: command failure with readable backend/CLI cause

## Testing Strategy

1. Add unit tests for `application/types` validation, defaults, and normalization.
2. Extend CLI tests to assert mapping from flags to canonical schemas.
3. Expand REST tests to cover ingest/export/redraft request validation and mapping.
4. Add model-cache tests for keying behavior (same config reuse, changed config reload).
5. Add HF auth tests (missing token, valid token, login-once behavior).
6. Keep web/notebook consistency checks lightweight but explicit (payload field parity and expected defaults).

## Migration and Rollout

1. Introduce shared schemas and wire CLI/REST to them.
2. Add HF auth helper and integrate ingest + training.
3. Refactor cache keying.
4. Update web ingest UI and web proxy payload mapping.
5. Align notebook config names/defaults.
6. Update docs for new canonical payload/flag expectations.

## Acceptance Criteria

1. Web ingest can select model via Whisper dropdown and optional HF override.
2. Web-triggered ingest and training support HuggingFace auth via server env token.
3. CLI, REST, and notebook use one canonical input contract and default set.
4. Cache behavior is deterministic across model changes.
5. Tests cover schema validation, auth integration points, and route/CLI mapping.
6. No dead code introduced; modified modules remain lint/test clean.
