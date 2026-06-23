from __future__ import annotations

from pydantic import BaseModel


class ExportRequestDTO(BaseModel):
    source_type: str
    source_id: str
    title: str = "Export"
