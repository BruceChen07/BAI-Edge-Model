from __future__ import annotations

import json as _json
from typing import Any

from pydantic import BaseModel, Field, field_validator


class MemoryCreateDTO(BaseModel):
    memory_type: str
    title: str
    content: str
    importance: float = 0.5
    confidence: float = 0.5
    write_mode: str = "manual"
    status: str = "active"
    source_session_id: str | None = None
    tags: list[str] = Field(default_factory=list)


class MemoryDTO(MemoryCreateDTO):
    id: str
    content_hash: str = ""
    access_count: int = 0
    last_accessed_at: str = ""
    expires_at: str = ""
    created_at: str = ""
    updated_at: str = ""

    @field_validator("tags", mode="before")
    @classmethod
    def parse_tags(cls, v: Any) -> list[str]:
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            try:
                return _json.loads(v)
            except Exception:
                return []
        return []


class MemorySearchRequest(BaseModel):
    query: str
    top_k: int = 5
    min_similarity: float = 0.4


class MemorySearchResult(BaseModel):
    id: str
    title: str
    content: str
    memory_type: str
    importance: float
    score: float


class MemoryConfigDTO(BaseModel):
    short_term_ttl_seconds: int = 300
    short_term_max_entries: int = 100
    trigger_turn_count: int = 10
    extract_min_confidence: float = 0.6
    dedup_threshold: float = 0.85
    top_k: int = 5


class MemoryStatsDTO(BaseModel):
    total_count: int
    type_distribution: dict[str, int]
    total_size_bytes: int
    active_count: int
    archived_count: int
