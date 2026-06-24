from __future__ import annotations

from pydantic import BaseModel, Field


class SessionCreateDTO(BaseModel):
    title: str = "New Session"
    mode: str = "chat"
    language: str = "zh-CN"
    rag_enabled: bool = True
    agent_enabled: bool = False


class SessionDTO(BaseModel):
    id: str
    title: str
    mode: str
    language: str
    rag_enabled: bool
    agent_enabled: bool
    last_message_at: str | None = None


class ChatAttachmentDTO(BaseModel):
    id: str
    session_id: str
    message_id: str | None = None
    file_name: str
    file_ext: str
    mime_type: str
    file_size: int
    attachment_type: str
    storage_path: str
    extracted_text_preview: str = ""
    ocr_status: str = "skipped"
    status: str = "uploaded"
    created_at: str | None = None


class MessageDTO(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    content_type: str
    model_name: str
    prompt_tokens: int
    completion_tokens: int
    status: str
    attachments: list[ChatAttachmentDTO] = Field(default_factory=list)


class ChatRequestDTO(BaseModel):
    session_id: str
    query: str
    model_name: str | None = None
    language: str = "zh-CN"
    rag_enabled: bool = True
    agent_enabled: bool = False
    knowledge_base_ids: list[str] = Field(default_factory=list)
    attachment_ids: list[str] = Field(default_factory=list)
    top_k: int = 5
    score_threshold: float = 0.1
    include_memory: bool = True


class ChatResponseDTO(BaseModel):
    answer: str
    citations: list[dict]
    model_used: str
