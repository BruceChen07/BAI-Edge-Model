from __future__ import annotations

from pydantic import BaseModel


class KnowledgeBaseCreateDTO(BaseModel):
    name: str
    description: str = ""


class KnowledgeBaseUpdateDTO(BaseModel):
    name: str
    description: str = ""
    status: str = "ready"


class KnowledgeBaseDTO(BaseModel):
    id: str
    name: str
    description: str
    path: str
    status: str
    file_count: int
    chunk_count: int
    created_at: str | None = None
    updated_at: str | None = None


class DocumentDTO(BaseModel):
    id: str
    kb_id: str
    file_name: str
    file_ext: str
    mime_type: str
    file_size: int
    storage_path: str
    sha256: str
    parse_status: str
    ocr_status: str
    index_status: str
    created_at: str | None = None
    updated_at: str | None = None


class ChunkDTO(BaseModel):
    id: str
    document_id: str
    kb_id: str
    chunk_index: int
    content: str
    content_hash: str
    page_no: int | None = None
    sheet_name: str = ""
    slide_no: int | None = None
    heading_path: str = ""
    token_count: int
    vector_ref: str = ""
    created_at: str | None = None
