from __future__ import annotations

import shutil
from pathlib import Path

from app.core.config import config
from app.core.database import get_connection
from app.schemas.knowledge_base import (
    ChunkDTO,
    DocumentDTO,
    KnowledgeBaseCreateDTO,
    KnowledgeBaseDTO,
    KnowledgeBaseUpdateDTO,
)
from app.services.base import BaseService, sha256_text
from app.services.document_chunking import build_structured_chunks
from app.services.parser_service import ParserService
from app.services.task_service import TaskService
from app.utils.ids import new_id


class KnowledgeBaseService(BaseService):
    def __init__(self) -> None:
        self.parser_service = ParserService()
        self.task_service = TaskService()

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

    def get_stats(self, kb_id: str) -> dict:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT
                    COALESCE(SUM(file_size), 0) AS total_size_bytes,
                    COUNT(*) AS file_count
                FROM documents
                WHERE kb_id = ?
                """,
                (kb_id,),
            ).fetchone()
            token_row = conn.execute(
                """
                SELECT
                    COALESCE(COUNT(*), 0) AS chunk_count,
                    COALESCE(SUM(token_count), 0) AS token_count
                FROM document_chunks
                WHERE kb_id = ?
                """,
                (kb_id,),
            ).fetchone()
        return {
            "kb_id": kb_id,
            "total_size_bytes": int(row["total_size_bytes"]),
            "file_count": int(row["file_count"]),
            "chunk_count": int(token_row["chunk_count"]),
            "token_count": int(token_row["token_count"]),
        }

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

    def list_chunks(
        self,
        kb_id: str,
        *,
        document_id: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> dict:
        where_sql = "WHERE dc.kb_id = ?"
        params: list[object] = [kb_id]
        if document_id:
            where_sql += " AND dc.document_id = ?"
            params.append(document_id)

        with get_connection() as conn:
            total_row = conn.execute(
                f"""
                SELECT COUNT(*) AS total
                FROM document_chunks dc
                {where_sql}
                """,
                tuple(params),
            ).fetchone()
            rows = conn.execute(
                f"""
                SELECT dc.*, d.file_name
                FROM document_chunks dc
                JOIN documents d ON d.id = dc.document_id
                {where_sql}
                ORDER BY dc.created_at DESC, dc.chunk_index ASC
                LIMIT ? OFFSET ?
                """,
                tuple([*params, limit, offset]),
            ).fetchall()
        items = []
        for row in rows:
            payload = dict(row)
            payload["file_name"] = row["file_name"]
            items.append(payload)
        return {
            "items": items,
            "total": int(total_row["total"]),
            "offset": offset,
            "limit": limit,
        }

    def start_reindex(self, kb_id: str) -> dict:
        task = self.task_service.create("reindex", kb_id, status="running", progress=0.0)
        return task.model_dump()

    def reindex(self, kb_id: str, task_id: str) -> dict:
        try:
            with get_connection() as conn:
                kb = conn.execute(
                    "SELECT * FROM knowledge_bases WHERE id = ?",
                    (kb_id,),
                ).fetchone()
                if kb is None:
                    raise ValueError(f"Knowledge base {kb_id} not found")
                documents = conn.execute(
                    "SELECT * FROM documents WHERE kb_id = ? ORDER BY created_at ASC",
                    (kb_id,),
                ).fetchall()
                conn.execute(
                    "UPDATE knowledge_bases SET status = 'reindexing', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (kb_id,),
                )

            if not documents:
                with get_connection() as conn:
                    conn.execute(
                        "DELETE FROM document_chunks WHERE kb_id = ?",
                        (kb_id,),
                    )
                    conn.execute(
                        """
                        UPDATE knowledge_bases
                        SET status = 'ready', file_count = 0, chunk_count = 0, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (kb_id,),
                    )
                task = self.task_service.update(task_id, status="done", progress=1.0)
                return {"task": task.model_dump(), "stats": self.get_stats(kb_id)}

            total_docs = len(documents)
            self.task_service.update(task_id, status="running", progress=0.1)

            for index, document in enumerate(documents, start=1):
                storage_path = Path(document["storage_path"])
                if storage_path.exists():
                    content = storage_path.read_bytes()
                    extracted_text, ocr_status = self.parser_service.extract_text(
                        document["file_name"],
                        content,
                        enable_ocr=True,
                        file_path=storage_path,
                    )
                else:
                    extracted_text = (
                        f"File content for {document['file_name']} is no longer present "
                        f"at {document['storage_path']}."
                    )
                    ocr_status = "missing"

                chunks = build_structured_chunks(extracted_text)
                if not chunks:
                    chunks = build_structured_chunks(
                        f"No structured text extracted from {document['file_name']}."
                    )

                with get_connection() as conn:
                    conn.execute(
                        "DELETE FROM document_chunks WHERE document_id = ?",
                        (document["id"],),
                    )
                    for chunk_index, chunk in enumerate(chunks):
                        conn.execute(
                            """
                            INSERT INTO document_chunks (
                                id, document_id, kb_id, chunk_index, content,
                                content_hash, page_no, sheet_name, slide_no, heading_path,
                                token_count, vector_ref
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                new_id("chunk"),
                                document["id"],
                                kb_id,
                                chunk_index,
                                chunk.content,
                                sha256_text(chunk.content),
                                chunk.page_no,
                                chunk.sheet_name,
                                chunk.slide_no,
                                chunk.heading_path,
                                len(chunk.content.split()),
                                f"local-vector://{document['id']}/{chunk_index}",
                            ),
                        )
                    conn.execute(
                        """
                        UPDATE documents
                        SET parse_status = 'done',
                            ocr_status = ?,
                            index_status = 'done',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (ocr_status, document["id"]),
                    )
                    conn.execute(
                        """
                        UPDATE knowledge_bases
                        SET file_count = (SELECT COUNT(*) FROM documents WHERE kb_id = ?),
                            chunk_count = (SELECT COUNT(*) FROM document_chunks WHERE kb_id = ?),
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (kb_id, kb_id, kb_id),
                    )

                progress = min(0.95, 0.1 + (0.85 * index / total_docs))
                self.task_service.update(task_id, status="running", progress=progress)

            with get_connection() as conn:
                conn.execute(
                    "UPDATE knowledge_bases SET status = 'ready', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (kb_id,),
                )
            task = self.task_service.update(task_id, status="done", progress=1.0)
            stats = self.get_stats(kb_id)
            self.log_operation(
                "knowledge_base",
                "reindex",
                kb_id,
                "success",
                {"task_id": task_id, **stats},
            )
            return {"task": task.model_dump(), "stats": stats}
        except Exception as exc:
            with get_connection() as conn:
                conn.execute(
                    "UPDATE knowledge_bases SET status = 'error', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (kb_id,),
                )
            self.task_service.update(
                task_id,
                status="failed",
                progress=1.0,
                error_code="reindex_failed",
                error_message=str(exc),
            )
            raise
