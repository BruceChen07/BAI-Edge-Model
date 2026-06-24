# File Upload Iteration Log

Status: Active
Feature: user file upload processing
Owner: GPT-5.4 / User
Record Path: docs/file_upload_iteration/

## Usage

- Update this file at the end of each phase.
- Record both planned and actual completion.
- Explain deviations with clear root causes.

## Milestones

| Phase | Planned Time | Actual Time | Status | Deliverables | Deviation Reason |
| --- | --- | --- | --- | --- | --- |
| Requirement Review | T+0.5 day | 2026-06-24 | Completed | Approved design scope | — |
| Frontend Validation | T+1.5 day | 2026-06-24 | Completed | shared upload policy, capability modal | — |
| Frontend Preprocess | T+1.5 day | 2026-06-24 | Completed | image compression and normalization | image preprocessing currently targets browser canvas-compatible images only; EXIF-aware rotation deferred |
| Backend Validation | T+1.5 day | 2026-06-24 | Completed | whitelist, size checks, error codes | upload capability rejection uses current selected model name passed from UI; no dedicated chat attachment endpoint yet |
| Capability Metadata | T+0.5 day | 2026-06-24 | Completed | `/api/v1/models` capability fields | — |
| Chat Attachment Planning | T+0.5 day | 2026-06-24 | Completed | implementation plan, scope split, record update | previous round completed backend contract draft only; frontend entry and regression coverage still pending |
| Chat Attachment Backend | T+1 day | 2026-06-24 | Completed | session attachment API, message binding, session detail attachment payload | — |
| Chat Attachment Frontend | T+1 day | 2026-06-24 | Completed | chat upload entry, pending attachment list, message attachment rendering | chose local snapshot persistence for refresh restore; no dedicated session reload UI yet |
| Chat Attachment Regression | T+0.5 day | 2026-06-24 | Completed | backend and frontend tests, evidence logs, ledger update | targeted automated verification completed; manual browser screenshots still optional |
| Integration Test | T+1 day | 2026-06-24 | Completed | regression results and screenshots | automated logs completed; UI screenshots need manual supplement if required for release archive |
| Handover | T+0.5 day | 2026-06-24 | In Progress | final report and docs | waiting for user review of implemented phase |

## Chronological Log

### 2026-06-24

- Stage: Design
- Planned:
  - inspect current upload flow
  - define validation rules
  - define preprocessing strategy
  - define local records path
- Actual:
  - completed current-state review of frontend and backend upload paths
  - confirmed lack of centralized upload policy and model capability gate
  - created design document and record skeletons under `docs/file_upload_iteration/`
- Notes:
  - no business code changes started in this stage
  - waiting for user review before implementation

### 2026-06-24

- Stage: Implementation
- Planned:
  - add centralized upload policy for frontend and backend
  - expose model upload capability fields from `/api/v1/models`
  - block unsupported uploads before backend transfer
  - add backend fallback validation and regression tests
  - record actual test results in local docs
- Actual:
  - added backend upload policy module with extension, size, MIME, and model capability validation
  - extended `/api/v1/models` with `supports_multimodal`, `supports_file_upload`, `supported_upload_types`, and `capability_source`
  - updated knowledge-base upload APIs to carry `model_name` and reject unsupported models in backend
  - added frontend shared upload policy helper, active model persistence, and image preprocessing helper
  - integrated upload validation into `CreateKnowledgeBaseModal` and `KnowledgeBaseManagePage`
  - updated upload hint copy to reflect supported formats and multimodal restrictions
  - added backend regression tests and frontend upload policy unit tests
  - created `docs/file_upload_iteration/evidence/` and stored test command logs
- Problems:
  - initial backend pytest run from repo root failed because Python module path did not include `backend/app`
  - no dedicated chat attachment endpoint exists yet, so current model capability gate is applied to existing knowledge-base related upload entry points
- Fixes:
  - reran backend tests from `backend/` directory using `python -m pytest tests/test_api.py`
  - reused persisted active model selection from chat page to drive upload gating in upload-related UI
- Remaining Risks:
  - multimodal capability inference still depends on `use_case` metadata or model-name keywords for some local models
  - image preprocessing currently omits EXIF-specific orientation correction

### 2026-06-24

- Stage: Chat Attachment Planning
- Planned:
  - verify current backend attachment contract and remaining frontend gaps
  - split delivery into backend regression, frontend entry/rendering, and record update stages
  - define concrete test matrix for upload, bind, render, download, and delete flows
- Actual:
  - confirmed backend draft already contains `chat_attachments` table, DTO extension, upload/delete/download endpoints, and message binding hooks
  - confirmed `ChatPage.tsx`, `api.ts`, and `chatHistoryStorage.ts` still lack attachment-aware state, request payloads, and message rendering
  - defined implementation order as: backend regression first, frontend integration second, automated tests third, final document and evidence update last
- Problems:
  - current frontend refresh restore only depends on `localStorage` snapshot and cannot yet recover message-side attachment rendering
  - automated coverage for the new attachment endpoints and session message attachment payload is still missing
- Fixes:
  - expanded milestone table and prepared this dedicated planning entry before additional code edits
  - aligned next implementation step to preserve traceability between code changes and test ledger updates
- Remaining Risks:
  - image attachments can be uploaded and converted to base64 for model payloads, but multimodal model compatibility still depends on the local Ollama model behavior
  - deleting linked attachments currently has no extra guard; expected behavior must be verified in regression tests

### 2026-06-24

- Stage: Chat Attachment Implementation
- Planned:
  - finish backend regression for chat attachment endpoints and message binding
  - integrate chat-page attachment upload, pending list, request payload wiring, and message bubble rendering
  - persist attachment state into local chat history snapshot for page refresh recovery
- Actual:
  - completed backend regression coverage for upload success, non-multimodal rejection, message binding, session detail attachment payload, and attachment download/delete flow
  - extended frontend `api.ts` with chat attachment types and upload/delete APIs
  - extended `chatHistoryStorage.ts` to persist `pendingAttachments` and per-message `attachments`
  - updated `ChatPage.tsx` with hidden file picker entry, pending attachment panel, send-time `attachment_ids`, optimistic user message flow, and message-side attachment cards with download links
  - updated localized copy for chat attachment labels and helper text
- Problems:
  - first frontend build failed because history snapshot attachments used a looser optional type than live upload API responses
  - initial attachment test run failed due to incomplete `API_BASE` mocking and an Ant Design button accessibility name mismatch
- Fixes:
  - added `toUiAttachment()` normalization to convert persisted snapshot attachments into upload-response-compatible UI objects
  - patched frontend tests to include `API_BASE` mock and use a regex for the rendered send-button accessible name
- Remaining Risks:
  - current refresh recovery relies on local snapshot persistence; chat page still does not fetch historical session details on mount
  - linked attachment deletion remains allowed by backend and may need product-level policy confirmation if historical evidence retention becomes a requirement

### 2026-06-24

- Stage: Chat Attachment Regression
- Planned:
  - rerun backend API regression after attachment tests are added
  - run focused frontend Vitest coverage, then lint and build
  - update evidence logs and ledger with actual pass counts
- Actual:
  - backend `python -m pytest tests/test_api.py` passed with 17/17 tests
  - frontend `vitest` targeted suite passed with 3/3 files and 6/6 tests
  - frontend `npm run lint` passed
  - frontend `npm run build` passed after attachment type normalization fix
  - appended current command outputs and covered checks to `docs/file_upload_iteration/evidence/`
- Problems:
  - no additional business logic defect found after the final verification round
- Fixes:
  - none beyond the previously recorded frontend type normalization and test mock fixes
- Remaining Risks:
  - automated CLI validation does not include manual browser screenshots or real Ollama multimodal runtime verification against a production local model

## Open Questions

- Should `.csv` be included in the first whitelist release?
- Should chat upload and knowledge-base upload share exactly the same size limits?
- Should unsupported non-multimodal models be hidden from upload UI or only blocked with modal guidance?

## Post-Approval Update Template

### YYYY-MM-DD

- Stage:
- Planned:
- Actual:
- Problems:
- Fixes:
- Remaining Risks:
