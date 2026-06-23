# LLMFIT Integration — Phased Implementation Plan

**Project**: BAI-Edge-Model / llmfit Integration  
**Created**: 2026-06-23  
**Status**: Phase 1 In Progress  
**Repository**: https://github.com/BruceChen07/BAI-Edge-Model

---

## Overview

Integrate the [llmfit](https://github.com/AlexsJones/llmfit) CLI tool into the BAI-Edge-Model edge LLM platform to provide hardware-aware model scoring and recommendation. The integration follows a three-phase approach, each with clearly defined deliverables, acceptance criteria, and risk mitigations.

### Architecture Context

```
┌──────────────────────────────────────────────────────┐
│                   FastAPI Backend                      │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────────┐ │
│  │ LlmfitService │◀─│  Ollama Svc │◀─│  Chat Svc    │ │
│  │ (Phase 1)    │  │  (existing) │  │  (existing)  │ │
│  └──────┬───────┘  └─────────────┘  └──────────────┘ │
│         │ fallback                                     │
│  ┌──────┴───────┐                                      │
│  │ ResourceMon  │  (existing psutil-based fallback)    │
│  └──────────────┘                                      │
└──────────────────────────────────────────────────────┘
```

---

## Phase 1: llmfit CLI Adapter & Core API Endpoints

### Objective
Wrap the `llmfit` CLI as a Python service with subprocess execution, JSON parsing, caching, graceful fallback, and REST API exposure.

### Core Tasks

| # | Task | Description | Priority |
|---|------|-------------|----------|
| 1.1 | `LlmfitService` class | Subprocess wrapper, `--json` output parsing, timeout handling | P0 |
| 1.2 | In-memory cache layer | 5-min TTL cache for system profile & recommendations | P0 |
| 1.3 | Graceful fallback | Degrade to `resource_monitor.py` + curated catalog when llmfit unavailable | P0 |
| 1.4 | Docker mode support | Detect and execute llmfit via Docker when `LLMFIT_BINARY=docker` | P1 |
| 1.5 | Alternate key parsing | Handle variant JSON key names (`physical_cores`/`brand`/`memory`/`gpus`) | P1 |
| 1.6 | API endpoints (4) | `GET /system`, `GET /recommend`, `GET /models/{name}`, `POST /cache/refresh` | P0 |
| 1.7 | Unit tests (38 cases) | Mock output parsing, field mapping, cache behavior, error handling, edge cases | P0 |

### Deliverables
- `backend/app/services/llmfit_service.py` — ~430 lines
- `backend/tests/test_llmfit_service.py` — 38 test cases, 9 test classes
- 4 new API endpoints in `backend/app/main.py`
- `llmfit_devlog.md` — development log with daily entries

### Acceptance Criteria
- [ ] All 38 unit tests pass with `pytest -v`
- [ ] API endpoints return valid JSON with correct schema
- [ ] Graceful fallback: service starts normally when llmfit is not installed
- [ ] Cache invalidation works (refresh endpoint, TTL expiry)
- [ ] Timeout handling: llmfit subprocess timeout triggers fallback (no crash)
- [ ] Malformed JSON from llmfit triggers fallback (no crash)

### Test Coverage Matrix

| Test Class | Test Count | Focus |
|------------|-----------|-------|
| TestDataModels | 5 | Dataclass instantiation, defaults |
| TestLlmfitNotInstalled | 4 | Fallback to psutil/catalog |
| TestSystemProfileParsing | 3 | Full system, no GPU, alternate keys |
| TestRecommendationParsing | 7 | Count, scores, fit levels, TPS, filtering, sorting, limit |
| TestCacheBehavior | 5 | Set/get, expiry, clear, system cache hit, refresh |
| TestErrorHandling | 5 | Subprocess error, timeout, invalid JSON, empty, malformed |
| TestDockerMode | 2 | Docker available, not available |
| TestModelInfo | 2 | Get info, cache hit |
| TestEdgeCases | 5 | Single GPU dict, scalar scores, use_case, error classes |

### Risk Mitigation
| Risk | Impact | Mitigation |
|------|--------|------------|
| llmfit not installed | Medium | Graceful fallback to psutil + curated catalog |
| Subprocess timeout | Low | 30s timeout + in-memory cache |
| JSON format change | Low | Alternate key parsing + try/except per field |

---

## Phase 2: Model Catalog & Frontend

### Objective
Build a persistent model catalog database, sync script, and frontend UI for hardware-aware model scoring and recommendation display.

### Core Tasks

| # | Task | Description | Priority |
|---|------|-------------|----------|
| 2.1 | `model_catalog` DB table | SQLite table: model_name, provider, param_size, version, scores, requirements, metadata | P0 |
| 2.2 | DB migration script | `alembic` migration or `init_db` extension to create catalog table | P0 |
| 2.3 | Catalog sync script | Python script: `python -m scripts.sync_model_catalog` — pulls from llmfit DB, updates SQLite | P0 |
| 2.4 | `ModelCatalogService` | CRUD operations, search/filter queries, scoring cache | P0 |
| 2.5 | API endpoints | `GET /catalog`, `GET /catalog/{name}`, `GET /catalog/search?q=`, `POST /catalog/sync` | P0 |
| 2.6 | Frontend `ModelScoringPanel` | React component: model list with scores (Q/S/F/C bars), hardware badge, filter/sort | P1 |
| 2.7 | Frontend `ModelDetailModal` | Detailed model info: memory req., TPS estimate, compatibility, run mode | P1 |
| 2.8 | API client types | TypeScript types for catalog responses, `useCatalogQuery` hook | P0 |
| 2.9 | Unit tests | 20+ tests: DB operations, sync script, API endpoints, service methods | P0 |

### Deliverables
- `backend/app/models/model_catalog.py` — SQLAlchemy model
- `backend/app/services/model_catalog_service.py` — service layer
- `scripts/sync_model_catalog.py` — sync script
- `backend/tests/test_model_catalog.py` — test suite
- `frontend/src/pages/ModelScoringPanel.tsx` — scoring UI
- `frontend/src/components/ModelDetailModal.tsx` — detail modal
- API endpoints (4) in `backend/app/main.py`

### Acceptance Criteria
- [ ] Catalog sync imports 200+ models from llmfit into SQLite
- [ ] API returns filtered/paginated catalog results within 200ms
- [ ] Frontend renders model list with score bars and hardware badges
- [ ] Search/filter works correctly by name, provider, param_size
- [ ] All 20+ unit tests pass
- [ ] Manual E2E test: start backend, sync catalog, verify frontend displays models

### Test Coverage Matrix

| Module | Test Count | Focus |
|--------|-----------|-------|
| DB schema | 3 | Table creation, columns, indexes |
| Sync script | 5 | Import, dedup, update, error handling, empty state |
| Service CRUD | 5 | Create, read, update, delete, search |
| API endpoints | 5 | List, detail, search, sync, auth |
| Frontend | TBD | Component render, filter, sort (Jest + React Testing Library) |

---

## Phase 3: Download Enhancement — Resumption & Multi-Source

### Objective
Improve model download reliability with resumption support and multi-source fallback (Ollama → HuggingFace → ModelScope).

### Core Tasks

| # | Task | Description | Priority |
|---|------|-------------|----------|
| 3.1 | `DownloadResumer` class | Track download progress in SQLite, resume from last byte offset | P0 |
| 3.2 | `MultiSourceResolver` | Priority queue: Ollama registry → HuggingFace → ModelScope | P0 |
| 3.3 | `DownloadProgressTracker` | SSE stream of download progress (% complete, speed, ETA) | P0 |
| 3.4 | API endpoint | `GET /download/status/{model}` — SSE progress stream | P0 |
| 3.5 | Frontend `DownloadPanel` | Download progress bar, pause/resume button, source indicator | P1 |
| 3.6 | `download_jobs` DB table | Track active/completed/failed downloads with timestamps | P0 |
| 3.7 | Integration tests | Mock network failures, verify resumption at byte offset, verify source fallback | P0 |
| 3.8 | Unit tests | 25+ tests: resumer, multi-source resolver, progress tracker, API, DB | P0 |

### Deliverables
- `backend/app/services/download_resumer.py` — resumption logic
- `backend/app/services/multi_source_resolver.py` — multi-source fallback
- `backend/app/services/download_progress_tracker.py` — SSE progress
- `backend/app/models/download_job.py` — SQLAlchemy model
- `backend/tests/test_download_resumer.py`
- `backend/tests/test_multi_source_resolver.py`
- `backend/tests/test_download_progress.py`
- `frontend/src/components/DownloadPanel.tsx`

### Acceptance Criteria
- [ ] Download resumption: pause at 50%, restart, continue from 50%
- [ ] Multi-source fallback: Ollama fails → HuggingFace fails → ModelScope succeeds
- [ ] SSE stream shows real-time download progress (% and speed)
- [ ] Download status persists across service restarts
- [ ] Frontend shows download progress bar with pause/resume
- [ ] All 25+ unit tests pass

### Test Coverage Matrix

| Module | Test Count | Focus |
|--------|-----------|-------|
| DownloadResumer | 8 | Resume, new download, completion, error, cleanup |
| MultiSourceResolver | 6 | Priority order, fallback chain, timeout, all fail |
| ProgressTracker | 5 | SSE events, progress %, speed, ETA, disconnect |
| API + DB | 5 | Status endpoint, job CRUD, history |
| Integration | 3 | Full flow with mock Ollama/HF/ModelScope |

---

## Milestone Summary

| Milestone | Phase | Key Deliverable | Target | Status |
|-----------|-------|-----------------|--------|--------|
| M1 | Phase 1 | Core llmfit service + 38 tests | 2026-06-23 | In Progress |
| M2 | Phase 2 | Model catalog DB + frontend | TBD | Pending |
| M3 | Phase 3 | Download resumption + multi-source | TBD | Pending |

---

## Daily Progress Tracking

Development progress is tracked in:
- **`llmfit_devlog.md`**: Daily entries with tasks, commits, test results, risks
- **`docs/llmfit_test_report.md`**: Full test execution report per phase

### Devlog Format

```markdown
| Date | Tasks Completed | Files Changed | Tests (Pass/Fail) | Status |
```

---

## Risk Register

| Risk | Phase | Probability | Impact | Mitigation | Status |
|------|-------|------------|--------|------------|--------|
| llmfit not installed | 1 | High | Medium | Graceful fallback to psutil | Mitigated |
| llmfit JSON format changes | 1 | Low | Medium | Alternate key parsing | Monitored |
| subprocess timeout | 1 | Medium | Low | 30s timeout + cache | Monitored |
| DB migration conflicts | 2 | Low | Medium | `alembic upgrade head` | To handle |
| Frontend bundle size | 2 | Low | Low | Lazy import for scoring panel | To handle |
| ModelScope API rate limit | 3 | Medium | Medium | Exponential backoff + cache | To handle |
| Large model download timeout | 3 | High | Medium | Resumption + chunked download | To handle |

---

## Change Log

| Date | Version | Author | Description |
|------|---------|--------|-------------|
| 2026-06-23 | 1.0 | System | Initial plan creation |
