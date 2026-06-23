"""
Auto-download service that ensures at least one capable edge model
is available locally on first deployment. Detects hardware, picks the
best-fit model from the curated catalog, and pulls it via Ollama.
"""
from __future__ import annotations

import logging
import os
import time
import traceback
from typing import Any

from app.core.database import get_connection
from app.core.logging import get_logger, log_event
from app.core.request_context import get_trace_id
from app.services.ollama_service import OllamaService
from app.services.resource_monitor import (
    CURATED_CATALOG,
    ModelRequirement,
    build_pull_fallbacks,
    get_full_resource_snapshot,
    select_best_model_for_hardware,
)

logger = get_logger("app.model_download")

# Read env for ModelScope preference at import time
_PREFER_MODELSCOPE = os.environ.get("OLLAMA_PREFER_MODELSCOPE", "").lower() in (
    "1", "true", "yes",
)


class ModelDownloadService:
    """Handles first-run model provisioning for edge deployments."""

    def __init__(self) -> None:
        self.ollama = OllamaService()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def ensure_default_model(self) -> dict[str, Any]:
        """
        Ensure at least one model is available locally.
        If no models exist, auto-detect hardware and pull the best-fitting
        model from the curated catalog. Updates the default_model setting.
        """
        started_at = time.time()
        trace_id = get_trace_id()

        # 1. Check currently available models
        available = self.ollama.list_models()
        if available:
            existing_names = [m["name"] for m in available]
            log_event(
                logger, logging.INFO,
                "model_download.models_already_available",
                f"Found {len(available)} model(s) already available; skipping auto-download",
                module_name="model_download", trace_id=trace_id,
                model_count=len(available), model_names=existing_names,
            )
            self._sync_default_model(existing_names)
            return {
                "action": "skip",
                "reason": f"{len(available)} model(s) already available",
                "models": existing_names,
                "elapsed_ms": round((time.time() - started_at) * 1000, 2),
            }

        # 2. Detect hardware and select best model
        best = select_best_model_for_hardware()
        if best is None:
            # Fallback to smallest model
            best = CURATED_CATALOG[-1]
            log_event(
                logger, logging.WARNING,
                "model_download.insufficient_hardware",
                f"Even the smallest model may struggle on this device. Pulling {best.ollama_name} as fallback.",
                module_name="model_download", trace_id=trace_id,
                fallback_model=best.ollama_name,
            )

        snapshot = get_full_resource_snapshot()
        log_event(
            logger, logging.INFO,
            "model_download.auto_select",
            f"Auto-selected {best.display_name} ({best.ollama_name}) for this device",
            module_name="model_download", trace_id=trace_id,
            selected_model=best.ollama_name,
            ram_required_gb=best.ram_gb,
            approx_size_gb=best.approx_size_gb,
            hardware=snapshot,
        )

        # 3. Pull the model — try Ollama registry first, then ModelScope fallback
        pull_names = build_pull_fallbacks(
            best.ollama_name, prefer_modelscope=_PREFER_MODELSCOPE)
        last_error: str | None = None
        result: dict[str, Any] = {}

        for pull_name in pull_names:
            pull_started = time.time()
            try:
                result = self.ollama.pull_model(pull_name)
            except Exception:
                last_error = traceback.format_exc()
                log_event(
                    logger, logging.WARNING,
                    "model_download.pull_attempt_failed",
                    f"Pull attempt failed for {pull_name}, trying next fallback",
                    module_name="model_download", trace_id=trace_id,
                    pull_name=pull_name, error=last_error,
                )
                continue

            if result.get("status") in ("failed", "error"):
                last_error = result.get("error", "unknown pull error")
                log_event(
                    logger, logging.WARNING,
                    "model_download.pull_attempt_error",
                    f"Pull returned error for {pull_name}, trying next fallback",
                    module_name="model_download", trace_id=trace_id,
                    pull_name=pull_name, error=last_error,
                )
                continue

            # Success — record which name was used
            pull_elapsed = round(time.time() - pull_started, 1)
            used_modelscope = "modelscope.cn/" in pull_name
            log_event(
                logger, logging.INFO,
                "model_download.pull_succeeded",
                f"Successfully pulled model via {pull_name}",
                module_name="model_download", trace_id=trace_id,
                pull_name=pull_name, used_modelscope=used_modelscope,
                elapsed_seconds=pull_elapsed,
            )
            break
        else:
            # All fallbacks exhausted
            log_event(
                logger, logging.ERROR,
                "model_download.all_pulls_failed",
                f"All pull attempts failed for {best.ollama_name}",
                module_name="model_download", trace_id=trace_id,
                attempted_names=pull_names, last_error=last_error,
            )
            return {
                "action": "failed",
                "model": best.ollama_name,
                "attempted": pull_names,
                "error": last_error or "all pull sources failed",
                "elapsed_ms": round((time.time() - started_at) * 1000, 2),
            }

        # 4. Update default model in DB
        self._set_default_model(best.ollama_name)

        log_event(
            logger, logging.INFO,
            "model_download.completed",
            f"Successfully pulled {best.display_name} ({best.ollama_name})",
            module_name="model_download", trace_id=trace_id,
            model=best.ollama_name,
            pull_elapsed_seconds=pull_elapsed,
            total_elapsed_ms=round((time.time() - started_at) * 1000, 2),
        )

        return {
            "action": "pulled",
            "model": best.ollama_name,
            "display_name": best.display_name,
            "approx_size_gb": best.approx_size_gb,
            "pull_elapsed_seconds": pull_elapsed,
            "total_elapsed_ms": round((time.time() - started_at) * 1000, 2),
        }

    def pull_model_manually(self, model_name: str) -> dict[str, Any]:
        """Pull a user-requested model, trying Ollama registry first then ModelScope."""
        started_at = time.time()
        trace_id = get_trace_id()
        pull_names = build_pull_fallbacks(
            model_name, prefer_modelscope=_PREFER_MODELSCOPE)

        log_event(
            logger, logging.INFO,
            "model_download.manual_pull.started",
            f"Manual pull for {model_name}, will try: {pull_names}",
            module_name="model_download", trace_id=trace_id,
            model=model_name, fallbacks=pull_names,
        )

        last_error: str | None = None
        for pull_name in pull_names:
            try:
                result = self.ollama.pull_model(pull_name)
                if result.get("status") not in ("failed", "error"):
                    self._set_default_model(pull_name)
                    log_event(
                        logger, logging.INFO,
                        "model_download.manual_pull.completed",
                        f"Manual pull completed via {pull_name}",
                        module_name="model_download", trace_id=trace_id,
                        model=pull_name,
                        elapsed_ms=round((time.time() - started_at) * 1000, 2),
                    )
                    return result
                last_error = result.get("error", "pull returned error")
            except Exception:
                last_error = traceback.format_exc()

        log_event(
            logger, logging.ERROR,
            "model_download.manual_pull.failed",
            f"All pull attempts failed for {model_name}",
            module_name="model_download", trace_id=trace_id,
            model=model_name, attempted=pull_names, error=last_error,
        )
        return {
            "model": model_name,
            "status": "failed",
            "attempted": pull_names,
            "error": last_error or "all sources failed",
        }

    def get_catalog(self) -> list[dict[str, Any]]:
        """Return the curated catalog with hardware suitability info."""
        snapshot = get_full_resource_snapshot()
        results = []
        for req in CURATED_CATALOG:
            ram_ok = (snapshot["memory"].get(
                "available_gb") or 0) >= req.ram_gb * 0.8
            vram_available = 0.0
            if snapshot["gpu"].get("available"):
                for g in snapshot["gpu"].get("gpus", []):
                    vram_available += g["memory_free_mb"] / 1024.0
            vram_ok = req.vram_gb is None or vram_available >= req.vram_gb * 0.8
            results.append({
                "ollama_name": req.ollama_name,
                "param_size": req.param_size,
                "display_name": req.display_name,
                "ram_gb": req.ram_gb,
                "vram_gb": req.vram_gb,
                "cpu_cores": req.cpu_cores,
                "approx_size_gb": req.approx_size_gb,
                "description": req.description,
                "tags": req.tags,
                "modelscope_name": req.modelscope_name,
                "feasible": ram_ok and vram_ok,
            })
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _set_default_model(self, model_name: str) -> None:
        """Persist the default model name in app_settings."""
        try:
            with get_connection() as conn:
                conn.execute(
                    "UPDATE app_settings SET default_model = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1",
                    (model_name,),
                )
        except Exception:
            logger.warning("Failed to persist default_model=%s",
                           model_name, exc_info=True)

    def _sync_default_model(self, existing_names: list[str]) -> None:
        """Ensure the default_model setting points to an actually available model."""
        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT default_model FROM app_settings WHERE id = 1"
                ).fetchone()
            current_default = row["default_model"] if row else ""
            if current_default not in existing_names and existing_names:
                self._set_default_model(existing_names[0])
        except Exception:
            pass
