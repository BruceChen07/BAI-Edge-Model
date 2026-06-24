from __future__ import annotations

import base64
from pathlib import Path

from fastapi import UploadFile

from app.core.config import config
from app.core.database import get_connection
from app.core.logging import get_logger
from app.core.request_context import get_trace_id
from app.schemas.chat import ChatAttachmentDTO
from app.services.base import BaseService, ensure_parent, sha256_bytes
from app.services.parser_service import ParserService
from app.services.upload_policy import (
    is_image_upload,
    normalize_upload_extension,
    validate_file_upload_policy,
)
from app.utils.ids import new_id


class ChatAttachmentService(BaseService):
    def __init__(self) -> None:
        self.logger = get_logger("app.chat_attachment")
        self.parser_service = ParserService()

    async def upload(self, session_id: str, file: UploadFile, enable_ocr: bool = True) -> ChatAttachmentDTO:
        content = await file.read()
        validate_file_upload_policy(
            file.filename, file.content_type, len(content))
        with get_connection() as conn:
            session = conn.execute(
                "SELECT id FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if session is None:
                raise ValueError(f"Session {session_id} not found")

            attachment_id = new_id("att")
            extension = normalize_upload_extension(file.filename)
            target_dir = config.storage_root / "chat_attachments" / session_id
            target_path = target_dir / f"{attachment_id}{extension}"
            ensure_parent(target_path)
            target_path.write_bytes(content)

            extracted_text, ocr_status = self.parser_service.extract_text(
                file.filename or attachment_id,
                content,
                enable_ocr=enable_ocr,
                file_path=target_path,
            )
            conn.execute(
                """
                INSERT INTO chat_attachments (
                    id, session_id, message_id, file_name, file_ext, mime_type,
                    file_size, attachment_type, storage_path, sha256,
                    extracted_text, ocr_status, status
                )
                VALUES (?, ?, '', ?, ?, ?, ?, ?, ?, ?, ?, ?, 'uploaded')
                """,
                (
                    attachment_id,
                    session_id,
                    file.filename or attachment_id,
                    extension,
                    file.content_type or "application/octet-stream",
                    len(content),
                    "image" if is_image_upload(file.filename) else "document",
                    str(target_path),
                    sha256_bytes(content),
                    extracted_text,
                    ocr_status,
                ),
            )
            row = conn.execute(
                "SELECT * FROM chat_attachments WHERE id = ?",
                (attachment_id,),
            ).fetchone()
        self.log_operation(
            "chat_attachment",
            "upload",
            attachment_id,
            "success",
            {"session_id": session_id, "file_name": file.filename,
                "trace_id": get_trace_id()},
        )
        return self._row_to_dto(dict(row))

    def delete(self, attachment_id: str) -> dict:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM chat_attachments WHERE id = ?",
                (attachment_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Attachment not found: {attachment_id}")
            payload = dict(row)
            conn.execute(
                "DELETE FROM chat_attachments WHERE id = ?",
                (attachment_id,),
            )
        storage_path = Path(payload["storage_path"])
        if storage_path.exists():
            storage_path.unlink()
        self.log_operation(
            "chat_attachment",
            "delete",
            attachment_id,
            "success",
            {"session_id": payload["session_id"],
                "file_name": payload["file_name"]},
        )
        return {"deleted": True, "attachment_id": attachment_id}

    def get(self, attachment_id: str) -> ChatAttachmentDTO:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM chat_attachments WHERE id = ?",
                (attachment_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"Attachment not found: {attachment_id}")
        return self._row_to_dto(dict(row))

    def list_for_message_ids(self, message_ids: list[str]) -> dict[str, list[ChatAttachmentDTO]]:
        if not message_ids:
            return {}
        placeholders = ",".join("?" for _ in message_ids)
        with get_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM chat_attachments
                WHERE message_id IN ({placeholders})
                ORDER BY created_at ASC
                """,
                tuple(message_ids),
            ).fetchall()
        grouped: dict[str, list[ChatAttachmentDTO]] = {}
        for row in rows:
            dto = self._row_to_dto(dict(row))
            grouped.setdefault(dto.message_id or "", []).append(dto)
        return grouped

    def get_linkable_attachments(self, session_id: str, attachment_ids: list[str]) -> list[dict]:
        if not attachment_ids:
            return []
        placeholders = ",".join("?" for _ in attachment_ids)
        with get_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM chat_attachments
                WHERE session_id = ?
                  AND id IN ({placeholders})
                ORDER BY created_at ASC
                """,
                (session_id, *attachment_ids),
            ).fetchall()
        return [dict(row) for row in rows]

    def bind_attachments_to_message(
        self,
        session_id: str,
        attachment_ids: list[str],
        message_id: str,
    ) -> None:
        rows = self.get_linkable_attachments(session_id, attachment_ids)
        if not rows:
            return
        with get_connection() as conn:
            for row in rows:
                conn.execute(
                    """
                    UPDATE chat_attachments
                    SET message_id = ?, status = 'linked', updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (message_id, row["id"]),
                )

    def build_prompt_payload(self, session_id: str, attachment_ids: list[str]) -> tuple[str, list[str], list[ChatAttachmentDTO]]:
        rows = self.get_linkable_attachments(session_id, attachment_ids)
        if not rows:
            return "", [], []
        text_blocks: list[str] = []
        image_payloads: list[str] = []
        attachments = [self._row_to_dto(row) for row in rows]
        for row in rows:
            preview_text = self._normalize_preview_text(
                str(row.get("extracted_text") or ""))
            if preview_text:
                text_blocks.append(
                    f"Attachment: {row['file_name']}\nExtracted Content:\n{preview_text}"
                )
            else:
                text_blocks.append(
                    f"Attachment: {row['file_name']}\nExtracted Content:\nNo text extracted."
                )
            if row.get("attachment_type") == "image":
                storage_path = Path(str(row["storage_path"]))
                if storage_path.exists():
                    image_payloads.append(base64.b64encode(
                        storage_path.read_bytes()).decode("utf-8"))
        return "\n\n".join(text_blocks), image_payloads, attachments

    def _normalize_preview_text(self, text: str, limit: int = 4000) -> str:
        normalized = " ".join(text.split())
        if len(normalized) <= limit:
            return normalized
        return f"{normalized[:limit]}..."

    def _row_to_dto(self, row: dict) -> ChatAttachmentDTO:
        return ChatAttachmentDTO(
            id=row["id"],
            session_id=row["session_id"],
            message_id=row.get("message_id") or None,
            file_name=row["file_name"],
            file_ext=row.get("file_ext", ""),
            mime_type=row.get("mime_type", "application/octet-stream"),
            file_size=int(row.get("file_size", 0) or 0),
            attachment_type=row.get("attachment_type", "document"),
            storage_path=row.get("storage_path", ""),
            extracted_text_preview=self._normalize_preview_text(
                str(row.get("extracted_text") or ""),
                limit=240,
            ),
            ocr_status=row.get("ocr_status", "skipped"),
            status=row.get("status", "uploaded"),
            created_at=row.get("created_at"),
        )
