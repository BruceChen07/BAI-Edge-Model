# Knowledge Base Management — Design Document

> **Status**: IMPLEMENTED (P0 + P1 + P2)
> **Date**: 2026-06-23
> **Author**: AI Agent
> **Project**: BAI-Edge-Model

---

## 1. Current State Audit

### 1.1 What Already Exists

| Layer | Component | Status |
|-------|-----------|--------|
| DB | `knowledge_bases` table | OK — id, name, description, path, status, file_count, chunk_count, timestamps |
| DB | `documents` table | OK — id, kb_id, file_name, file_ext, mime_type, file_size, storage_path, sha256, parse/ocr/index status, timestamps |
| DB | `document_chunks` table | OK — id, document_id, kb_id, chunk_index, content, content_hash, token_count, vector_ref, timestamps |
| DB | `parse_tasks` table | OK — task tracking for ingest |
| Backend | `POST /knowledge-bases` | OK — create KB |
| Backend | `GET /knowledge-bases` | OK — list all KBs |
| Backend | `GET /knowledge-bases/{id}` | OK — get single KB |
| Backend | `PUT /knowledge-bases/{id}` | OK — update KB (name, description) |
| Backend | `DELETE /knowledge-bases/{id}` | OK — delete KB + cascading files/chunks |
| Backend | `POST /knowledge-bases/{id}/files/upload` | OK — upload + parse + chunk |
| Backend | `GET /knowledge-bases/{id}/files` | OK — list files |
| Backend | `DELETE /knowledge-bases/{id}/files/{fid}` | OK — delete single file |
| Backend | `POST /knowledge-bases/{id}/reindex` | OK — background reindex task with real chunk rebuild |
| Backend | `GET /knowledge-bases/{id}/chunks` | OK — paginated chunk list with `document_id` filter |
| Backend | `GET /knowledge-bases/{id}/stats` | OK — storage size, file count, chunk count, token count |
| Frontend | ChatPage KB selector | OK — multi-select dropdown |
| Frontend | ChatPage "Create KB" modal | OK — name + description + file upload |
| Frontend | KnowledgeBaseManagePage | OK — search, sort, detail tabs, export, reindex |
| Frontend | AdminPage KB count | OK — statistic card only |

### 1.2 Historical Gaps

| Gap | Previous Severity | Current Status |
|-----|-------------------|----------------|
| No dedicated KB management page | High | Fixed |
| No KB rename / delete / detail view in UI | High | Fixed |
| No file list + delete per KB in UI | High | Fixed |
| No chunk inspection UI | Medium | Fixed |
| `reindex` backend is a stub (no actual re-index logic) | Medium | Fixed |
| No KB storage size shown | Low | Fixed |
| No file count / chunk count update on delete_file (partially fixed) | Low | Fixed |

---

## 2. Proposed Architecture

### 2.1 New Page: `KnowledgeBaseManagePage`

A dedicated management page accessible from the main navigation, parallel to Chat / Admin / Catalog / Downloads.

```
Navigation Bar
├── Home (Chat)
├── Knowledge Bases   <-- NEW
├── Model Catalog
├── Downloads
└── Admin
```

### 2.2 Page Layout

```
┌──────────────────────────────────────────────────┐
│  Knowledge Base Management          [+ Create KB] │
│                                                    │
│  ┌──────────┬──────────┬──────────┬──────────┐    │
│  │ KB Name  │  Files   │  Chunks  │  Status  │    │
│  │  (sort)  │  (sort)  │  (sort)  │ (filter) │    │
│  ├──────────┼──────────┼──────────┼──────────┤    │
│  │ TechDocs │    12    │   2,340  │  ready   │  ... Row: click → detail panel
│  │ Handbook │     3    │     520  │  ready   │  ...
│  │ ...      │   ...    │    ...   │  ...     │  ...
│  └──────────┴──────────┴──────────┴──────────┘    │
│                                                    │
│  [Detail Panel — opens on row click]               │
│  ┌────────────────────────────────────────────┐    │
│  │ Name:  TechDocs           [Rename] [Delete] │    │
│  │ Desc:  Technical docs for...               │    │
│  │ Storage:  /kb/files/kb_xxx/                │    │
│  │ Status:  ready                             │    │
│  │                                            │    │
│  │ Files (12)                    [Upload File] │    │
│  │ ┌──────────────────────────────────────┐    │    │
│  │ │ file_name │ size  │ parse │ [x] del  │    │    │
│  │ │ a.pdf     │ 2.3MB │ done  │          │    │    │
│  │ │ b.docx    │ 1.1MB │ done  │          │    │    │
│  │ └──────────────────────────────────────┘    │    │
│  │                                            │    │
│  │ Chunks (2,340)                  [Reindex]   │    │
│  │ ┌──────────────────────────────────────┐    │    │
│  │ │ doc  │ idx │ content preview...      │    │    │
│  │ │ a.pdf│  0  │ "Chapter 1: Intro..."   │    │    │
│  │ │ a.pdf│  1  │ "Section 1.1: ..."      │    │    │
│  │ └──────────────────────────────────────┘    │    │
│  └────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────┘
```

### 2.3 Component Tree

```
KnowledgeBaseManagePage
├── KBListTable          (sortable, clickable rows)
├── CreateKBModal        (reused from ChatPage, extracted to shared component)
├── KBDetailPanel        (shown on row click)
│   ├── KBInfoSection    (name, desc, status, storage, rename/delete actions)
│   ├── KBFileSection    (file list table + upload button + delete per file)
│   └── KBChunkSection   (chunk list with pagination + reindex button)
```

---

## 3. Backend Changes

### 3.1 Fix `reindex` Endpoint

Current stub:
```python
@app.post("/api/v1/knowledge-bases/{kb_id}/reindex")
def reindex_knowledge_base(kb_id: str):
    task = task_service.create("reindex", kb_id, status="done", progress=1.0)
    return ApiResponse(data=task.model_dump())
```

Proposed fix — actually re-runs the chunking pipeline:
```python
POST /api/v1/knowledge-bases/{kb_id}/reindex
→ Deletes all existing chunks for this KB
→ Re-reads stored file content for each document
→ Re-extracts text via ParserService
→ Re-chunks and inserts
→ Updates KB chunk_count
→ Returns task with real progress
```

**Risk**: Large KBs may take time; recommend running as background task with progress updates.

### 3.2 Add Pagination to Chunk Listing

```
GET /api/v1/knowledge-bases/{kb_id}/chunks?document_id=&offset=0&limit=50
```

Add optional `document_id` filter to view chunks of a specific file.

### 3.3 Add KB Stats Endpoint (Optional)

```
GET /api/v1/knowledge-bases/{kb_id}/stats
→ { total_size_bytes, file_count, chunk_count, token_count }
```

---

## 4. Frontend Feature Checklist

| # | Feature | Priority | Estimate |
|---|---------|----------|----------|
| 1 | Extract `CreateKnowledgeBaseModal` as shared component | P0 | Small |
| 2 | New `KnowledgeBaseManagePage` with route `/knowledge-bases` | P0 | Medium |
| 3 | KB list table with sortable columns | P0 | Small |
| 4 | KB detail panel (info + rename + delete) | P0 | Medium |
| 5 | File list in detail panel with delete per file | P0 | Small |
| 6 | Upload file to existing KB (in detail panel) | P0 | Small |
| 7 | Chunk list with pagination and per-document filter | P1 | Medium |
| 8 | Reindex button + progress tracking | P1 | Medium |
| 9 | KB delete with confirmation dialog | P0 | Small |
| 10 | Navigation entry "Knowledge Bases" | P0 | Small |
| 11 | i18n: all labels in zh-CN + en-US | P0 | Small |

---

## 5. Data Flow

### 5.1 KB List Load
```
User opens /knowledge-bases
→ GET /api/v1/knowledge-bases
→ Render KBListTable
```

### 5.2 KB Detail
```
User clicks a KB row
→ GET /api/v1/knowledge-bases/{id}  (KB info)
→ GET /api/v1/knowledge-bases/{id}/files  (file list)
→ Show KBDetailPanel
```

### 5.3 Chunk Inspection
```
User switches to "Chunks" tab in detail panel
→ GET /api/v1/knowledge-bases/{id}/chunks?document_id=&offset=0&limit=50
→ Render chunk list with pagination
```

### 5.4 Delete KB
```
User clicks "Delete" → confirmation dialog → confirm
→ DELETE /api/v1/knowledge-bases/{id}
→ Invalidate queries → close detail panel → refresh list
```

### 5.5 Reindex KB
```
User clicks "Reindex" → confirmation dialog → confirm
→ POST /api/v1/knowledge-bases/{id}/reindex
→ Poll task status via GET /api/v1/tasks
→ Show progress bar → auto-refresh chunk list on complete
```

---

## 6. Implementation Plan (Phased)

### Phase 1 — Core Management (P0)
- Extract shared `CreateKnowledgeBaseModal`
- New `KnowledgeBaseManagePage` with KB list table
- KB detail panel with rename, delete
- File list in detail with upload + delete per file
- Navigation entry + i18n
- **Tests**: render page, create KB, delete KB, upload file, delete file

### Phase 2 — Inspection & Fixes (P1)
- Fix backend `reindex` endpoint (real implementation)
- Chunk list with pagination + document filter
- Reindex button with progress tracking
- **Tests**: reindex flow, chunk pagination, progress polling

### Phase 3 — Polish (P2)
- KB storage size endpoint + display
- Sorting by file_count / chunk_count / created_at
- Search/filter KBs by name
- KB export (reuse existing export service)

---

## 6.1 Implementation Outcome

### P0 Delivered
- Extracted shared `CreateKnowledgeBaseModal`
- Added route `/knowledge-bases` and navigation entry
- Implemented KB list, detail tabs, rename, delete, file upload, file delete
- Added bilingual labels in `zh-CN` and `en-US`

### P1 Delivered
- Implemented real backend reindex flow with background task progress polling
- Added paginated chunk inspection with optional `document_id` filtering
- Connected reindex progress UI and automatic data refresh after completion

### P2 Delivered
- Added KB stats endpoint and UI display for storage size and token count
- Added KB table search, sorting, and status filtering
- Added Markdown / DOCX / XLSX export actions in the management page
- Added screenshot-like OCR text grounding improvements for source-oriented Q&A
- Added evidence-first answering for paper/source lookup questions

### Validation Result
- Backend: `python -m pytest tests/test_api.py` -> `8 passed`
- Frontend: `npm run lint` -> passed
- Frontend: `npm test -- --run` -> `14 passed`
- Frontend: `npm run build` -> passed
- Backend regression: screenshot-style OCR source question now returns the cited paper title, year, author, and link deterministically

---

## 7. Dependencies & Licenses

All dependencies are already in the project:
- Frontend: React, Ant Design, @tanstack/react-query, react-router-dom — all MIT
- Backend: FastAPI, Python stdlib — MIT / PSF
- No new third-party dependencies required.

---

## 8. API Summary

| Method | Path | Phase | Notes |
|--------|------|-------|-------|
| `GET` | `/api/v1/knowledge-bases` | existing | — |
| `GET` | `/api/v1/knowledge-bases/{id}` | existing | — |
| `PUT` | `/api/v1/knowledge-bases/{id}` | existing | — |
| `DELETE` | `/api/v1/knowledge-bases/{id}` | existing | — |
| `POST` | `/api/v1/knowledge-bases` | existing | — |
| `POST` | `/api/v1/knowledge-bases/{id}/files/upload` | existing | — |
| `GET` | `/api/v1/knowledge-bases/{id}/files` | existing | — |
| `DELETE` | `/api/v1/knowledge-bases/{id}/files/{fid}` | existing | — |
| `POST` | `/api/v1/knowledge-bases/{id}/reindex` | P1 (fix) | real reindex logic |
| `GET` | `/api/v1/knowledge-bases/{id}/chunks?document_id=&offset=&limit=` | P1 (fix) | add pagination + filter |
| `GET` | `/api/v1/knowledge-bases/{id}/stats` | P2 | storage and token statistics |

---

## 9. Test Plan

| Scenario | Test Type | Phase |
|----------|-----------|-------|
| KB list renders correctly | Unit (frontend) | P1 |
| Create KB via modal | Integration (frontend) | P1 |
| Delete KB with confirmation | Unit (frontend) | P1 |
| Rename KB | Integration (frontend) | P1 |
| Upload file to existing KB | Integration (frontend + backend) | P1 |
| Delete file from KB | Unit (frontend + backend) | P1 |
| Chunk list with pagination | Unit (frontend) | P2 |
| Reindex with progress | Integration (backend) | P2 |
| Cross-page: ChatPage KB selector updates after manage page changes | E2E (manual) | P2 |

---

## 10. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Reindex on large KBs is slow | Background task with progress polling; warn user before starting |
| KB delete is irreversible | Confirmation dialog with KB name entry required |
| File upload to wrong KB | Show KB name in upload area; disable upload when no KB selected |
| State inconsistency between ChatPage and ManagePage | Use react-query cache invalidation (`queryKey: ["knowledge-bases"]`) |

---

## 11. Delivery Checklist

- [x] Page layout and UX flow implemented
- [x] Backend reindex design implemented
- [x] Phase scope completed for P0, P1, and P2
- [x] No new third-party dependencies introduced
- [x] Chunk pagination design implemented
