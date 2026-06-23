from __future__ import annotations

import logging
import mimetypes
import time
from pathlib import Path

from fastapi import UploadFile

from app.core.database import get_connection
from app.core.logging import get_logger, log_event
from app.core.request_context import get_trace_id
from app.schemas.knowledge_base import DocumentDTO
from app.services.base import BaseService, ensure_parent, sha256_bytes, sha256_text
from app.services.document_chunking import build_structured_chunks
from app.services.parser_service import ParserService
from app.services.task_service import TaskService
from app.utils.ids import new_id


class IngestService(BaseService):
    def __init__(self) -> None:
        self.task_service = TaskService()
        self.parser_service = ParserService()
        self.logger = get_logger("app.ingest")

    async def upload(self, kb_id: str, file: UploadFile, enable_ocr: bool = True) -> dict:
        started_at = time.time()
        trace_id = get_trace_id()
        content = await file.read()
        file_sha256 = sha256_bytes(content)
        file_id = new_id("doc")
        log_event(
            self.logger,
            logging.INFO,
            "ingest.upload.started",
            "Knowledge base file upload started",
            module_name="ingest",
            trace_id=trace_id,
            kb_id=kb_id,
            file_name=file.filename,
            file_size=len(content),
            enable_ocr=enable_ocr,
        )
        task = self.task_service.create(
            "ingest", file_id, status="running", progress=0.1)

        with get_connection() as conn:
            kb = conn.execute(
                "SELECT * FROM knowledge_bases WHERE id = ?", (kb_id,)).fetchone()
            if kb is None:
                raise ValueError(f"Knowledge base {kb_id} not found")
            existing = conn.execute(
                "SELECT * FROM documents WHERE kb_id = ? AND sha256 = ?",
                (kb_id, file_sha256),
            ).fetchone()
            if existing is not None:
                self.task_service.update(task.id, status="done", progress=1.0)
                log_event(
                    self.logger,
                    logging.INFO,
                    "ingest.upload.deduplicated",
                    "Knowledge base file upload was deduplicated",
                    module_name="ingest",
                    trace_id=trace_id,
                    kb_id=kb_id,
                    file_name=file.filename,
                    existing_document_id=existing["id"],
                )
                return {
                    "upload_id": existing["id"],
                    "task_ids": [task.id],
                    "document": DocumentDTO(**dict(existing)),
                    "deduplicated": True,
                }
            target_dir = Path(kb["path"]) / "uploads"
            target_path = target_dir / (file.filename or file_id)
            ensure_parent(target_path)
            target_path.write_bytes(content)

            mime_type, _ = mimetypes.guess_type(file.filename or "")
            extracted_text, ocr_status = self.parser_service.extract_text(
                file.filename or "",
                content,
                enable_ocr=enable_ocr,
                file_path=target_path,
            )
            conn.execute(
                """
                INSERT INTO documents (id, kb_id, file_name, file_ext, mime_type, file_size, storage_path, sha256, parse_status, ocr_status, index_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'done', ?, 'done')
                """,
                (
                    file_id,
                    kb_id,
                    file.filename or file_id,
                    Path(file.filename or '').suffix.lower(),
                    mime_type or 'application/octet-stream',
                    len(content),
                    str(target_path),
                    file_sha256,
                    ocr_status,
                ),
            )

            chunks = build_structured_chunks(extracted_text)
            if not chunks:
                chunks = [
                    build_structured_chunks(
                        f"No structured text extracted from {file.filename}."
                    )[0]
                ]
            for index, chunk in enumerate(chunks):
                conn.execute(
                    """
                    INSERT INTO document_chunks (
                        id, document_id, kb_id, chunk_index, content, content_hash,
                        page_no, sheet_name, slide_no, heading_path, token_count, vector_ref
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_id("chunk"),
                        file_id,
                        kb_id,
                        index,
                        chunk.content,
                        sha256_text(chunk.content),
                        chunk.page_no,
                        chunk.sheet_name,
                        chunk.slide_no,
                        chunk.heading_path,
                        len(chunk.content.split()),
                        f"local-vector://{file_id}/{index}",
                    ),
                )

            conn.execute(
                "UPDATE knowledge_bases SET file_count = (SELECT COUNT(*) FROM documents WHERE kb_id = ?), chunk_count = (SELECT COUNT(*) FROM document_chunks WHERE kb_id = ?), updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (kb_id, kb_id, kb_id),
            )

            row = conn.execute(
                "SELECT * FROM documents WHERE id = ?", (file_id,)).fetchone()
        self.task_service.update(task.id, status="done", progress=1.0)
        self.log_operation("ingest", "upload", file_id, "success", {
                           "file_name": file.filename, "kb_id": kb_id})
        log_event(
            self.logger,
            logging.INFO,
            "ingest.upload.completed",
            "Knowledge base file upload completed",
            module_name="ingest",
            trace_id=trace_id,
            kb_id=kb_id,
            document_id=file_id,
            chunk_count=len(chunks),
            ocr_status=ocr_status,
            elapsed_ms=round((time.time() - started_at) * 1000, 2),
        )
        return {"upload_id": file_id, "task_ids": [task.id], "document": DocumentDTO(**dict(row))}
