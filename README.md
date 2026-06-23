# BAI-Edge-Model

A local-first edge LLM platform with RAG (Retrieval-Augmented Generation), Agent workflows, knowledge base management, and hardware-aware model auto-provisioning. Designed to run entirely on consumer laptops — no cloud dependency.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Browser (React)                       │
│               http://127.0.0.1:5173                      │
└───────────────────────┬─────────────────────────────────┘
                        │ REST / SSE
┌───────────────────────▼─────────────────────────────────┐
│               FastAPI Backend (:8000)                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │  Chat    │ │Knowledge │ │  Agent   │ │  Export  │   │
│  │ Service  │ │  Base    │ │ Service  │ │ Service  │   │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘   │
│       │            │            │            │          │
│  ┌────▼────┐ ┌─────▼──────┐ ┌──▼────┐ ┌────▼──────┐   │
│  │ Ollama  │ │ MinerU +   │ │Memory │ │ Doc Parser│   │
│  │ Service │ │ OCR Engine │ │Service│ │ (xlsx,    │   │
│  │         │ │            │ │       │ │  docx,    │   │
│  │         │ │            │ │       │ │  pptx)    │   │
│  └────┬────┘ └─────┬──────┘ └──┬────┘ └─────┬─────┘   │
│       │            │            │            │          │
│  ┌────▼────────────▼────────────▼────────────▼────┐    │
│  │              SQLite (local storage)              │    │
│  └────────────────────────────────────────────────┘    │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Resource Monitor  │  Model Download Service     │  │
│  │  (CPU/RAM/GPU)     │  (Auto-provision + MS fallback) │
│  └──────────────────────────────────────────────────┘  │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│               Ollama (:11434)                             │
│     Local LLM inference (qwen3, llama3.2, gemma3…)       │
└─────────────────────────────────────────────────────────┘
```

### Key Design Principles

| Principle | Implementation |
|-----------|---------------|
| **Local-first** | All data stored in local SQLite + filesystem; no cloud uploads |
| **Hardware-aware** | Auto-detects CPU/RAM/GPU and picks the best-fitting model |
| **Multi-source pull** | Tries Ollama registry first, falls back to ModelScope for restricted networks |
| **Tiered timeout** | Per-model-size timeout presets prevent false failure on large models |
| **Structured logging** | JSON-line logs with `trace_id` for full request-chain tracing |

---

## Capabilities

###  Chat & RAG
- Multi-turn conversation with session persistence
- Retrieval-Augmented Generation: chat with your uploaded documents
- Streaming SSE response for real-time token output
- Configurable RAG parameters: `top_k`, `score_threshold`
- **Markdown rendering** with syntax highlighting, line numbers, one-click copy, LaTeX math (KaTeX), Mermaid diagrams, responsive tables, and 3 built-in themes (Light / Dark / Eye Care)
- **Chat history persistence**: auto-save to localStorage, restore on page reload / navigation, capped at 10 most recent messages

###  Knowledge Base Management
- Upload PDF, DOCX, XLSX, PPTX, TXT files
- Auto-parsing via **MinerU** (PDF) + **pytesseract** OCR for scanned documents
- Chunk-level inspection and full reindex support
- Multi-knowledge-base selection per chat session

###  Agent Framework
- Tool-calling agent with extensible tool registry
- Streaming agent execution with run tracking (`/api/v1/agent/stream`)
- Run history inspection

###  Hardware Intelligence
- Real-time CPU / RAM / GPU snapshot API
- Model feasibility check against current hardware before launch
- Visual warning modal in UI with one-click model downgrade
- Auto-downloads the best-fit model on first startup

###  Memory & Context (Long-Short Term Memory System)
- **Short-term cache**: Thread-safe LRU + TTL cache (< 0.1ms read latency)
- **Long-term storage**: FTS5 + Jaccard 2-stage semantic retrieval
- **Auto-extraction**: LLM-powered (qwen3:0.6B) memory extraction from conversations, with rule-based fallback
- **Compression**: Hash dedup + Jaccard merge + importance-based archival (≥60% redundancy removal)
- **Encryption**: AES-256-GCM field-level encryption with PBKDF2 key derivation (local-only keys)
- **Context injection**: Automatic memory injection into chat prompts via `MemoryOrchestrator`

###  Hardware-Aware Model Intelligence
- **llmfit integration**: Hardware detection via llmfit CLI, with graceful fallback to psutil + curated catalog when llmfit not installed
- **Model catalog**: Persistent SQLite catalog with Q/S/F/C four-dimensional scoring, hardware requirements, and multi-field filter/search
- **Scoring UI**: Frontend `ModelCatalogPage` with score bars, detail modal, and sync controls
- **Auto-download**: First-startup model provisioning with multi-source fallback (Ollama → HuggingFace → ModelScope)
- **Download resumption**: SQLite-tracked chunked download with pause/resume and SSE progress streaming

###  Export
- Export chat sessions to Markdown, DOCX, or XLSX
- Downloadable export artifacts

###  Observability
- Structured JSON logging (`storage/logs/app.log`)
- Log query API with filtering by level, module, trace_id, time range
- Request tracing via `X-Trace-Id` header

---

## Prerequisites

| Component | Required | Check Command |
|-----------|----------|---------------|
| **Python** | 3.10+ | `python --version` |
| **Node.js** | 18+ | `node --version` |
| **npm** | 9+ | `npm --version` |
| **Ollama** | latest | `ollama --version` |
| **MinerU** | optional¹ | `mineru --version` |
| **Tesseract OCR** | optional² | `tesseract --version` |

¹ MinerU provides higher-quality PDF parsing. Without it, the service falls back to PyMuPDF + OCR.

² Tesseract is needed for OCR of scanned/image-based PDFs.

Install Ollama from [ollama.com](https://ollama.com/download).

---

## Quick Start

### One-Click (Windows)

```bat
start-dev.bat
```

This script will:
1. Create a Python virtual environment and install backend dependencies
2. Install frontend npm dependencies
3. Start the backend on **http://127.0.0.1:8000**
4. Start the frontend on **http://127.0.0.1:5173**
5. Open the browser automatically

On **first launch**, the service auto-detects your hardware and downloads the best-fitting model from the curated catalog:

| Your Hardware | Auto-Selected Model |
|---------------|---------------------|
| 10GB+ RAM + 8GB VRAM | `qwen3:8b` |
| 5GB+ RAM + 4GB VRAM | `gemma3:4b` or `phi4-mini:3.8b` |
| 4GB+ RAM + 3GB VRAM | `llama3.2:3b` |
| 2.5GB+ RAM | `qwen3:1.8b` |
| Low-end / fallback | `qwen3:0.6b` |

### Manual Start

**Start Ollama:**
```bash
ollama serve
```

**Start Backend:**
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Start Frontend:**
```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

### Stop Services

Close the two terminal windows started by `start-dev.bat`, or press `Ctrl+C` in each terminal if started manually.

### Verify

```bash
# Check backend health
curl http://127.0.0.1:8000/api/v1/system/info

# List available models
curl http://127.0.0.1:8000/api/v1/models

# Check hardware resources
curl http://127.0.0.1:8000/api/v1/system/resources
```

---

## Configuration

All settings use sensible defaults. Override via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `LOG_MAX_BYTES` | `5242880` | Max log file size before rotation (5 MB) |
| `LOG_BACKUP_COUNT` | `5` | Number of rotated log files to keep |
| `OLLAMA_READ_TIMEOUT_SECONDS` | `300` | Default read timeout for Ollama (overridden by tiered system) |
| `OLLAMA_CONNECT_TIMEOUT_SECONDS` | `10` | Connection timeout to Ollama |
| `OLLAMA_WRITE_TIMEOUT_SECONDS` | `30` | Write timeout |
| `OLLAMA_LIST_TIMEOUT_SECONDS` | `10` | Model listing timeout |
| `MINERU_COMMAND` | `mineru` | MinerU CLI command path |
| `MINERU_DEVICE` | `cpu` | MinerU device (cpu / cuda) |
| `OLLAMA_PREFER_MODELSCOPE` | `false` | Try ModelScope before Ollama registry (`1`/`true` to enable) |

### Tiered Timeout System

Timeouts are automatically scaled by model parameter size:

| Model Size | Read Timeout | Write Timeout |
|------------|-------------|---------------|
| 0.6B | 90s | 30s |
| 1.5B – 1.8B | 120–150s | 30s |
| 3B – 3.8B | 240–300s | 30s |
| 4B | 360s | 60s |
| 8B | 600s | 60s |

Users can override via the **Timeout Settings** button in the UI or the `PUT /api/v1/system/timeout-override` API.

---

## API Overview

### System
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/system/info` | App version and runtime info |
| GET | `/api/v1/system/resources` | CPU/RAM/GPU snapshot + recommendations |
| GET | `/api/v1/system/resources/check` | Feasibility check for a model |
| GET | `/api/v1/system/models/recommendations` | Models ranked by hardware suitability |
| GET | `/api/v1/system/models/catalog` | Curated model catalog with download info |
| POST | `/api/v1/system/models/pull` | Download a model |
| POST | `/api/v1/system/models/pull/stream` | Download with real-time NDJSON progress |
| GET | `/api/v1/system/timeout-info` | Resolved timeout tier for a model |
| PUT | `/api/v1/system/timeout-override` | Set manual timeout override |
| GET | `/api/v1/models` | List locally available Ollama models |

### LLMFIT Intelligence
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/llmfit/system` | Hardware profile from llmfit (with fallback) |
| GET | `/api/v1/llmfit/recommend` | Scored model recommendations |
| GET | `/api/v1/llmfit/models/{name}` | Single model hardware-fit info |
| POST | `/api/v1/llmfit/cache/refresh` | Clear llmfit in-memory cache |

### Model Catalog
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/catalog` | List catalog with filters (provider, size, fit, score, use_case) |
| GET | `/api/v1/catalog/search` | Full-text search across name, provider, description, tags |
| GET | `/api/v1/catalog/{name}` | Single model catalog detail |
| POST | `/api/v1/catalog/sync` | Trigger sync from curated catalog or llmfit |

### Download (Phase 3)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/download/pull` | Pull model with multi-source fallback |
| GET | `/api/v1/download/plan/{model}` | Get resolved download source plan |
| GET | `/api/v1/download/progress/{model}` | SSE real-time download progress |
| GET | `/api/v1/download/jobs` | List download jobs (filter by status) |
| GET | `/api/v1/download/jobs/{id}` | Single download job detail |
| POST | `/api/v1/download/jobs/{id}/pause` | Pause an active download |

### Chat & Sessions
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/chat/completions` | Non-streaming chat |
| POST | `/api/v1/chat/stream` | Streaming SSE chat |
| POST | `/api/v1/sessions` | Create session |
| GET | `/api/v1/sessions` | List sessions |
| GET | `/api/v1/sessions/{id}` | Get session detail |
| PUT | `/api/v1/sessions/{id}` | Update session |
| DELETE | `/api/v1/sessions/{id}` | Delete session |

### Knowledge Bases
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/knowledge-bases` | Create KB |
| GET | `/api/v1/knowledge-bases` | List KBs |
| GET/PUT/DELETE | `/api/v1/knowledge-bases/{id}` | CRUD operations |
| POST | `/api/v1/knowledge-bases/{id}/files/upload` | Upload files |
| GET | `/api/v1/knowledge-bases/{id}/files` | List files |
| DELETE | `/api/v1/knowledge-bases/{id}/files/{fid}` | Remove file |
| POST | `/api/v1/knowledge-bases/{id}/reindex` | Force reindex |
| GET | `/api/v1/knowledge-bases/{id}/chunks` | Inspect chunks |

### Agent & Memory
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/agent/tools` | List available agent tools |
| POST | `/api/v1/agent/stream` | Streaming agent execution |
| GET | `/api/v1/agent/runs/{id}` | Get agent run result |
| POST | `/api/v1/memories` | Create memory |
| GET | `/api/v1/memories` | List memories |
| PUT/DELETE | `/api/v1/memories/{id}` | CRUD |
| POST | `/api/v1/memories/extract` | Auto-extract memories |

### Export & Logs
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/exports/markdown` | Export session to Markdown |
| POST | `/api/v1/exports/docx` | Export session to DOCX |
| POST | `/api/v1/exports/xlsx` | Export session to XLSX |
| GET | `/api/v1/exports/{id}/download` | Download export |
| GET | `/api/v1/logs` | Query structured logs |
| GET | `/api/v1/tasks` | List background tasks |

### Settings
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/settings` | Get app settings |
| PUT | `/api/v1/settings` | Update settings |
| GET | `/api/v1/languages` | List supported languages |

---

## Project Structure

```
BAI-Edge-Model/
├── backend/
│   ├── app/
│   │   ├── core/           # Config, DB, logging, request context
│   │   ├── schemas/        # Pydantic models (chat, agent, KB, export…)
│   │   ├── services/       # Business logic
│   │   │   ├── chat_service.py            # Chat orchestration
│   │   │   ├── ollama_service.py          # Ollama API client
│   │   │   ├── resource_monitor.py        # Hardware detection
│   │   │   ├── model_download_service.py  # Auto-provision + ModelScope
│   │   │   ├── knowledge_base_service.py  # KB CRUD
│   │   │   ├── ingest_service.py          # File ingest pipeline
│   │   │   ├── parser_service.py          # PDF/DOCX/XLSX parser
│   │   │   ├── mineru_service.py          # MinerU integration
│   │   │   ├── agent_service.py           # Agent framework
│   │   │   ├── memory_service.py          # Long-term memory
│   │   │   ├── export_service.py          # Session export
│   │   │   ├── log_service.py             # Log query
│   │   │   └── ...
│   │   ├── utils/           # ID generation
│   │   └── main.py          # FastAPI app + all routes
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   └── markdown/          # Markdown rendering components
│   │   │       ├── MarkdownRenderer.tsx   # Main renderer + theme system
│   │   │       ├── CodeBlock.tsx          # Syntax highlight + copy
│   │   │       ├── MermaidBlock.tsx       # Mermaid diagram renderer
│   │   │       ├── markdownThemes.ts      # 3 built-in themes
│   │   │       └── markdownUtils.ts       # Chunking + sanitizer
│   │   ├── pages/
│   │   │   ├── ChatPage.tsx          # Main chat UI
│   │   │   ├── MarkdownStudioPage.tsx # Markdown prototype / preview
│   │   │   └── AdminPage.tsx         # Admin panel
│   │   ├── services/api.ts           # API client + types
│   │   ├── i18n/messages.ts          # Internationalization
│   │   ├── utils/
│   │   │   └── chatHistoryStorage.ts # localStorage chat persistence
│   │   └── ...
│   ├── package.json
│   └── vite.config.ts
├── storage/         # Runtime data (gitignored)
├── start-dev.bat    # One-click launcher
└── .gitignore
```

---

## Development

### Run Tests

```bash
cd backend
python -m pytest tests/ -v
```

### Lint

```bash
# Frontend
cd frontend
npm run lint

# Backend (ruff recommended)
pip install ruff
ruff check backend/
```

### Build Frontend

```bash
cd frontend
npm run build
```

Output goes to `frontend/dist/`.

---

## Troubleshooting

### "No local Ollama models are available"
The service auto-downloads a model on first startup. If it fails:
1. Ensure Ollama is running: `ollama serve`
2. Manually pull: `ollama pull qwen3:1.8b`
3. Or use ModelScope: set `OLLAMA_PREFER_MODELSCOPE=1` and restart

### Chat times out
- If using a large model on CPU, increase the read timeout via the UI or API
- Check hardware load with `/api/v1/system/resources`
- Query logs for timeout events: `GET /api/v1/logs?module=ollama`

### PDF parsing quality
- Install MinerU for best results: `pip install magic-pdf`
- For scanned PDFs, install Tesseract OCR and its Chinese language pack

### Model download from HuggingFace is blocked
- The service automatically falls back to ModelScope
- Or set `OLLAMA_PREFER_MODELSCOPE=1` to prioritize ModelScope

---

## License

MIT

