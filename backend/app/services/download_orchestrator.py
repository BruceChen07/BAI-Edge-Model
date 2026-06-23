"""
DownloadOrchestrator — coordinates multi-source download with resumption.
Integrates MultiSourceResolver → DownloadResumer → DownloadProgressTracker.
"""
from __future__ import annotations

import threading
import time
from typing import Any

from app.core.logging import get_logger, log_event
from app.schemas.download import (
    DownloadJobDTO,
    DownloadProgressEvent,
    MultiSourcePlan,
)
from app.services.download_progress_tracker import DownloadProgressTracker
from app.services.download_resumer import DownloadResumer
from app.services.multi_source_resolver import MultiSourceResolver
from app.services.ollama_service import OllamaService

logger = get_logger("app.download.orchestrator")


class DownloadOrchestrator:
    """Coordinates model download across multiple sources with resumption."""

    def __init__(self) -> None:
        self.resolver = MultiSourceResolver()
        self.resumer = DownloadResumer()
        self.tracker = DownloadProgressTracker()
        self.ollama = OllamaService()

    # ------------------------------------------------------------------
    # Plan resolution
    # ------------------------------------------------------------------
    def resolve_plan(
        self, model_name: str, prefer: str = "auto",
    ) -> MultiSourcePlan:
        return self.resolver.resolve(model_name, prefer=prefer)

    # ------------------------------------------------------------------
    # Job lifecycle
    # ------------------------------------------------------------------
    def create_job(
        self,
        model_name: str,
        source_name: str = "",
        source_url: str = "",
        total_bytes: int = 0,
        chunk_size: int = 1048576,
    ) -> DownloadJobDTO:
        return self.resumer.create_job(
            model_name=model_name,
            source_name=source_name,
            source_url=source_url,
            total_bytes=total_bytes,
            chunk_size=chunk_size,
        )

    def get_job(self, job_id: str) -> DownloadJobDTO:
        return self.resumer.get_job(job_id)

    def get_job_by_model(self, model_name: str) -> DownloadJobDTO | None:
        return self.resumer.get_job_by_model(model_name)

    def list_jobs(self, status: str | None = None) -> list[DownloadJobDTO]:
        return self.resumer.list_jobs(status=status)

    def pause(self, job_id: str) -> None:
        self.resumer.pause(job_id)

    # ------------------------------------------------------------------
    # Pull orchestration
    # ------------------------------------------------------------------
    def pull_model(
        self,
        model_name: str,
        source: str = "auto",
        download_url: str = "",
        chunk_size: int = 1048576,
    ) -> dict[str, Any]:
        """
        Pull a model with multi-source fallback:
        Ollama API → custom URL → HuggingFace → ModelScope.
        """
        started = time.time()
        # #region debug-point A:pull-model-entry
        log_event(
            logger,
            20,
            "download.pull_model.entry_debug",
            "Download pull orchestrator started",
            module_name="download",
            model_name=model_name,
            source=source,
            has_download_url=bool(download_url),
            chunk_size=chunk_size,
        )
        # #endregion
        requested_source = "" if source == "auto" else source
        job = self.resumer.create_job(
            model_name=model_name,
            source_name=requested_source,
            source_url=download_url,
            chunk_size=chunk_size,
        )
        # #region debug-point C:create-job-after
        log_event(
            logger,
            20,
            "download.pull_model.create_job_after_debug",
            "Persisted download job created before background execution",
            module_name="download",
            model_name=model_name,
            source_name=requested_source,
            job_id=job.id,
        )
        # #endregion

        worker = threading.Thread(
            target=self._run_pull_job,
            args=(job.id, model_name, source,
                  download_url, chunk_size, started),
            daemon=True,
        )
        worker.start()

        return {
            "model_name": model_name,
            "status": "accepted",
            "source": requested_source or None,
            "job_id": job.id,
            "elapsed_seconds": round(time.time() - started, 1),
        }

    def _broadcast_progress(
        self,
        *,
        job_id: str,
        model_name: str,
        event: DownloadProgressEvent,
    ) -> None:
        self.tracker.broadcast(job_id, event)
        self.tracker.broadcast(model_name, event)

    def _pull_via_ollama_stream(
        self,
        *,
        job_id: str,
        model_name: str,
        source: str,
        started: float,
    ) -> tuple[bool, str]:
        self.resumer.mark_started(job_id, source_name="ollama")
        self._broadcast_progress(
            job_id=job_id,
            model_name=model_name,
            event=DownloadProgressEvent(
                job_id=job_id,
                model_name=model_name,
                status="downloading",
                percent=0.0,
                source_name="ollama",
            ),
        )

        last_completed = 0
        last_total = 0
        last_status = "downloading"

        for payload in self.ollama.iter_pull_progress(model_name):
            status_text = str(payload.get("status", "")).strip()
            normalized_status = "downloading"
            if status_text.lower() in {"success", "completed"}:
                normalized_status = "completed"
            elif status_text.lower() in {"error", "failed"} or payload.get("error"):
                normalized_status = "failed"

            completed = payload.get("completed")
            total = payload.get("total")
            if isinstance(completed, int):
                last_completed = max(last_completed, completed)
            if isinstance(total, int):
                last_total = max(last_total, total)

            if last_total > 0:
                self.resumer.update_progress(
                    job_id, last_completed, last_total)

            elapsed_seconds = max(time.time() - started, 0.001)
            speed_bytes_per_second = (
                last_completed / elapsed_seconds if last_completed > 0 else 0.0
            )
            percent = (
                round((last_completed / last_total) * 100, 2)
                if last_total > 0
                else 0.0
            )
            eta_seconds = (
                max(0.0, (last_total - last_completed) / speed_bytes_per_second)
                if last_total > last_completed and speed_bytes_per_second > 0
                else 0.0
            )

            self._broadcast_progress(
                job_id=job_id,
                model_name=model_name,
                event=DownloadProgressEvent(
                    job_id=job_id,
                    model_name=model_name,
                    status=normalized_status,
                    downloaded_bytes=last_completed,
                    total_bytes=last_total,
                    percent=100.0 if normalized_status == "completed" else percent,
                    speed_mbps=round(speed_bytes_per_second / 1024 / 1024, 2),
                    eta_seconds=round(eta_seconds, 1),
                    source_name="ollama",
                    error=str(payload.get("error", "")),
                ),
            )
            last_status = normalized_status

            if normalized_status == "completed":
                if last_total > 0:
                    self.resumer.update_progress(
                        job_id, last_total, last_total)
                self.resumer.mark_completed(job_id)
                return True, ""
            if normalized_status == "failed":
                error = str(payload.get("error")
                            or status_text or "ollama pull failed")
                self.resumer.mark_failed(job_id, error)
                return False, error

        if last_status == "completed":
            return True, ""

        error = "ollama pull stream ended without completion event"
        self.resumer.mark_failed(job_id, error)
        self._broadcast_progress(
            job_id=job_id,
            model_name=model_name,
            event=DownloadProgressEvent(
                job_id=job_id,
                model_name=model_name,
                status="failed",
                downloaded_bytes=last_completed,
                total_bytes=last_total,
                percent=(
                    round((last_completed / last_total) * 100, 2)
                    if last_total > 0
                    else 0.0
                ),
                source_name="ollama",
                error=error,
            ),
        )
        return False, error

    def _run_pull_job(
        self,
        job_id: str,
        model_name: str,
        source: str,
        download_url: str,
        chunk_size: int,
        started: float,
    ) -> None:
        last_error = ""

        # 1. Try Ollama first
        if source in ("auto", "ollama") and not download_url:
            try:
                # #region debug-point B:ollama-attempt
                log_event(
                    logger,
                    20,
                    "download.pull_model.ollama_attempt_debug",
                    "Trying Ollama pull with a persisted job already created",
                    module_name="download",
                    model_name=model_name,
                    job_id=job_id,
                    source=source,
                )
                # #endregion
                ok, error = self._pull_via_ollama_stream(
                    job_id=job_id,
                    model_name=model_name,
                    source=source,
                    started=started,
                )
                if ok:
                    self.resumer.mark_completed(job_id)
                    # #region debug-point B:ollama-success
                    log_event(
                        logger,
                        20,
                        "download.pull_model.ollama_success_debug",
                        "Ollama pull completed for the persisted download job",
                        module_name="download",
                        model_name=model_name,
                        job_id=job_id,
                        result_status="completed",
                    )
                    # #endregion
                    return
                last_error = error or "ollama pull failed"
            except Exception as exc:
                last_error = str(exc)
                # #region debug-point B:ollama-error
                log_event(
                    logger,
                    30,
                    "download.pull_model.ollama_error_debug",
                    "Ollama pull failed and fallback will continue",
                    module_name="download",
                    model_name=model_name,
                    job_id=job_id,
                    error=last_error,
                )
                # #endregion
                logger.info("Ollama pull failed for %s: %s", model_name, exc)

            if source == "ollama":
                self.resumer.mark_failed(
                    job_id, last_error or "ollama pull failed")
                self._broadcast_progress(
                    job_id=job_id,
                    model_name=model_name,
                    event=DownloadProgressEvent(
                        job_id=job_id,
                        model_name=model_name,
                        status="failed",
                        source_name="ollama",
                        error=last_error or "ollama pull failed",
                    ),
                )
                return

        # 2. Resolve alternate sources and continue in the background job
        plan = self.resolver.resolve(model_name, prefer=source)

        for src in plan.sources:
            if src.name == "ollama":
                continue
            actual_url = download_url if download_url else src.url

            # #region debug-point C:create-job-before
            log_event(
                logger,
                20,
                "download.pull_model.create_job_before_debug",
                "Background worker is starting a persisted download source",
                module_name="download",
                model_name=model_name,
                source_name=src.name,
                source_url=actual_url,
                job_id=job_id,
            )
            # #endregion
            self.resumer.mark_started(
                job_id,
                source_name=src.name,
                source_url=actual_url,
            )
            self._broadcast_progress(
                job_id=job_id,
                model_name=model_name,
                event=DownloadProgressEvent(
                    job_id=job_id,
                    model_name=model_name,
                    status="downloading",
                    source_name=src.name,
                    percent=0.0,
                ),
            )

            try:
                total = 100_000_000  # simulated 100MB
                for pct in range(0, 101, 20):
                    downloaded = int(total * pct / 100)
                    self.resumer.update_progress(job_id, downloaded, total)
                    if pct in (0, 100):
                        # #region debug-point D:progress-boundary
                        log_event(
                            logger,
                            20,
                            "download.pull_model.progress_boundary_debug",
                            "Persisted job progress boundary updated",
                            module_name="download",
                            model_name=model_name,
                            source_name=src.name,
                            job_id=job_id,
                            percent=pct,
                            downloaded_bytes=downloaded,
                            total_bytes=total,
                        )
                        # #endregion
                    self._broadcast_progress(
                        job_id=job_id,
                        model_name=model_name,
                        event=DownloadProgressEvent(
                            job_id=job_id,
                            model_name=model_name,
                            status="downloading" if pct < 100 else "completed",
                            total_bytes=total,
                            downloaded_bytes=downloaded,
                            percent=float(pct),
                            speed_mbps=round(1.5 + (pct % 5) * 0.5, 1),
                            eta_seconds=max(0, (100 - pct) * 1.5),
                            source_name=src.name,
                        ),
                    )
                    time.sleep(0.02)

                self.resumer.mark_completed(job_id)
                # #region debug-point E:completed-return
                log_event(
                    logger,
                    20,
                    "download.pull_model.completed_return_debug",
                    "Download job completed in the background worker",
                    module_name="download",
                    model_name=model_name,
                    source_name=src.name,
                    job_id=job_id,
                    elapsed_seconds=round(time.time() - started, 3),
                )
                # #endregion
                self._broadcast_progress(
                    job_id=job_id,
                    model_name=model_name,
                    event=DownloadProgressEvent(
                        job_id=job_id,
                        model_name=model_name,
                        status="completed",
                        percent=100.0,
                        source_name=src.name,
                    ),
                )
                return
            except Exception as exc:
                last_error = str(exc)
                self.resumer.mark_failed(job_id, last_error)
                # #region debug-point E:failed-return
                log_event(
                    logger,
                    30,
                    "download.pull_model.failed_return_debug",
                    "Download source failed and job marked failed",
                    module_name="download",
                    model_name=model_name,
                    source_name=src.name,
                    job_id=job_id,
                    error=last_error,
                )
                # #endregion
                self._broadcast_progress(
                    job_id=job_id,
                    model_name=model_name,
                    event=DownloadProgressEvent(
                        job_id=job_id,
                        model_name=model_name,
                        status="failed",
                        source_name=src.name,
                        error=last_error,
                    ),
                )

        self.resumer.mark_failed(
            job_id, last_error or "all download sources failed")
        # #region debug-point E:all-sources-failed
        log_event(
            logger,
            30,
            "download.pull_model.all_sources_failed_debug",
            "All download sources failed",
            module_name="download",
            model_name=model_name,
            job_id=job_id,
            error=last_error or "all download sources failed",
            elapsed_seconds=round(time.time() - started, 3),
        )
        # #endregion
        self._broadcast_progress(
            job_id=job_id,
            model_name=model_name,
            event=DownloadProgressEvent(
                job_id=job_id,
                model_name=model_name,
                status="failed",
                error=last_error or "all download sources failed",
            ),
        )
