from __future__ import annotations

from pydantic import BaseModel


class MemoryCreateDTO(BaseModel):
    memory_type: str
    title: str
    content: str
    importance: float = 0.5
    confidence: float = 0.5
    write_mode: str = "manual"
    status: str = "active"


class MemoryDTO(MemoryCreateDTO):
    id: str
