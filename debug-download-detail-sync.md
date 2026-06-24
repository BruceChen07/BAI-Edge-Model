[OPEN] Download detail page and realtime sync debugging

## Session
- Session ID: download-detail-sync
- Started At: 2026-06-24
- Scope: investigate download detail page load failure and missing realtime status/progress updates

## Symptoms
- Download action succeeds or creates a task, but no detail information is visible afterward.
- Progress, status, file information, and error messages do not refresh on the UI.

## Hypotheses
1. Detail API response shape no longer matches the frontend contract.
2. Frontend requests the wrong task identifier or route param when opening the detail view.
3. Realtime refresh logic is not polling/subscribing correctly after task creation.
4. Backend task state changes are not persisted or not exposed in detail/list endpoints.
5. Frontend state normalization drops fields required by the detail panel.

## Plan
1. Locate download feature frontend/backend code paths and current tests.
2. Add instrumentation only at the first logical code change points.
3. Reproduce the issue with runtime evidence.
4. Confirm root cause from logs, then apply minimal fix.
5. Add focused regression tests and verify diagnostics.

## Evidence
- Pre-fix evidence 1: `POST /api/v1/download/pull` with `source=auto` and successful Ollama mock returned `job_id = null`, while `download_jobs` row count remained `0`.
- Pre-fix evidence 2: fallback source flow completed the persisted job inside the same HTTP request before the API returned; the frontend only subscribed after `onSuccess`, so it missed all SSE events emitted during the blocking request.
- Frontend inspection confirmed the page only tracked `activeModel` and inferred "latest job" from the list, without querying `/download/jobs/{id}` for a selected task.

## Root Cause
1. The Ollama success branch never created a persisted download job, so the UI had no job detail to load.
2. The pull API executed the full download synchronously, so the frontend subscribed too late to receive live progress.
3. The frontend lacked a task-detail query keyed by `job_id`, so detail rendering depended on best-effort list matching instead of explicit detail loading.

## Fix
- Backend now creates a persisted job immediately and returns `job_id` with `status=accepted`.
- Download execution runs in a background thread, updating the same job record and broadcasting progress on both `job_id` and model channels.
- Added job-scoped SSE endpoint: `/api/v1/download/jobs/{job_id}/progress`.
- Frontend now subscribes by `job_id`, polls explicit job detail data, and renders full task detail including bytes, timestamps, output path, and backend errors.

## Validation
- Backend: `python -m pytest tests/test_download_phase3.py` -> `32 passed`
- Frontend: `npm test -- --run src/pages/DownloadPage.test.tsx` -> `2 passed`
- Diagnostics: edited backend/frontend files report no IDE diagnostics.
