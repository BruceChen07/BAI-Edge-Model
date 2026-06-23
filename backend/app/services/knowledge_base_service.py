from __future__ import annotations

import shutil

from app.core.config import config
from app.core.database import get_connection
from app.schemas.knowledge_base import ChunkDTO, DocumentDTO, KnowledgeBaseCreateDTO, KnowledgeBaseDTO, KnowledgeBaseUpdateDTO
from app.services.base import BaseService
from app.utils.ids import new_id


class KnowledgeBaseService(BaseService):
    def create(self, payload: KnowledgeBaseCreateDTO) -> KnowledgeBaseDTO:
        kb_id = new_id("kb")
        kb_path = config.files_root / kb_id
        kb_path.mkdir(parents=True, exist_ok=True)
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO knowledge_bases (id, name, description, path) VALUES (?, ?, ?, ?)",
                (kb_id, payload.name, payload.description, str(kb_path)),
            )
            row = conn.execute("SELECT * FROM knowledge_bases WHERE id = ?", (kb_id,)).fetchone()
        self.log_operation("knowledge_base", "create", kb_id, "success", payload.model_dump())
        return KnowledgeBaseDTO(**dict(row))

    def list_all(self) -> list[KnowledgeBaseDTO]:
        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM knowledge_bases ORDER BY created_at DESC").fetchall()
        return [KnowledgeBaseDTO(**dict(row)) for row in rows]

    def get(self, kb_id: str) -> KnowledgeBaseDTO:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM knowledge_bases WHERE id = ?", (kb_id,)).fetchone()
        return KnowledgeBaseDTO(**dict(row))

    def update(self, kb_id: str, payload: KnowledgeBaseUpdateDTO) -> KnowledgeBaseDTO:
        with get_connection() as conn:
            conn.execute(
                "UPDATE knowledge_bases SET name = ?, description = ?, status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (payload.name, payload.description, payload.status, kb_id),
            )
            row = conn.execute("SELECT * FROM knowledge_bases WHERE id = ?", (kb_id,)).fetchone()
        self.log_operation("knowledge_base", "update", kb_id, "success", payload.model_dump())
        return KnowledgeBaseDTO(**dict(row))

    def delete(self, kb_id: str) -> None:
        with get_connection() as conn:
            conn.execute("DELETE FROM document_chunks WHERE kb_id = ?", (kb_id,))
            conn.execute("DELETE FROM documents WHERE kb_id = ?", (kb_id,))
            conn.execute("DELETE FROM knowledge_bases WHERE id = ?", (kb_id,))
        kb_path = config.files_root / kb_id
        if kb_path.exists():
            shutil.rmtree(kb_path)

    def list_files(self, kb_id: str) -> list[DocumentDTO]:
        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM documents WHERE kb_id = ? ORDER BY created_at DESC", (kb_id,)).fetchall()
        return [DocumentDTO(**dict(row)) for row in rows]

    def delete_file(self, kb_id: str, file_id: str) -> dict:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE kb_id = ? AND id = ?",
                (kb_id, file_id),
            ).fetchone()
            if row is None:
                raise ValueError(f"Document {file_id} not found in knowledge base {kb_id}")

            conn.execute("DELETE FROM document_chunks WHERE document_id = ?", (file_id,))
            conn.execute("DELETE FROM documents WHERE id = ?", (file_id,))
            conn.execute(
                "UPDATE knowledge_bases SET file_count = (SELECT COUNT(*) FROM documents WHERE kb_id = ?), chunk_count = (SELECT COUNT(*) FROM document_chunks WHERE kb_id = ?), updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (kb_id, kb_id, kb_id),
            )

        target_path = config.files_root / kb_id / "uploads" / row["file_name"]
        if target_path.exists():
            target_path.unlink()

        self.log_operation(
            "knowledge_base",
            "delete_file",
            file_id,
            "success",
            {"kb_id": kb_id, "file_name": row["file_name"]},
        )
        return {"deleted": True, "kb_id": kb_id, "file_id": file_id}

    def list_chunks(self, kb_id: str) -> list[ChunkDTO]:
        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM document_chunks WHERE kb_id = ? ORDER BY created_at DESC", (kb_id,)).fetchall()
        return [ChunkDTO(**dict(row)) for row in rows]
