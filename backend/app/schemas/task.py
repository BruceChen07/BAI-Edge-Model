from __future__ import annotations

from pydantic import BaseModel


class TaskDTO(BaseModel):
    id: str
    task_type: str
    related_id: str
    status: str
    progress: float
    error_code: str
    error_message: str
    started_at: str
    finished_at: str
