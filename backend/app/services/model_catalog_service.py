"""
Model Catalog Service — CRUD operations for the model_catalog table.

Provides persistent storage of curated model metadata with scores,
hardware requirements, and search/filter capabilities.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.database import get_connection
from app.core.logging import get_logger
from app.schemas.catalog import (
    CatalogEntryDTO,
    CatalogListResponse,
    CatalogSyncResult,
)
from app.services.resource_monitor import extract_param_size

logger = get_logger("app.catalog")


def _row_to_dto(row: dict) -> CatalogEntryDTO:
    """Convert SQLite row dict to CatalogEntryDTO."""
    tags_raw = row.get("tags", "[]")
    try:
        tags = json.loads(tags_raw) if isinstance(tags_raw, str) else (tags_raw or [])
    except (json.JSONDecodeError, TypeError):
        tags = []
    if not isinstance(tags, list):
        tags = []

    return CatalogEntryDTO(
        id=row["id"],
        model_name=row["model_name"],
        provider=row["provider"],
        param_size=row["param_size"],
        version=row.get("version", ""),
        score_total=row.get("score_total", 0),
        score_quality=row.get("score_quality", 0),
        score_speed=row.get("score_speed", 0),
        score_fit=row.get("score_fit", 0),
        score_context=row.get("score_context", 0),
        fit_level=row.get("fit_level", "unknown"),
        estimated_tps=row.get("estimated_tps", 0),
        quantization=row.get("quantization", "Q4_K_M"),
        memory_required_gb=row.get("memory_required_gb", 0),
        vram_required_gb=row.get("vram_required_gb", 0),
        run_mode=row.get("run_mode", "CPU"),
        use_case=row.get("use_case", "general"),
        max_context=row.get("max_context", 8192),
        is_moe=bool(row.get("is_moe", 0)),
        available=bool(row.get("available", 0)),
        description=row.get("description", ""),
        tags=tags,
        source=row.get("source", "manual"),
        raw_json=row.get("raw_json", ""),
        last_synced_at=row.get("last_synced_at", ""),
        created_at=row.get("created_at", ""),
        updated_at=row.get("updated_at", ""),
    )


class ModelCatalogService:
    """CRUD service for model_catalog table."""

    # ------------------------------------------------------------------
    # Create / Upsert
    # ------------------------------------------------------------------
    def upsert(self, entry: CatalogEntryDTO) -> CatalogEntryDTO:
        now = _now()
        with get_connection() as conn:
            existing = conn.execute(
                "SELECT id FROM model_catalog WHERE model_name = ?", (entry.model_name,)
            ).fetchone()

            if existing:
                conn.execute(
                    """
                    UPDATE model_catalog SET
                        provider = ?, param_size = ?, version = ?,
                        score_total = ?, score_quality = ?, score_speed = ?,
                        score_fit = ?, score_context = ?,
                        fit_level = ?, estimated_tps = ?, quantization = ?,
                        memory_required_gb = ?, vram_required_gb = ?,
                        run_mode = ?, use_case = ?, max_context = ?,
                        is_moe = ?, available = ?, description = ?, tags = ?,
                        source = ?, raw_json = ?, last_synced_at = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        entry.provider, entry.param_size, entry.version,
                        entry.score_total, entry.score_quality, entry.score_speed,
                        entry.score_fit, entry.score_context,
                        entry.fit_level, entry.estimated_tps, entry.quantization,
                        entry.memory_required_gb, entry.vram_required_gb,
                        entry.run_mode, entry.use_case, entry.max_context,
                        int(entry.is_moe), int(entry.available),
                        entry.description, json.dumps(entry.tags),
                        entry.source, entry.raw_json, now, now,
                        existing["id"],
                    ),
                )
                entry_id = existing["id"]
            else:
                entry_id = entry.id or str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO model_catalog (
                        id, model_name, provider, param_size, version,
                        score_total, score_quality, score_speed,
                        score_fit, score_context,
                        fit_level, estimated_tps, quantization,
                        memory_required_gb, vram_required_gb,
                        run_mode, use_case, max_context,
                        is_moe, available, description, tags,
                        source, raw_json, last_synced_at,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry_id, entry.model_name, entry.provider, entry.param_size, entry.version,
                        entry.score_total, entry.score_quality, entry.score_speed,
                        entry.score_fit, entry.score_context,
                        entry.fit_level, entry.estimated_tps, entry.quantization,
                        entry.memory_required_gb, entry.vram_required_gb,
                        entry.run_mode, entry.use_case, entry.max_context,
                        int(entry.is_moe), int(entry.available),
                        entry.description, json.dumps(entry.tags),
                        entry.source, entry.raw_json, now,
                        now, now,
                    ),
                )

        row = self._get_by_id(entry_id)
        if row is None:
            return entry
        return _row_to_dto(row)

    def upsert_batch(self, entries: list[CatalogEntryDTO]) -> CatalogSyncResult:
        synced = 0
        updated = 0
        errors: list[str] = []
        for entry in entries:
            try:
                existing = self._get_by_model_name(entry.model_name)
                self.upsert(entry)
                if existing:
                    updated += 1
                else:
                    synced += 1
            except Exception as e:
                errors.append(f"{entry.model_name}: {e}")
        return CatalogSyncResult(
            synced=synced,
            updated=updated,
            skipped=0,
            source=entries[0].source if entries else "unknown",
            errors=errors,
        )

    def sync_local_models(self, local_models: list[dict[str, Any]]) -> CatalogSyncResult:
        entries: list[CatalogEntryDTO] = []
        for item in local_models:
            model_name = str(item.get("name", "")).strip()
            if not model_name:
                continue
            entries.append(
                CatalogEntryDTO(
                    id=str(uuid.uuid4()),
                    model_name=model_name,
                    provider=_infer_provider(model_name),
                    param_size=extract_param_size(model_name),
                    version="",
                    score_total=0,
                    score_quality=0,
                    score_speed=0,
                    score_fit=0,
                    score_context=0,
                    fit_level="unknown",
                    estimated_tps=0,
                    quantization=_infer_quantization(model_name),
                    memory_required_gb=0,
                    vram_required_gb=0,
                    run_mode="CPU",
                    use_case="general",
                    max_context=8192,
                    is_moe=False,
                    available=True,
                    description="",
                    tags=[],
                    source="local",
                    raw_json=json.dumps(item, ensure_ascii=False),
                    last_synced_at="",
                    created_at="",
                    updated_at="",
                )
            )
        return self.upsert_batch(entries)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    def get_by_id(self, entry_id: str) -> CatalogEntryDTO | None:
        row = self._get_by_id(entry_id)
        if row is None:
            return None
        return _row_to_dto(row)

    def get_by_model_name(self, model_name: str) -> CatalogEntryDTO | None:
        row = self._get_by_model_name(model_name)
        if row is None:
            return None
        return _row_to_dto(row)

    def _get_by_id(self, entry_id: str) -> dict | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM model_catalog WHERE id = ?", (entry_id,)
            ).fetchone()
        if row is None:
            return None
        return dict(row)

    def _get_by_model_name(self, model_name: str) -> dict | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM model_catalog WHERE model_name = ?", (model_name,)
            ).fetchone()
        if row is None:
            return None
        return dict(row)

    # ------------------------------------------------------------------
    # List / Search / Filter
    # ------------------------------------------------------------------
    def list_all(
        self,
        provider: str | None = None,
        param_size: str | None = None,
        fit_level: str | None = None,
        use_case: str | None = None,
        run_mode: str | None = None,
        min_score: float | None = None,
        sort_by: str = "score_total",
        sort_dir: str = "desc",
        offset: int = 0,
        limit: int = 20,
    ) -> CatalogListResponse:
        conditions: list[str] = []
        params: list[Any] = []

        if provider:
            conditions.append("provider = ?")
            params.append(provider)
        if param_size:
            conditions.append("param_size = ?")
            params.append(param_size)
        if fit_level:
            conditions.append("fit_level = ?")
            params.append(fit_level)
        if use_case:
            conditions.append("use_case = ?")
            params.append(use_case)
        if run_mode:
            conditions.append("run_mode = ?")
            params.append(run_mode)
        if min_score is not None:
            conditions.append("score_total >= ?")
            params.append(min_score)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        # validate sort columns to prevent SQL injection
        allowed_sort = {
            "score_total", "estimated_tps", "param_size", "model_name",
            "memory_required_gb", "max_context", "created_at",
        }
        sort_col = sort_by if sort_by in allowed_sort else "score_total"
        direction = "DESC" if sort_dir.lower() == "desc" else "ASC"

        with get_connection() as conn:
            # count
            count_row = conn.execute(
                f"SELECT COUNT(*) FROM model_catalog {where}", params
            ).fetchone()
            total = count_row[0] if count_row else 0

            # fetch
            rows = conn.execute(
                f"SELECT * FROM model_catalog {where} ORDER BY {sort_col} {direction} LIMIT ? OFFSET ?",
                params + [limit, offset],
            ).fetchall()

        items = [_row_to_dto(dict(r)) for r in rows]
        return CatalogListResponse(total=total, items=items)

    def search(
        self,
        query: str,
        offset: int = 0,
        limit: int = 20,
    ) -> CatalogListResponse:
        """Full-text search across model_name, provider, description, and tags."""
        if not query.strip():
            return self.list_all(offset=offset, limit=limit)

        like = f"%{query}%"
        with get_connection() as conn:
            count_row = conn.execute(
                """
                SELECT COUNT(*) FROM model_catalog
                WHERE model_name LIKE ? OR provider LIKE ? OR description LIKE ? OR tags LIKE ?
                """,
                (like, like, like, like),
            ).fetchone()
            total = count_row[0] if count_row else 0

            rows = conn.execute(
                """
                SELECT * FROM model_catalog
                WHERE model_name LIKE ? OR provider LIKE ? OR description LIKE ? OR tags LIKE ?
                ORDER BY score_total DESC
                LIMIT ? OFFSET ?
                """,
                (like, like, like, like, limit, offset),
            ).fetchall()

        items = [_row_to_dto(dict(r)) for r in rows]
        return CatalogListResponse(total=total, items=items)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------
    def delete(self, entry_id: str) -> bool:
        with get_connection() as conn:
            cursor = conn.execute("DELETE FROM model_catalog WHERE id = ?", (entry_id,))
            return cursor.rowcount > 0

    def count(self) -> int:
        with get_connection() as conn:
            row = conn.execute("SELECT COUNT(*) FROM model_catalog").fetchone()
            return row[0] if row else 0

    def clear(self) -> int:
        with get_connection() as conn:
            cursor = conn.execute("DELETE FROM model_catalog")
            return cursor.rowcount


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _infer_provider(model_name: str) -> str:
    name = model_name.lower()
    if name.startswith("qwen"):
        return "Qwen"
    if name.startswith("llama"):
        return "Meta"
    if name.startswith("gemma"):
        return "Google"
    if name.startswith("phi"):
        return "Microsoft"
    if name.startswith("deepseek"):
        return "DeepSeek"
    return "unknown"


def _infer_quantization(model_name: str) -> str:
    lowered = model_name.lower()
    for token in ("q2", "q3", "q4", "q5", "q6", "q8"):
        if token in lowered:
            return token.upper()
    return "Q4_K_M"
