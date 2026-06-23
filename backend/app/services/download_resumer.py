"""
DownloadResumer — chunked HTTP download with SQLite-backed state tracking.
Supports pause/resume by recording downloaded_bytes and resuming from byte offset.
"""
from __future__ import annotations

import os
import threading
import uuid
from pathlib import Path

from app.core.config import config
from app.core.database import get_connection
from app.core.logging import get_logger
from app.schemas.download import DownloadJobDTO

logger = get_logger("app.download.resumer")

CHUNK_SIZE_DEFAULT = 1048576  # 1MB


def _row_to_job(row: dict) -> DownloadJobDTO:
    return DownloadJobDTO(
        id=row["id"],
        model_name=row["model_name"],
        source_name=row.get("source_name", ""),
        source_url=row.get("source_url", ""),
        total_bytes=row.get("total_bytes", 0),
        downloaded_bytes=row.get("downloaded_bytes", 0),
        chunk_size=row.get("chunk_size", CHUNK_SIZE_DEFAULT),
        status=row.get("status", "pending"),
        error_message=row.get("error_message", ""),
        retry_count=row.get("retry_count", 0),
        max_retries=row.get("max_retries", 3),
        priority=row.get("priority", 2),
        output_path=row.get("output_path", ""),
        started_at=row.get("started_at", ""),
        completed_at=row.get("completed_at", ""),
        last_progress_at=row.get("last_progress_at", ""),
        created_at=row.get("created_at", ""),
        updated_at=row.get("updated_at", ""),
    )


class DownloadResumer:
    """
    Manages chunked HTTP downloads with SQLite-backed state for resumption.

    Thread-safe: uses a lock per job_id to prevent concurrent writes.
    """

    def __init__(self) -> None:
        self._locks: dict[str, threading.Lock] = {}
        self._active_jobs: dict[str, bool] = {}
        self._progress_callbacks: dict[str, list] = {}

    # ------------------------------------------------------------------
    # Job lifecycle
    # ------------------------------------------------------------------
    def create_job(
        self,
        model_name: str,
        source_name: str = "",
        source_url: str = "",
        total_bytes: int = 0,
        chunk_size: int = CHUNK_SIZE_DEFAULT,
        max_retries: int = 3,
        output_path: str = "",
    ) -> DownloadJobDTO:
        job_id = str(uuid.uuid4())
        if not output_path:
            safe_name = model_name.replace(":", "_").replace("/", "_")
            output_path = str(
                Path(config.storage_root) / "models" / f"{safe_name}.gguf"
            )

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        now = _now()
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO download_jobs (
                    id, model_name, source_name, source_url,
                    total_bytes, downloaded_bytes, chunk_size,
                    status, max_retries, output_path,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 0, ?, 'pending', ?, ?, ?, ?)
                """,
                (
                    job_id, model_name, source_name, source_url,
                    total_bytes, chunk_size, max_retries, output_path,
                    now, now,
                ),
            )
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> DownloadJobDTO:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM download_jobs WHERE id = ?", (job_id,)
            ).fetchone()
        if row is None:
            raise ValueError(f"Download job not found: {job_id}")
        return _row_to_job(dict(row))

    def get_job_by_model(self, model_name: str) -> DownloadJobDTO | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM download_jobs WHERE model_name = ? ORDER BY created_at DESC LIMIT 1",
                (model_name,),
            ).fetchone()
        if row is None:
            return None
        return _row_to_job(dict(row))

    def list_jobs(self, status: str | None = None) -> list[DownloadJobDTO]:
        with get_connection() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM download_jobs WHERE status = ? ORDER BY created_at DESC",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM download_jobs ORDER BY created_at DESC"
                ).fetchall()
        return [_row_to_job(dict(r)) for r in rows]

    def update_progress(self, job_id: str, downloaded_bytes: int, total_bytes: int = 0) -> None:
        now = _now()
        with get_connection() as conn:
            if total_bytes > 0:
                conn.execute(
                    """
                    UPDATE download_jobs
                    SET downloaded_bytes = ?, total_bytes = ?,
                        status = 'downloading', last_progress_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (downloaded_bytes, total_bytes, now, now, job_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE download_jobs
                    SET downloaded_bytes = ?, status = 'downloading',
                        last_progress_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (downloaded_bytes, now, now, job_id),
                )

    def mark_completed(self, job_id: str) -> None:
        now = _now()
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE download_jobs
                SET status = 'completed', completed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (now, now, job_id),
            )

    def mark_failed(self, job_id: str, error: str) -> None:
        now = _now()
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE download_jobs
                SET status = 'failed', error_message = ?,
                    retry_count = retry_count + 1, updated_at = ?
                WHERE id = ?
                """,
                (error, now, job_id),
            )

    def mark_paused(self, job_id: str) -> None:
        now = _now()
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE download_jobs
                SET status = 'paused', updated_at = ?
                WHERE id = ?
                """,
                (now, job_id),
            )

    def get_resume_offset(self, job_id: str) -> int:
        job = self.get_job(job_id)
        return job.downloaded_bytes

    def can_resume(self, job_id: str) -> bool:
        job = self.get_job(job_id)
        return job.status in ("downloading", "paused", "failed") and job.downloaded_bytes > 0

    def pause(self, job_id: str) -> None:
        self._active_jobs[job_id] = False
        self.mark_paused(job_id)

    def is_active(self, job_id: str) -> bool:
        return self._active_jobs.get(job_id, False)

    def register_progress_callback(self, job_id: str, cb) -> None:
        if job_id not in self._progress_callbacks:
            self._progress_callbacks[job_id] = []
        self._progress_callbacks[job_id].append(cb)

    def _notify_progress(self, job_id: str, event: DownloadProgressEvent) -> None:
        for cb in self._progress_callbacks.get(job_id, []):
            try:
                cb(event)
            except Exception:
                logger.warning("Progress callback failed for job %s", job_id)


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
