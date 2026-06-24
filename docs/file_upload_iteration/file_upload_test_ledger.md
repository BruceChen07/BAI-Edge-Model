# File Upload Test Ledger

Status: Active
Feature: user file upload processing
Record Path: docs/file_upload_iteration/

## Usage

- Record every executed case after implementation starts.
- Keep raw error messages, simplified UI messages, and fix status together.
- Save screenshots and logs under `docs/file_upload_iteration/evidence/`.

## Test Environment

| Item | Value |
| --- | --- |
| OS | Windows 11 |
| Browser | Vitest jsdom; manual browser screenshot capture pending |
| Backend Commit | Pending |
| Frontend Commit | Pending |
| Test Date | 2026-06-24 |
| Tester | GPT-5.4 |

## Case Matrix

| Case ID | Scenario Type | Preconditions | Input Data | Expected Result | Actual Result | Status | Error Message | Fix Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| FU-001 | Normal | multimodal model selected | valid `sample.pdf`, 2 MB | upload succeeds | not executed in this round | Pending | — | Open | Pending |
| FU-002 | Normal | multimodal model selected | valid `image.png`, 3 MB | preprocess + upload succeeds | frontend helper successfully normalized and preprocessed valid image input | Passed | — | Closed | `evidence/frontend_test_log_20260624.txt` |
| FU-003 | Exception | non-multimodal model selected | `image.png` | upload blocked before backend | frontend validator blocked unsupported model; backend also returned 400 when `model_name=gemma4:4b` | Passed | `当前模型不支持文件上传，请切换到支持文件上传的多模态模型后重试。` | Closed | `evidence/backend_test_log_20260624.txt`, `evidence/frontend_test_log_20260624.txt` |
| FU-004 | Exception | multimodal model selected | `virus.exe` | extension rejected | backend returned 400 for unsupported extension | Passed | `不支持该文件类型：仅支持 PDF、DOC、DOCX、TXT、MD、XLSX、PPTX、PNG、JPG、JPEG、WEBP。` | Closed | `evidence/backend_test_log_20260624.txt` |
| FU-005 | Exception | multimodal model selected | `oversize.pdf`, 30 MB | size rejected | frontend oversize image check passed; backend returned 400 for `oversize.pdf` over 25 MB | Passed | `文件超过大小限制：当前文件 26.0 MB，允许的最大大小为 25 MB。请压缩后重试。` | Closed | `evidence/backend_test_log_20260624.txt`, `evidence/frontend_test_log_20260624.txt` |
| FU-006 | Exception | multimodal model selected | damaged image file | preprocess failure with readable message | not executed in this round | Pending | Pending | Open | Pending |
| FU-007 | Exception | multimodal model selected | duplicate file | deduplicated or blocked with clear response | existing ingest dedup path remains available but upload policy-specific retest not executed in this round | Pending | Pending | Open | Pending |
| FU-008 | Regression | KB upload existing path | `notes.docx` | old upload path still works | backend regression `test_docx_xlsx_ingest_and_delete` passed | Passed | — | Closed | `evidence/backend_test_log_20260624.txt` |
| FU-009 | Regression | create KB with files | two valid files | KB create + upload succeeds | not executed in this round | Pending | — | Open | Pending |
| FU-010 | Regression | OCR image upload | `ocr-test.jpg` | image path remains parseable | backend OCR grounding regression test passed after upload changes | Passed | — | Closed | `evidence/backend_test_log_20260624.txt` |
| FU-011 | Normal | existing chat session, multimodal model selected | valid `chat-note.txt`, 1 KB | chat attachment upload succeeds and returns `attachment_id` | backend test passed; upload returned attachment payload with extracted preview and `uploaded` status | Passed | — | Closed | `evidence/backend_test_log_20260624.txt` |
| FU-012 | Exception | existing chat session, non-multimodal model selected | `evidence.png` | chat attachment upload blocked before or at backend | backend returned HTTP 400 for `model_name=gemma4:4b` | Passed | `当前模型不支持文件上传，请切换到支持文件上传的多模态模型后重试。` | Closed | `evidence/backend_test_log_20260624.txt` |
| FU-013 | Regression | uploaded attachment linked during send | `attachment_ids` + chat prompt | `/chat/completions` binds attachment to user message | backend test passed; attachment records moved to `linked` and were attached to the saved user message | Passed | — | Closed | `evidence/backend_test_log_20260624.txt` |
| FU-014 | Regression | session contains linked attachment | query session detail | message payload includes attachment list | backend session detail test passed; user message returned linked `summary.txt` and `diagram.png` attachments | Passed | — | Closed | `evidence/backend_test_log_20260624.txt` |
| FU-015 | Regression | uploaded chat attachment exists | download by attachment id | file download succeeds with original filename | backend download endpoint returned original bytes and filename | Passed | — | Closed | `evidence/backend_test_log_20260624.txt` |
| FU-016 | Regression | uploaded but unsent chat attachment exists | delete by attachment id | attachment metadata and stored file are removed | backend delete endpoint passed; subsequent download returned 404 | Passed | — | Closed | `evidence/backend_test_log_20260624.txt` |
| FU-017 | Frontend | multimodal model selected in chat page | select valid file then send | pending attachment list renders and `attachment_ids` are submitted | Vitest passed; pending attachment renders, chat API receives `attachment_ids`, assistant reply and download action render | Passed | — | Closed | `evidence/frontend_test_log_20260624.txt` |
| FU-018 | Frontend | stored local chat history with attachments | reload page | message-side attachment list restores from snapshot or session payload | Vitest passed; pending attachment and linked message attachment restored from local snapshot | Passed | — | Closed | `evidence/frontend_test_log_20260624.txt` |

## Error Log Snapshot Template

### Case ID: FU-003

- Raw backend message: `当前模型不支持文件上传，请切换到支持文件上传的多模态模型后重试。`
- Simplified frontend message: `当前模型不支持文件上传`
- Root cause: selected model lacked `supports_file_upload` capability and upload path previously had no hard block
- Fix applied: added capability fields to `/api/v1/models`, frontend modal interception, and backend `model_name` verification
- Retest result: passed

### Case ID: FU-004

- Raw backend message: `不支持该文件类型：仅支持 PDF、DOC、DOCX、TXT、MD、XLSX、PPTX、PNG、JPG、JPEG、WEBP。`
- Simplified frontend message: same as backend
- Root cause: upload path previously trusted UI `accept` filter and lacked centralized whitelist validation
- Fix applied: added shared whitelist constants and backend extension/MIME validation
- Retest result: passed

### Case ID: FU-005

- Raw backend message: `文件超过大小限制：当前文件 26.0 MB，允许的最大大小为 25 MB。请压缩后重试。`
- Simplified frontend message: same as backend
- Root cause: no centralized size threshold or backend fallback guard
- Fix applied: added frontend size checks and backend hard ceiling validation
- Retest result: passed

## Summary Dashboard

| Metric | Value |
| --- | --- |
| Total Cases | 18 |
| Passed | 14 |
| Failed | 0 |
| Blocked | 0 |
| Pending | 4 |

## Evidence Checklist

- UI rejection screenshot
- capability-block modal screenshot
- oversize file rejection screenshot
- unsupported extension screenshot
- processed image size comparison log
- backend structured error log
- backend automated test log: `evidence/backend_test_log_20260624.txt`
- frontend automated test log: `evidence/frontend_test_log_20260624.txt`
