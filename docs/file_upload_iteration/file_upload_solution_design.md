# File Upload Processing Solution Design

Status: Approved and implemented
Owner: GPT-5.4 / User
Last Updated: 2026-06-24
Scope: chat-facing user file upload validation, preprocessing, backend acceptance, test recording, and iteration traceability

## 1. Background

The project already supports knowledge-base file upload through `POST /api/v1/knowledge-bases/{id}/files/upload`, but the current implementation is not enough for a user-facing general file upload workflow:

- There is no unified single-file size threshold.
- There is no centralized whitelist strategy shared by frontend and backend.
- There is no model capability gate that blocks upload when the selected model is not multimodal.
- Frontend upload components currently rely on local `accept` filters and direct mutation calls, but they do not perform complete pre-validation or image preprocessing.
- Current backend ingest flow reads the entire file and persists it directly after deduplication; it does not expose a user-oriented validation contract for chat uploads.

This design introduces a complete upload solution before code implementation.

## 2. Goals

### 2.1 Functional Goals

- Block oversize files before backend transfer.
- Block unsupported file extensions consistently on frontend and backend.
- Block file upload globally when the selected model does not support multimodal input.
- Preprocess accepted files before backend submission:
  - normalize extension and MIME metadata
  - compress image files when needed
  - keep non-image files unchanged except metadata normalization
- Return user-friendly Chinese error messages for all common failures.

### 2.2 Engineering Goals

- Maintain a single source of truth for upload policy.
- Make model capability checks reusable across chat and knowledge-base upload entry points.
- Add local documents for design review, test ledger, and iteration logs.
- Keep all records under a fixed project path for traceability.

## 3. Non-Goals

- This phase does not change OCR or document parsing quality.
- This phase does not add cloud storage.
- This phase does not implement streaming upload or chunked resumable upload.
- This phase does not change LLM inference logic itself beyond capability gating.

## 4. Current-State Analysis

### 4.1 Existing Backend Upload Flow

Current backend upload entry:

- `backend/app/main.py` -> `POST /api/v1/knowledge-bases/{kb_id}/files/upload`
- `backend/app/services/ingest_service.py` -> reads file bytes, deduplicates, stores original file, extracts text, inserts `documents` and `document_chunks`

Current gaps:

- no central file size rule
- no explicit extension whitelist enforcement in backend upload service
- no model capability verification in upload path
- no standardized error model for user-facing upload failures

### 4.2 Existing Frontend Upload Flow

Current upload entry points:

- `frontend/src/pages/KnowledgeBaseManagePage.tsx`
- `frontend/src/components/knowledgeBase/CreateKnowledgeBaseModal.tsx`

Current gaps:

- `accept` attribute is not enough for security or correctness
- no file size validation
- no model capability check before upload
- no preprocessing/compression step
- no upload policy abstraction shared between components

### 4.3 Existing Model Metadata Gaps

Current local model structure (`frontend/src/services/api.ts -> ModelInfo`) does not include a dedicated upload capability field.

Current backend `/api/v1/models` returns enriched model metadata but does not expose:

- `supports_file_upload`
- `supports_multimodal`
- `supported_upload_types`

This makes it impossible to perform reliable UI blocking based on model capability.

## 5. Proposed Architecture

## 5.1 High-Level Flow

1. User selects a file in chat or knowledge-base upload UI.
2. Frontend loads current selected model metadata.
3. Frontend runs upload policy validation:
   - model capability check
   - file extension whitelist check
   - single-file size check
4. If file is an image and passes validation, frontend runs preprocessing:
   - decode image
   - normalize orientation
   - resize/compress if above configured dimension or byte threshold
5. Frontend submits sanitized file plus metadata to backend.
6. Backend re-validates:
   - extension
   - MIME
   - size
   - model capability context when the endpoint is model-bound
7. Backend stores original or processed payload, then continues existing ingest/parser flow.
8. UI shows success, validation error, or repair guidance.

## 5.2 Core Components

### Frontend

- `uploadPolicy.ts`
  - central constants and helpers
- `uploadPreprocess.ts`
  - image normalization and compression helpers
- `modelCapability.ts`
  - interprets backend capability fields
- `UploadCapabilityModal.tsx`
  - unified modal for model capability rejection
- integration into:
  - `ChatPage.tsx`
  - `KnowledgeBaseManagePage.tsx`
  - `CreateKnowledgeBaseModal.tsx`

### Backend

- upload policy constants module
- upload validation exception model
- capability enrichment in `/api/v1/models`
- ingest service validation layer
- optional dedicated preprocessing metadata persistence fields

### Documentation / Tracking

- `docs/file_upload_iteration/file_upload_solution_design.md`
- `docs/file_upload_iteration/file_upload_iteration_log.md`
- `docs/file_upload_iteration/file_upload_test_ledger.md`

## 6. Upload Policy Design

## 6.1 Single File Size Threshold

Recommended initial threshold:

- image files: 10 MB
- document files: 25 MB
- all single files hard ceiling: 25 MB

Reasoning:

- enough for common screenshots, PDFs, DOCX, and markdown/text files
- low enough to avoid browser memory spikes on personal laptops
- aligned with local-first usage patterns

Policy constants:

- `MAX_UPLOAD_BYTES_IMAGE = 10 * 1024 * 1024`
- `MAX_UPLOAD_BYTES_DOCUMENT = 25 * 1024 * 1024`
- `MAX_UPLOAD_BYTES_HARD = 25 * 1024 * 1024`

User-facing error example:

- `文件超过大小限制：当前文件 31.4 MB，允许的最大大小为 25 MB。请压缩后重试。`

## 6.2 Allowed Extension Whitelist

Recommended whitelist:

- documents: `.pdf`, `.doc`, `.docx`, `.txt`, `.md`, `.xlsx`, `.pptx`
- images: `.png`, `.jpg`, `.jpeg`, `.webp`

Optional future extension:

- `.csv`
- `.gif`

Blocked by default:

- executable and archive types: `.exe`, `.bat`, `.cmd`, `.ps1`, `.zip`, `.rar`, `.7z`
- unsupported office/image types not yet covered by parser path

Validation rule:

- frontend validates by extension first
- backend validates by extension + MIME
- backend is the final authority

User-facing error example:

- `不支持该文件类型：仅支持 PDF、DOC、DOCX、TXT、MD、XLSX、PPTX、PNG、JPG、JPEG、WEBP。`

## 6.3 Model Capability Gate

New backend capability fields for each model:

- `supports_multimodal: boolean`
- `supports_file_upload: boolean`
- `supported_upload_types: string[]`
- `capability_source: "llmfit" | "catalog" | "manual" | "inferred"`

Default rule:

- if model `use_case == "multimodal"` then `supports_multimodal = true`
- otherwise `false`

Business rule:

- If user selects a non-multimodal model in a chat upload entry, all file uploads are blocked globally.
- UI shows a modal with:
  - current model name
  - reason: current model does not support file upload
  - recommended multimodal alternatives
  - quick switch action

User-facing modal copy:

- Title: `当前模型不支持文件上传`
- Content: `你当前选择的大模型不具备多模态能力，无法解析图片或附件内容。请切换到支持文件上传的多模态模型后再继续。`

## 7. Frontend Validation Logic

Validation order:

1. Ensure a model is selected.
2. Check model capability.
3. Check extension whitelist.
4. Check file size threshold.
5. For image files, load metadata and estimate post-compression feasibility.
6. If all pass, enter preprocessing.

Shared helper API:

```ts
validateUploadCandidate({
  file,
  model,
  scenario: "chat" | "knowledge_base",
})
```

Return shape:

```ts
type UploadValidationResult = {
  ok: boolean
  code?: "MODEL_UNSUPPORTED" | "INVALID_EXTENSION" | "FILE_TOO_LARGE"
  message?: string
}
```

Integration points:

- Chat global attachment entry
- Knowledge base upload button
- Knowledge base creation modal upload list

## 8. File Preprocessing Design

## 8.1 Non-Image Files

- preserve file bytes
- normalize file name extension to lowercase
- normalize MIME fallback metadata

## 8.2 Image Files

Processing steps:

1. Read via `FileReader`
2. Decode to `ImageBitmap` or `HTMLImageElement`
3. Fix EXIF orientation if available
4. Resize if width or height exceeds configured threshold
5. Compress to JPEG/WebP depending on source type and browser support
6. If compressed result is larger than original, keep original

Recommended initial constraints:

- max image long edge: 2048 px
- target image upload size: <= 4 MB when compression is possible
- target quality: 0.82

Output:

- new `File` object
- preprocessing metadata:
  - original size
  - processed size
  - compression ratio
  - original mime
  - processed mime

## 8.3 Safety Rules

- never preprocess PDF or Office documents on frontend
- never mutate user file names except extension normalization
- never upload both original and processed version simultaneously

## 9. Backend Validation and Processing

## 9.1 Backend Validation Responsibilities

Backend must always re-check:

- file size
- extension whitelist
- MIME consistency
- empty file
- kb existence

For model-bound endpoints in later chat upload phase, backend must also check:

- selected model ID/name exists
- selected model supports upload

## 9.2 Backend Error Model

Introduce standardized error codes:

- `UPLOAD_FILE_TOO_LARGE`
- `UPLOAD_UNSUPPORTED_EXTENSION`
- `UPLOAD_EMPTY_FILE`
- `UPLOAD_MODEL_NOT_SUPPORTED`
- `UPLOAD_PERMISSION_DENIED`
- `UPLOAD_PREPROCESS_FAILED`

API response pattern:

```json
{
  "code": 400,
  "message": "当前模型不支持文件上传，请切换到多模态模型后重试。",
  "data": {
    "error_code": "UPLOAD_MODEL_NOT_SUPPORTED",
    "repair_action": "switch_model"
  }
}
```

## 9.3 Ingest Flow Changes

Before current `IngestService.upload()` persistence logic, add:

- `validate_upload_policy(file_name, mime_type, size_bytes)`
- optional `validate_model_upload_capability(model_name)` for model-bound usage

After validation:

- continue deduplication
- continue file persistence
- continue parser extraction

## 10. Model Capability Metadata Design

Current `/api/v1/models` response will be extended with:

- `supports_multimodal`
- `supports_file_upload`
- `supported_upload_types`
- `capability_source`

Derivation priority:

1. explicit catalog metadata
2. llmfit `use_case == multimodal`
3. model-name keyword inference
4. fallback false

Name-based inference examples:

- likely multimodal:
  - contains `vision`
  - contains `vl`
  - contains `llava`
  - contains `omni`
- otherwise default false

## 11. Exception Handling Mechanism

Frontend error handling:

- inline upload rejection message for file-level errors
- modal for model capability rejection
- retry button for transient processing failures

Backend error handling:

- convert validation failures to stable API errors
- log technical details in backend logs
- expose simplified Chinese message to frontend

Common scenarios:

- port or network failure during upload
- OCR parser unavailable for image extraction
- browser memory pressure on very large images
- duplicate file detection

## 12. Development Schedule

### Phase 0: Requirement Confirmation

- Time: T+0.5 day
- Deliverables:
  - reviewed design document
  - approved upload policy thresholds
  - approved whitelist and capability rules

### Phase 1: Frontend Policy and Preprocess

- Time: T+1.5 day
- Deliverables:
  - upload policy helpers
  - image preprocessing utilities
  - capability rejection modal
  - integration into upload entry points

### Phase 2: Backend Validation and Capability Metadata

- Time: T+1.5 day
- Deliverables:
  - backend whitelist/size validation
  - `/api/v1/models` capability enrichment
  - stable upload error codes

### Phase 3: Joint Debugging and Regression

- Time: T+1 day
- Deliverables:
  - end-to-end verification
  - test ledger update
  - iteration log update

### Phase 4: Final Handover

- Time: T+0.5 day
- Deliverables:
  - final implementation summary
  - test report
  - risk list and follow-up items

Estimated total: 4 to 5 working days

## 13. Testing Strategy

### 13.1 Frontend Cases

- valid multimodal model + valid PDF under limit
- non-multimodal model + image upload blocked
- unsupported extension blocked
- oversize file blocked
- large image compressed successfully
- image preprocessing fallback keeps original when compression is ineffective

### 13.2 Backend Cases

- valid upload accepted
- unsupported extension rejected
- oversize upload rejected
- empty file rejected
- duplicate upload deduplicated
- parser failure returns readable error

### 13.3 Regression Scope

- knowledge base upload flow
- create knowledge base with files flow
- local model switching flow
- chat page model selector flow

## 14. Risks and Mitigations

- Risk: image preprocessing causes browser memory spikes
  - Mitigation: hard-stop large image decode, compress only within threshold, fallback to original
- Risk: model capability inference is inaccurate for some custom names
  - Mitigation: add catalog metadata override and capability source field
- Risk: backend parser supports more or fewer formats than frontend whitelist
  - Mitigation: maintain shared whitelist constants with mirrored tests
- Risk: user confusion between knowledge-base upload and chat attachment upload
  - Mitigation: separate UI copy and scenario-specific messages

## 15. Local Traceability Plan

All implementation and verification records must be maintained under:

- `docs/file_upload_iteration/`

Files:

- `file_upload_solution_design.md`
- `file_upload_iteration_log.md`
- `file_upload_test_ledger.md`

Optional evidence folder after implementation:

- `docs/file_upload_iteration/evidence/`
  - screenshots
  - captured logs
  - validation error samples

## 16. Review Gate

Coding started after user approval on 2026-06-24 and the approved scope in this document has been implemented.

Approval checklist:

- size thresholds approved
- extension whitelist approved
- multimodal capability gate approved
- frontend preprocessing strategy approved
- local record path approved

## 17. Proposed Implementation Scope After Approval

- frontend shared upload policy helpers
- frontend image preprocessing utilities
- backend upload validation layer
- model capability enrichment in `/api/v1/models`
- upload-related tests
- local iteration and test records updates
