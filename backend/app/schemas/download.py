"""DTO schemas for download jobs and progress tracking."""
from __future__ import annotations

from pydantic import BaseModel, Field


class DownloadJobCreateDTO(BaseModel):
    model_name: str
    source_name: str = ""
    source_url: str = ""
    total_bytes: int = 0
    chunk_size: int = Field(default=1048576, description="Default 1MB chunks")
    max_retries: int = 3
    priority: int = 2
    output_path: str = ""


class DownloadJobDTO(BaseModel):
    id: str
    model_name: str
    source_name: str = ""
    source_url: str = ""
    total_bytes: int = 0
    downloaded_bytes: int = 0
    chunk_size: int = 1048576
    status: str = "pending"
    error_message: str = ""
    retry_count: int = 0
    max_retries: int = 3
    priority: int = 2
    output_path: str = ""
    started_at: str = ""
    completed_at: str = ""
    last_progress_at: str = ""
    created_at: str = ""
    updated_at: str = ""


class DownloadProgressEvent(BaseModel):
    """Single SSE event payload during download."""
    model_name: str
    status: str
    downloaded_bytes: int = 0
    total_bytes: int = 0
    percent: float = 0.0
    speed_mbps: float = 0.0
    eta_seconds: float = 0.0
    source_name: str = ""
    error: str = ""


class MultiSourceEntry(BaseModel):
    """A single download source in the priority chain."""
    name: str
    url: str
    priority: int  # lower = try first
    enabled: bool = True
    timeout_seconds: int = 60


class MultiSourcePlan(BaseModel):
    """Resolved download plan with ordered sources."""
    model_name: str
    sources: list[MultiSourceEntry] = Field(default_factory=list)


class DownloadJobListResponse(BaseModel):
    total: int
    items: list[DownloadJobDTO]


class DownloadPullRequest(BaseModel):
    """Request to pull a model with multi-source download."""
    model_name: str
    source: str = Field(default="auto", description="auto|modelscope|huggingface|ollama")
    download_url: str = Field(default="", description="Custom direct download URL")
    chunk_size: int = Field(default=1048576, ge=65536, le=104857600, description="1MB default")
