from __future__ import annotations

from contextlib import asynccontextmanager
import json
import threading
import time
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.core.config import config
from app.core.database import init_db
from app.core.logging import get_logger, log_event, setup_logging
from app.core.request_context import get_trace_id, set_trace_id
from app.schemas.agent import AgentRequestDTO
from app.schemas.chat import ChatRequestDTO, SessionCreateDTO
from app.schemas.common import ApiResponse
from app.schemas.export import ExportRequestDTO
from app.schemas.knowledge_base import KnowledgeBaseCreateDTO, KnowledgeBaseUpdateDTO
from app.schemas.catalog import CatalogSearchRequest
from app.schemas.download import DownloadPullRequest
from app.schemas.memory import (
    MemoryConfigDTO,
    MemoryCreateDTO,
    MemorySearchRequest,
)
from app.schemas.settings import SettingsUpdateDTO
from app.services.agent_service import AgentService
from app.services.chat_service import ChatService
from app.services.download_orchestrator import DownloadOrchestrator
from app.services.export_service import ExportService
from app.services.ingest_service import IngestService
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.llmfit_service import LlmfitService
from app.services.log_service import LogService
from app.services.model_catalog_service import ModelCatalogService
from app.services.memory_orchestrator import MemoryOrchestrator
from app.services.memory_service import MemoryService
from app.services.model_download_service import ModelDownloadService
from app.services.ollama_service import OllamaService
from app.services.resource_monitor import extract_param_size
from app.services.settings_service import SettingsService
from app.services.task_service import TaskService

_lifespan_logger = get_logger("app.lifespan")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    setup_logging()
    # Auto-download the best-fit edge model on first deployment
    dl_service = ModelDownloadService()
    log_event(
        _lifespan_logger, 20, "lifespan.auto_download_started",
        "Starting auto model download check",
        module_name="lifespan", trace_id="startup",
    )
    try:
        result = dl_service.ensure_default_model()
        log_event(
            _lifespan_logger, 20, "lifespan.auto_download_completed",
            f"Auto model download: {result.get('action')}",
            module_name="lifespan", trace_id="startup",
            **result,
        )
    except Exception:
        log_event(
            _lifespan_logger, 30, "lifespan.auto_download_error",
            "Auto model download check failed (non-fatal)",
            module_name="lifespan", trace_id="startup",
            exc_info=True,
        )
    yield


app = FastAPI(title=config.app_name,
              version=config.app_version, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
logger = get_logger("app.api")

settings_service = SettingsService()
kb_service = KnowledgeBaseService()
chat_service = ChatService()
memory_service = MemoryService()
memory_orchestrator = MemoryOrchestrator()
llmfit_service = LlmfitService()
catalog_service = ModelCatalogService()
download_orchestrator = DownloadOrchestrator()
agent_service = AgentService()
export_service = ExportService()
task_service = TaskService()
ingest_service = IngestService()
log_service = LogService()


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-Id") or str(uuid4())
    set_trace_id(trace_id)
    started_at = time.time()
    log_event(
        logger,
        20,
        "http.request.started",
        "HTTP request started",
        module_name="api",
        trace_id=trace_id,
        method=request.method,
        path=request.url.path,
        query=str(request.url.query),
        client=request.client.host if request.client else "",
    )
    try:
        response = await call_next(request)
    except Exception:
        log_event(
            logger,
            40,
            "http.request.failed",
            "HTTP request raised an unhandled exception",
            module_name="api",
            trace_id=trace_id,
            method=request.method,
            path=request.url.path,
            elapsed_ms=round((time.time() - started_at) * 1000, 2),
            exc_info=True,
        )
        raise
    response.headers["X-Trace-Id"] = trace_id
    level = 30 if response.status_code >= 400 else 20
    log_event(
        logger,
        level,
        "http.request.completed",
        "HTTP request completed",
        module_name="api",
        trace_id=trace_id,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        elapsed_ms=round((time.time() - started_at) * 1000, 2),
    )
    return response


@app.get("/api/v1/system/info")
def system_info() -> ApiResponse[dict]:
    return ApiResponse(
        data={
            "app_name": config.app_name,
            "version": config.app_version,
            "runtime": {
                "python": "local",
                "llm": "adapter-ready",
                "storage_root": str(config.storage_root),
                "logging": {
                    "level": config.log_level,
                    "log_root": str(config.logs_root),
                    "rotation_max_bytes": config.log_max_bytes,
                    "rotation_backup_count": config.log_backup_count,
                },
                "ollama": {
                    "base_url": "http://127.0.0.1:11434",
                    "list_timeout_seconds": config.ollama_list_timeout_seconds,
                    "connect_timeout_seconds": config.ollama_connect_timeout_seconds,
                    "read_timeout_seconds": config.ollama_read_timeout_seconds,
                },
            },
        }
    )


# ---------------------------------------------------------------------------
# Resource monitoring & model recommendation endpoints
# ---------------------------------------------------------------------------

class TimeoutOverrideDTO(BaseModel):
    read_timeout_seconds: float | None = Field(
        default=None, ge=10, le=3600,
        description="Override read timeout in seconds (10-3600). Set to null to revert to tiered auto-selection."
    )


@app.get("/api/v1/system/resources")
def system_resources() -> ApiResponse[dict]:
    """Return a real-time snapshot of CPU, RAM, and GPU resources."""
    return ApiResponse(data=chat_service.check_resources())


@app.get("/api/v1/system/resources/check")
def check_model_resources(model_name: str = Query(..., description="Model name to check feasibility for")) -> ApiResponse[dict]:
    """Check if the current hardware can support the specified model."""
    result = chat_service.check_resources(model_name=model_name)
    return ApiResponse(data=result)


@app.get("/api/v1/system/models/recommendations")
def model_recommendations() -> ApiResponse[list[dict]]:
    """Return all registered models ranked by suitability for current hardware."""
    result = chat_service.check_resources()
    return ApiResponse(data=result.get("recommendations", []))


@app.get("/api/v1/system/timeout-info")
def timeout_info(model_name: str = Query(..., description="Model name to get timeout tier for")) -> ApiResponse[dict]:
    """Return the resolved timeout tier for a given model."""
    return ApiResponse(data=chat_service.get_timeout_info(model_name))


@app.put("/api/v1/system/timeout-override")
def set_timeout_override(payload: TimeoutOverrideDTO) -> ApiResponse[dict]:
    """Set a user-custom read timeout override. Set null to revert to tiered auto-selection."""
    # Mutate the config's user_timeout_override_seconds (bypass frozen dataclass via object.__setattr__)
    object.__setattr__(config, "user_timeout_override_seconds",
                       payload.read_timeout_seconds)
    log_event(
        logger,
        20,
        "timeout_override.updated",
        "User timeout override updated",
        module_name="api",
        trace_id=get_trace_id(),
        read_timeout_seconds=payload.read_timeout_seconds,
    )
    return ApiResponse(data={
        "user_timeout_override_seconds": config.user_timeout_override_seconds,
        "message": "Timeout override updated" if payload.read_timeout_seconds else "Reverted to tiered auto-selection",
    })


# ---------------------------------------------------------------------------
# Model download & catalog endpoints
# ---------------------------------------------------------------------------

_model_download_service = ModelDownloadService()


def _infer_provider_from_name(model_name: str) -> str:
    lowered = model_name.lower()
    if lowered.startswith("qwen"):
        return "Qwen"
    if lowered.startswith("llama"):
        return "Meta"
    if lowered.startswith("gemma"):
        return "Google"
    if lowered.startswith("phi"):
        return "Microsoft"
    if lowered.startswith("deepseek"):
        return "DeepSeek"
    return "unknown"


def _find_catalog_fallback(model_name: str, provider: str, param_size: str) -> dict | None:
    entry = catalog_service.get_by_model_name(model_name)
    if entry is not None:
        return entry.model_dump()

    family = model_name.split(":", 1)[0].strip()
    if not family:
        return None

    candidates = catalog_service.search(family, limit=50).items
    exact_size = [
        item for item in candidates
        if item.param_size == param_size and (
            item.provider.lower() == provider.lower() or provider == "unknown"
        )
    ]
    if exact_size:
        return exact_size[0].model_dump()

    exact_provider = [
        item for item in candidates
        if item.provider.lower() == provider.lower()
    ]
    if exact_provider:
        return exact_provider[0].model_dump()

    return candidates[0].model_dump() if candidates else None


def _enrich_local_model(item: dict) -> dict:
    model_name = str(item.get("name", "")).strip()
    provider = _infer_provider_from_name(model_name)
    param_size = extract_param_size(model_name)
    enriched = {
        "name": model_name,
        "size": item.get("size", 0),
        "modified_at": item.get("modified_at", ""),
        "digest": item.get("digest", ""),
        "provider": provider,
        "param_size": param_size,
        "score_total": 0,
        "score_quality": 0,
        "score_speed": 0,
        "score_fit": 0,
        "score_context": 0,
        "fit_level": "unknown",
        "estimated_tps": 0,
        "quantization": "unknown",
        "memory_required_gb": 0,
        "vram_required_gb": 0,
        "run_mode": "CPU",
        "use_case": "general",
        "max_context": 8192,
        "is_moe": False,
        "available": True,
        "source": "local",
    }

    llmfit_rec = llmfit_service.get_model_info(model_name)
    if llmfit_rec is not None:
        enriched.update({
            "provider": llmfit_rec.provider or provider,
            "param_size": llmfit_rec.param_size or param_size,
            "score_total": llmfit_rec.score.total,
            "score_quality": llmfit_rec.score.quality,
            "score_speed": llmfit_rec.score.speed,
            "score_fit": llmfit_rec.score.fit,
            "score_context": llmfit_rec.score.context,
            "fit_level": llmfit_rec.fit_level,
            "estimated_tps": llmfit_rec.estimated_tps,
            "quantization": llmfit_rec.quantization,
            "memory_required_gb": llmfit_rec.memory_required_gb,
            "run_mode": llmfit_rec.run_mode,
            "use_case": llmfit_rec.use_case,
            "max_context": llmfit_rec.max_context or 8192,
            "is_moe": llmfit_rec.is_moe,
            "source": "local+llmfit",
        })

    catalog_rec = _find_catalog_fallback(
        model_name,
        str(enriched["provider"]),
        str(enriched["param_size"]),
    )
    if catalog_rec is not None:
        enriched.update({
            "provider": catalog_rec.get("provider") or enriched["provider"],
            "param_size": catalog_rec.get("param_size") or enriched["param_size"],
            "score_total": enriched["score_total"] or catalog_rec.get("score_total", 0),
            "score_quality": enriched["score_quality"] or catalog_rec.get("score_quality", 0),
            "score_speed": enriched["score_speed"] or catalog_rec.get("score_speed", 0),
            "score_fit": enriched["score_fit"] or catalog_rec.get("score_fit", 0),
            "score_context": enriched["score_context"] or catalog_rec.get("score_context", 0),
            "fit_level": enriched["fit_level"] if enriched["fit_level"] != "unknown" else catalog_rec.get("fit_level", "unknown"),
            "estimated_tps": enriched["estimated_tps"] or catalog_rec.get("estimated_tps", 0),
            "quantization": enriched["quantization"] if enriched["quantization"] != "unknown" else catalog_rec.get("quantization", "unknown"),
            "memory_required_gb": enriched["memory_required_gb"] or catalog_rec.get("memory_required_gb", 0),
            "vram_required_gb": catalog_rec.get("vram_required_gb", 0),
            "run_mode": enriched["run_mode"] if enriched["run_mode"] != "CPU" else catalog_rec.get("run_mode", "CPU"),
            "use_case": enriched["use_case"] if enriched["use_case"] != "general" else catalog_rec.get("use_case", "general"),
            "max_context": enriched["max_context"] if enriched["max_context"] != 8192 else catalog_rec.get("max_context", 8192),
            "is_moe": enriched["is_moe"] or catalog_rec.get("is_moe", False),
            "source": enriched["source"] if enriched["source"] != "local" else "local+catalog",
        })

    return enriched


@app.get("/api/v1/system/models/catalog")
def model_catalog() -> ApiResponse[list[dict]]:
    """Return the curated catalog of recommended edge models with hardware suitability."""
    return ApiResponse(data=_model_download_service.get_catalog())


@app.post("/api/v1/system/models/pull")
def pull_model(payload: dict) -> ApiResponse[dict]:
    """Pull (download) a model from the Ollama library. Body: {"model_name": "qwen3:1.8b"}."""
    model_name = payload.get("model_name", "")
    if not model_name:
        raise HTTPException(status_code=400, detail="model_name is required")
    result = _model_download_service.pull_model_manually(model_name)
    return ApiResponse(data=result)


@app.post("/api/v1/system/models/pull/stream")
def pull_model_stream(payload: dict) -> StreamingResponse:
    """Pull a model with real-time NDJSON progress streaming. Body: {"model_name": "qwen3:1.8b"}."""
    model_name = payload.get("model_name", "")
    if not model_name:
        raise HTTPException(status_code=400, detail="model_name is required")
    ollama = OllamaService()
    return StreamingResponse(
        ollama.pull_model_stream(model_name),
        media_type="application/x-ndjson",
    )


# ---------------------------------------------------------------------------
# llmfit integration — hardware detection & model recommendation
# ---------------------------------------------------------------------------

@app.get("/api/v1/llmfit/system")
def llmfit_system() -> ApiResponse[dict]:
    """Return hardware profile from llmfit (with psutil fallback)."""
    profile = llmfit_service.get_system_profile()
    return ApiResponse(data={
        "available": llmfit_service.available,
        "source": "llmfit" if llmfit_service.available else "psutil",
        "cpu": {
            "cores": profile.cpu.cores,
            "model": profile.cpu.model,
            "arch": profile.cpu.arch,
        },
        "ram": {
            "total_gb": profile.ram.total_gb,
            "available_gb": profile.ram.available_gb,
        },
        "gpus": [
            {"name": g.name, "vram_gb": g.vram_gb, "backend": g.backend}
            for g in profile.gpus
        ],
        "os": profile.os,
    })


@app.get("/api/v1/llmfit/recommend")
def llmfit_recommend(
    use_case: str = Query(
        "general", description="general|coding|reasoning|chat|multimodal|embedding"),
    limit: int = Query(10, ge=1, le=50),
    min_fit: str = Query("marginal", description="perfect|good|marginal"),
    sort: str = Query("score", description="score|tps|params|mem|ctx"),
    include_too_tight: bool = Query(False),
) -> ApiResponse[dict]:
    """Return scored model recommendations from llmfit (with catalog fallback)."""
    recs = llmfit_service.get_recommendations(
        limit=limit,
        use_case=use_case,
        min_fit=min_fit,
        sort=sort,
        include_too_tight=include_too_tight,
    )
    return ApiResponse(data={
        "available": llmfit_service.available,
        "source": "llmfit" if llmfit_service.available else "catalog",
        "count": len(recs),
        "recommendations": [
            {
                "model_name": r.model_name,
                "provider": r.provider,
                "param_size": r.param_size,
                "score": {
                    "total": r.score.total,
                    "quality": r.score.quality,
                    "speed": r.score.speed,
                    "fit": r.score.fit,
                    "context": r.score.context,
                },
                "fit_level": r.fit_level,
                "estimated_tps": r.estimated_tps,
                "quantization": r.quantization,
                "memory_required_gb": r.memory_required_gb,
                "run_mode": r.run_mode,
                "use_case": r.use_case,
                "max_context": r.max_context,
                "is_moe": r.is_moe,
                "available": r.available,
            }
            for r in recs
        ],
    })


@app.get("/api/v1/llmfit/models/{model_name:path}")
def llmfit_model_info(model_name: str) -> ApiResponse[dict]:
    """Return detailed info for a specific model from llmfit."""
    rec = llmfit_service.get_model_info(model_name)
    if rec is None:
        raise HTTPException(
            status_code=404, detail=f"Model not found in llmfit: {model_name}")
    return ApiResponse(data={
        "model_name": rec.model_name,
        "provider": rec.provider,
        "param_size": rec.param_size,
        "score": {
            "total": rec.score.total,
            "quality": rec.score.quality,
            "speed": rec.score.speed,
            "fit": rec.score.fit,
            "context": rec.score.context,
        },
        "fit_level": rec.fit_level,
        "estimated_tps": rec.estimated_tps,
        "quantization": rec.quantization,
        "memory_required_gb": rec.memory_required_gb,
        "run_mode": rec.run_mode,
        "use_case": rec.use_case,
        "max_context": rec.max_context,
        "is_moe": rec.is_moe,
    })


@app.post("/api/v1/llmfit/cache/refresh")
def llmfit_refresh_cache() -> ApiResponse[dict]:
    """Clear the llmfit in-memory cache to force fresh data."""
    llmfit_service.refresh_cache()
    return ApiResponse(data={"message": "llmfit cache cleared"})


# ---------------------------------------------------------------------------
# Model catalog — persistent model metadata with scores & hardware reqs
# ---------------------------------------------------------------------------

@app.get("/api/v1/catalog")
def catalog_list(
    provider: str | None = Query(None),
    param_size: str | None = Query(None),
    fit_level: str | None = Query(None),
    use_case: str | None = Query(None),
    run_mode: str | None = Query(None),
    min_score: float | None = Query(None, ge=0, le=100),
    sort_by: str = Query("score_total"),
    sort_dir: str = Query("desc"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> ApiResponse[dict]:
    """List model catalog with optional filters."""
    result = catalog_service.list_all(
        provider=provider,
        param_size=param_size,
        fit_level=fit_level,
        use_case=use_case,
        run_mode=run_mode,
        min_score=min_score,
        sort_by=sort_by,
        sort_dir=sort_dir,
        offset=offset,
        limit=limit,
    )
    return ApiResponse(data={
        "total": result.total,
        "items": [item.model_dump() for item in result.items],
    })


@app.get("/api/v1/catalog/search")
def catalog_search(q: str = Query("", description="Search query")) -> ApiResponse[dict]:
    """Full-text search across model catalog by name, provider, description, tags."""
    result = catalog_service.search(query=q, limit=100)
    return ApiResponse(data={
        "total": result.total,
        "items": [item.model_dump() for item in result.items],
    })


@app.get("/api/v1/catalog/{model_name:path}")
def catalog_detail(model_name: str) -> ApiResponse[dict]:
    """Get detailed info for a single model in the catalog."""
    entry = catalog_service.get_by_model_name(model_name)
    if entry is None:
        raise HTTPException(
            status_code=404, detail=f"Model not found in catalog: {model_name}")
    return ApiResponse(data=entry.model_dump())


@app.post("/api/v1/catalog/sync")
def catalog_sync(payload: dict | None = None) -> ApiResponse[dict]:
    """Sync catalog from curated model list, llmfit, or local Ollama models."""
    source = str((payload or {}).get("source", "curated")).strip() or "curated"
    count_before = catalog_service.count()

    if source in {"local", "auto"}:
        local_models = chat_service.list_models()
        enriched_models = [_enrich_local_model(item) for item in local_models]
        result = catalog_service.sync_local_models(enriched_models)
        return ApiResponse(
            data={
                "message": "local model sync completed",
                "source": source,
                "count_before": count_before,
                "hint": "This endpoint synced local Ollama models into the catalog table.",
                "local_model_count": len(local_models),
                "result": result.model_dump(),
            }
        )

    msg = "catalog sync trigger received"
    return ApiResponse(
        data={
            "message": msg,
            "source": source,
            "count_before": count_before,
            "hint": "Run: python -m scripts.sync_model_catalog --source " + source,
        }
    )


# ---------------------------------------------------------------------------
# Download — multi-source download with resumption & SSE progress
# ---------------------------------------------------------------------------

@app.post("/api/v1/download/pull")
def download_pull(payload: DownloadPullRequest) -> ApiResponse[dict]:
    """Pull a model with multi-source fallback (Ollama → HF → ModelScope)."""
    # #region debug-point A:download-pull-entry
    log_event(
        logger,
        20,
        "download.pull.endpoint_entry_debug",
        "Download pull API request received",
        module_name="download",
        trace_id=get_trace_id(),
        model_name=payload.model_name,
        source=payload.source,
        has_download_url=bool(payload.download_url),
        chunk_size=payload.chunk_size,
    )
    # #endregion
    result = download_orchestrator.pull_model(
        model_name=payload.model_name,
        source=payload.source,
        download_url=payload.download_url,
        chunk_size=payload.chunk_size,
    )
    # #region debug-point E:download-pull-return
    log_event(
        logger,
        20,
        "download.pull.endpoint_return_debug",
        "Download pull API request completed",
        module_name="download",
        trace_id=get_trace_id(),
        model_name=payload.model_name,
        source=payload.source,
        result_status=result.get("status"),
        result_source=result.get("source"),
        job_id=result.get("job_id"),
    )
    # #endregion
    return ApiResponse(data=result)


@app.get("/api/v1/download/plan/{model_name:path}")
def download_plan(model_name: str, source: str = "auto") -> ApiResponse[dict]:
    """Return the resolved multi-source download plan for a model."""
    plan = download_orchestrator.resolve_plan(model_name, prefer=source)
    return ApiResponse(data=plan.model_dump())


@app.get("/api/v1/download/progress/{model_name:path}")
async def download_progress(model_name: str) -> StreamingResponse:
    """SSE endpoint for real-time download progress."""
    return StreamingResponse(
        download_orchestrator.tracker.stream(model_name),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/v1/download/jobs/{job_id}/progress")
async def download_job_progress(job_id: str) -> StreamingResponse:
    """SSE endpoint for a single persisted download job."""
    return StreamingResponse(
        download_orchestrator.tracker.stream(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/v1/download/jobs")
def download_jobs(status: str | None = None) -> ApiResponse[dict]:
    """List download jobs, optionally filtered by status."""
    jobs = download_orchestrator.list_jobs(status=status)
    return ApiResponse(data={
        "total": len(jobs),
        "items": [j.model_dump() for j in jobs],
    })


@app.get("/api/v1/download/jobs/{job_id}")
def download_job_detail(job_id: str) -> ApiResponse[dict]:
    """Get a single download job by ID."""
    try:
        job = download_orchestrator.get_job(job_id)
        return ApiResponse(data=job.model_dump())
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")


@app.post("/api/v1/download/jobs/{job_id}/pause")
def download_job_pause(job_id: str) -> ApiResponse[dict]:
    """Pause an active download job."""
    download_orchestrator.pause(job_id)
    return ApiResponse(data={"message": "paused", "job_id": job_id})


@app.get("/api/v1/settings")
def get_settings() -> ApiResponse[dict]:
    return ApiResponse(data=settings_service.get().model_dump())


@app.put("/api/v1/settings")
def update_settings(payload: SettingsUpdateDTO) -> ApiResponse[dict]:
    return ApiResponse(data=settings_service.update(payload).model_dump())


@app.get("/api/v1/languages")
def get_languages() -> ApiResponse[list[dict]]:
    return ApiResponse(
        data=[
            {"code": "zh-CN", "label": "简体中文"},
            {"code": "en-US", "label": "English"},
        ]
    )


@app.get("/api/v1/models")
def get_models() -> ApiResponse[list[dict]]:
    local_models = chat_service.list_models()
    return ApiResponse(data=[_enrich_local_model(item) for item in local_models])


@app.post("/api/v1/knowledge-bases")
def create_knowledge_base(payload: KnowledgeBaseCreateDTO) -> ApiResponse[dict]:
    return ApiResponse(data=kb_service.create(payload).model_dump())


@app.get("/api/v1/knowledge-bases")
def list_knowledge_bases() -> ApiResponse[list[dict]]:
    return ApiResponse(data=[item.model_dump() for item in kb_service.list_all()])


@app.get("/api/v1/knowledge-bases/{kb_id}")
def get_knowledge_base(kb_id: str) -> ApiResponse[dict]:
    return ApiResponse(data=kb_service.get(kb_id).model_dump())


@app.put("/api/v1/knowledge-bases/{kb_id}")
def update_knowledge_base(
    kb_id: str, payload: KnowledgeBaseUpdateDTO
) -> ApiResponse[dict]:
    return ApiResponse(data=kb_service.update(kb_id, payload).model_dump())


@app.delete("/api/v1/knowledge-bases/{kb_id}")
def delete_knowledge_base(kb_id: str) -> ApiResponse[dict]:
    kb_service.delete(kb_id)
    return ApiResponse(data={"deleted": True, "kb_id": kb_id})


@app.post("/api/v1/knowledge-bases/{kb_id}/files/upload")
async def upload_file(
    kb_id: str, file: UploadFile = File(...), enable_ocr: bool = Query(True)
) -> ApiResponse[dict]:
    try:
        data = await ingest_service.upload(kb_id, file, enable_ocr=enable_ocr)
        payload = {**data, "document": data["document"].model_dump()}
        return ApiResponse(data=payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v1/knowledge-bases/{kb_id}/files")
def list_files(kb_id: str) -> ApiResponse[list[dict]]:
    return ApiResponse(data=[item.model_dump() for item in kb_service.list_files(kb_id)])


@app.delete("/api/v1/knowledge-bases/{kb_id}/files/{file_id}")
def delete_file(kb_id: str, file_id: str) -> ApiResponse[dict]:
    try:
        return ApiResponse(data=kb_service.delete_file(kb_id, file_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/v1/knowledge-bases/{kb_id}/reindex")
def reindex_knowledge_base(kb_id: str) -> ApiResponse[dict]:
    task = kb_service.start_reindex(kb_id)
    worker = threading.Thread(
        target=kb_service.reindex,
        args=(kb_id, task["id"]),
        daemon=True,
    )
    worker.start()
    return ApiResponse(data=task)


@app.get("/api/v1/knowledge-bases/{kb_id}/chunks")
def list_chunks(
    kb_id: str,
    document_id: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> ApiResponse[dict]:
    return ApiResponse(
        data=kb_service.list_chunks(
            kb_id,
            document_id=document_id,
            offset=offset,
            limit=limit,
        )
    )


@app.get("/api/v1/knowledge-bases/{kb_id}/stats")
def get_knowledge_base_stats(kb_id: str) -> ApiResponse[dict]:
    return ApiResponse(data=kb_service.get_stats(kb_id))


@app.get("/api/v1/tasks")
def list_tasks() -> ApiResponse[list[dict]]:
    return ApiResponse(data=[item.model_dump() for item in task_service.list_all()])


@app.get("/api/v1/tasks/{task_id}")
def get_task(task_id: str) -> ApiResponse[dict]:
    return ApiResponse(data=task_service.get(task_id).model_dump())


@app.post("/api/v1/tasks/{task_id}/retry")
def retry_task(task_id: str) -> ApiResponse[dict]:
    return ApiResponse(data=task_service.update(task_id, status="done", progress=1.0).model_dump())


@app.post("/api/v1/tasks/{task_id}/cancel")
def cancel_task(task_id: str) -> ApiResponse[dict]:
    return ApiResponse(data=task_service.update(task_id, status="cancelled", progress=0).model_dump())


@app.post("/api/v1/sessions")
def create_session(payload: SessionCreateDTO) -> ApiResponse[dict]:
    return ApiResponse(data=chat_service.create_session(payload).model_dump())


@app.get("/api/v1/sessions")
def list_sessions() -> ApiResponse[list[dict]]:
    return ApiResponse(data=[item.model_dump() for item in chat_service.list_sessions()])


@app.get("/api/v1/sessions/{session_id}")
def get_session(session_id: str) -> ApiResponse[dict]:
    data = chat_service.get_session(session_id)
    return ApiResponse(
        data={
            "session": data["session"].model_dump(),
            "messages": [msg.model_dump() for msg in data["messages"]],
        }
    )


@app.put("/api/v1/sessions/{session_id}")
def update_session(session_id: str, payload: dict) -> ApiResponse[dict]:
    return ApiResponse(
        data=chat_service.update_session_title(
            session_id, payload.get("title", "Untitled")
        ).model_dump()
    )


@app.delete("/api/v1/sessions/{session_id}")
def delete_session(session_id: str) -> ApiResponse[dict]:
    chat_service.delete_session(session_id)
    return ApiResponse(data={"deleted": True, "session_id": session_id})


@app.post("/api/v1/chat/completions")
def chat_completions(payload: ChatRequestDTO) -> ApiResponse[dict]:
    # #region debug-point C:chat-completions-entry
    log_event(
        logger,
        20,
        "chat.completions.received",
        "Chat completion request received",
        module_name="chat",
        trace_id=get_trace_id() if get_trace_id() != "-" else payload.session_id,
        session_id=payload.session_id,
        model_name=payload.model_name,
        query_chars=len(payload.query),
        knowledge_base_count=len(payload.knowledge_base_ids),
        top_k=payload.top_k,
    )
    # #endregion
    try:
        return ApiResponse(data=chat_service.answer(payload).model_dump())
    except RuntimeError as exc:
        # #region debug-point D:chat-completions-runtime-error
        log_event(
            logger,
            30,
            "chat.completions.runtime_error_debug",
            "Chat completion raised runtime error",
            module_name="chat",
            trace_id=get_trace_id() if get_trace_id() != "-" else payload.session_id,
            session_id=payload.session_id,
            model_name=payload.model_name,
            error=str(exc),
        )
        # #endregion
        trace_id = get_trace_id()
        if trace_id == "-" and payload.session_id:
            trace_id = payload.session_id
        log_event(
            logger,
            30,
            "chat.runtime_error",
            "Chat completion raised a runtime error",
            module_name="chat",
            trace_id=trace_id,
            session_id=payload.session_id,
            model_name=payload.model_name,
            exc_info=True,
        )
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        # #region debug-point D:chat-completions-exception
        log_event(
            logger,
            40,
            "chat.completions.exception_debug",
            "Chat completion raised unexpected exception",
            module_name="chat",
            trace_id=get_trace_id() if get_trace_id() != "-" else payload.session_id,
            session_id=payload.session_id,
            model_name=payload.model_name,
            error=str(exc),
        )
        # #endregion
        trace_id = get_trace_id()
        if trace_id == "-" and payload.session_id:
            trace_id = payload.session_id
        log_event(
            logger,
            40,
            "chat.unexpected_error",
            "Chat completion raised an unexpected exception",
            module_name="chat",
            trace_id=trace_id,
            session_id=payload.session_id,
            model_name=payload.model_name,
            exc_info=True,
        )
        raise HTTPException(
            status_code=502, detail=f"Ollama request failed: {exc}") from exc


@app.post("/api/v1/chat/stream")
def chat_stream(payload: ChatRequestDTO) -> StreamingResponse:
    try:
        return StreamingResponse(chat_service.stream_answer(payload), media_type="text/event-stream")
    except RuntimeError as exc:
        trace_id = get_trace_id()
        if trace_id == "-" and payload.session_id:
            trace_id = payload.session_id
        log_event(
            logger,
            30,
            "chat.stream.runtime_error",
            "Chat stream raised a runtime error",
            module_name="chat",
            trace_id=trace_id,
            session_id=payload.session_id,
            model_name=payload.model_name,
            exc_info=True,
        )
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        trace_id = get_trace_id()
        if trace_id == "-" and payload.session_id:
            trace_id = payload.session_id
        log_event(
            logger,
            40,
            "chat.stream.unexpected_error",
            "Chat stream raised an unexpected exception",
            module_name="chat",
            trace_id=trace_id,
            session_id=payload.session_id,
            model_name=payload.model_name,
            exc_info=True,
        )
        raise HTTPException(
            status_code=502, detail=f"Ollama request failed: {exc}") from exc


@app.get("/api/v1/logs")
def query_logs(
    level: str | None = Query(None),
    module: str | None = Query(None),
    trace_id: str | None = Query(None),
    start_time: str | None = Query(None),
    end_time: str | None = Query(None),
    limit: int = Query(200, ge=1, le=2000),
) -> ApiResponse[list[dict]]:
    return ApiResponse(
        data=log_service.query(
            level=level,
            module=module,
            trace_id=trace_id,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )
    )


@app.get("/api/v1/memories")
def list_memories() -> ApiResponse[list[dict]]:
    return ApiResponse(data=memory_orchestrator.list_memories())


@app.post("/api/v1/memories")
def create_memory(payload: MemoryCreateDTO) -> ApiResponse[dict]:
    return ApiResponse(data=memory_orchestrator.create_memory(payload).model_dump())


@app.put("/api/v1/memories/{memory_id}")
def update_memory(memory_id: str, payload: MemoryCreateDTO) -> ApiResponse[dict]:
    return ApiResponse(data=memory_orchestrator.update_memory(memory_id, payload).model_dump())


@app.delete("/api/v1/memories/{memory_id}")
def delete_memory(memory_id: str) -> ApiResponse[dict]:
    memory_orchestrator.delete_memory(memory_id)
    return ApiResponse(data={"deleted": True, "memory_id": memory_id})


@app.post("/api/v1/memories/search")
def search_memories(payload: MemorySearchRequest) -> ApiResponse[list[dict]]:
    results = memory_orchestrator.search_memories(
        query=payload.query,
        top_k=payload.top_k,
        min_similarity=payload.min_similarity,
    )
    return ApiResponse(data=results)


@app.post("/api/v1/memories/extract")
def extract_memory(payload: dict) -> ApiResponse[dict]:
    memory = memory_orchestrator.create_memory(
        MemoryCreateDTO(
            memory_type="fact",
            title=payload.get("title", "Extracted Memory"),
            content=payload.get("content", "No content"),
            importance=payload.get("importance", 0.7),
            confidence=payload.get("confidence", 0.7),
            write_mode="auto",
            status="active",
            source_session_id=payload.get("session_id", ""),
            tags=payload.get("tags", []),
        )
    )
    return ApiResponse(data=memory.model_dump())


@app.post("/api/v1/memories/extract/auto")
def auto_extract_memories(payload: dict) -> ApiResponse[list[dict]]:
    session_id = payload.get("session_id", "")
    messages = payload.get("messages", [])
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    created = memory_orchestrator.auto_extract_from_messages(
        session_id, messages)
    return ApiResponse(data=[m.model_dump() for m in created])


@app.post("/api/v1/memories/compact")
def compact_memories() -> ApiResponse[dict]:
    result = memory_orchestrator.compact()
    return ApiResponse(data=result)


@app.get("/api/v1/memories/stats")
def memory_stats() -> ApiResponse[dict]:
    stats = memory_orchestrator.get_stats()
    cache_stats = memory_orchestrator.cache.stats()
    return ApiResponse(data={
        "persistent": stats.model_dump(),
        "cache": cache_stats,
    })


@app.get("/api/v1/memories/config")
def get_memory_config() -> ApiResponse[dict]:
    return ApiResponse(data=memory_orchestrator.get_config())


@app.get("/api/v1/agent/tools")
def get_agent_tools() -> ApiResponse[list[str]]:
    return ApiResponse(data=agent_service.tools())


@app.post("/api/v1/agent/stream")
def agent_stream(payload: AgentRequestDTO) -> StreamingResponse:
    return StreamingResponse(agent_service.stream(payload), media_type="text/event-stream")


@app.get("/api/v1/agent/runs/{run_id}")
def get_agent_run(run_id: str) -> ApiResponse[dict]:
    return ApiResponse(data=agent_service.get_run(run_id))


@app.post("/api/v1/exports/markdown")
def export_markdown(payload: ExportRequestDTO) -> ApiResponse[dict]:
    return ApiResponse(data=export_service.create_markdown(payload))


@app.post("/api/v1/exports/docx")
def export_docx(payload: ExportRequestDTO) -> ApiResponse[dict]:
    return ApiResponse(data=export_service.create_docx(payload))


@app.post("/api/v1/exports/xlsx")
def export_xlsx(payload: ExportRequestDTO) -> ApiResponse[dict]:
    return ApiResponse(data=export_service.create_xlsx(payload))


@app.get("/api/v1/exports/{export_id}")
def get_export(export_id: str) -> ApiResponse[dict]:
    return ApiResponse(data=export_service.get_export(export_id))


@app.get("/api/v1/exports/{export_id}/download")
def download_export(export_id: str) -> FileResponse:
    export = export_service.get_export(export_id)
    return FileResponse(export["file_path"], filename=export["file_name"])
