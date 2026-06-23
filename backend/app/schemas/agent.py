from __future__ import annotations

from pydantic import BaseModel, Field


class AgentRequestDTO(BaseModel):
    session_id: str
    task: str
    language: str = "zh-CN"
    tools: list[str] = Field(default_factory=list)
    max_steps: int = 6
    require_user_confirm_for_write: bool = True
