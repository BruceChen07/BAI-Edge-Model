"""DTO schemas for model_catalog."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CatalogEntryDTO(BaseModel):
    id: str
    model_name: str
    provider: str
    param_size: str
    version: str = ""
    score_total: float = 0
    score_quality: float = 0
    score_speed: float = 0
    score_fit: float = 0
    score_context: float = 0
    fit_level: str = "unknown"
    estimated_tps: float = 0
    quantization: str = "Q4_K_M"
    memory_required_gb: float = 0
    vram_required_gb: float = 0
    run_mode: str = "CPU"
    use_case: str = "general"
    max_context: int = 8192
    is_moe: bool = False
    available: bool = False
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    source: str = "manual"
    raw_json: str = ""
    last_synced_at: str = ""
    created_at: str = ""
    updated_at: str = ""


class CatalogSyncRequest(BaseModel):
    source: str = Field(default="llmfit", description="llmfit|curated|manual")
    limit: int = Field(default=200, ge=1, le=500)
    use_case: str = Field(default="general")


class CatalogSyncResult(BaseModel):
    synced: int = 0
    updated: int = 0
    skipped: int = 0
    source: str = "unknown"
    errors: list[str] = Field(default_factory=list)


class CatalogSearchRequest(BaseModel):
    q: str = Field(default="", description="Search query across model_name, provider, description, tags")
    provider: str | None = None
    param_size: str | None = None
    fit_level: str | None = None
    use_case: str | None = None
    run_mode: str | None = None
    min_score: float | None = None
    sort_by: str = Field(default="score_total", description="score_total|estimated_tps|param_size|model_name")
    sort_dir: str = Field(default="desc", description="asc|desc")
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class CatalogListResponse(BaseModel):
    total: int
    items: list[CatalogEntryDTO]
