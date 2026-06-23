from __future__ import annotations

import json
import logging
import time
from typing import Iterator

from app.core.database import get_connection
from app.core.logging import get_logger, log_event
from app.core.request_context import get_trace_id
from app.schemas.chat import ChatRequestDTO, ChatResponseDTO, MessageDTO, SessionCreateDTO, SessionDTO
from app.services.ollama_service import OllamaService
from app.services.resource_monitor import (
    check_model_feasibility,
    get_full_resource_snapshot,
    list_recommended_models,
)
from app.services.settings_service import SettingsService
from app.utils.ids import new_id


class ChatService:
    def __init__(self) -> None:
        self.ollama_service = OllamaService()
        self.settings_service = SettingsService()
        self.logger = get_logger("app.chat")

    def create_session(self, payload: SessionCreateDTO) -> SessionDTO:
        session_id = new_id("sess")
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO sessions (id, title, mode, language, rag_enabled, agent_enabled) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, payload.title, payload.mode, payload.language,
                 int(payload.rag_enabled), int(payload.agent_enabled)),
            )
            row = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return SessionDTO(
            id=row["id"], title=row["title"], mode=row["mode"], language=row["language"],
            rag_enabled=bool(row["rag_enabled"]), agent_enabled=bool(row["agent_enabled"]), last_message_at=row["last_message_at"],
        )

    def list_sessions(self) -> list[SessionDTO]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY last_message_at DESC").fetchall()
        return [SessionDTO(id=row["id"], title=row["title"], mode=row["mode"], language=row["language"], rag_enabled=bool(row["rag_enabled"]), agent_enabled=bool(row["agent_enabled"]), last_message_at=row["last_message_at"]) for row in rows]

    def get_session(self, session_id: str) -> dict:
        with get_connection() as conn:
            session = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            messages = conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC", (session_id,)).fetchall()
        return {
            "session": SessionDTO(id=session["id"], title=session["title"], mode=session["mode"], language=session["language"], rag_enabled=bool(session["rag_enabled"]), agent_enabled=bool(session["agent_enabled"]), last_message_at=session["last_message_at"]),
            "messages": [MessageDTO(**dict(row)) for row in messages],
        }

    def update_session_title(self, session_id: str, title: str) -> SessionDTO:
        with get_connection() as conn:
            conn.execute(
                "UPDATE sessions SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (title, session_id))
            row = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return SessionDTO(id=row["id"], title=row["title"], mode=row["mode"], language=row["language"], rag_enabled=bool(row["rag_enabled"]), agent_enabled=bool(row["agent_enabled"]), last_message_at=row["last_message_at"])

    def delete_session(self, session_id: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    def answer(self, payload: ChatRequestDTO) -> ChatResponseDTO:
        started_at = time.time()
        trace_id = get_trace_id()
        if trace_id == "-" and payload.session_id:
            trace_id = payload.session_id
        log_event(
            self.logger,
            logging.INFO,
            "chat.answer.started",
            "Chat answer flow started",
            module_name="chat",
            trace_id=trace_id,
            session_id=payload.session_id,
            requested_model=payload.model_name,
            rag_enabled=payload.rag_enabled,
            knowledge_base_ids=payload.knowledge_base_ids,
        )
        citations = self._search(
            payload.knowledge_base_ids, payload.query, payload.top_k)
        model_name = self._resolve_model_name(payload.model_name)
        answer = self._compose_answer(
            payload.query, citations, model_name, payload.session_id)
        self._save_message(payload.session_id, "user",
                           payload.query, model_name)
        message_id = self._save_message(
            payload.session_id, "assistant", answer, model_name)
        self._save_citations(message_id, citations)
        log_event(
            self.logger,
            logging.INFO,
            "chat.answer.completed",
            "Chat answer flow completed",
            module_name="chat",
            trace_id=trace_id,
            session_id=payload.session_id,
            model_used=model_name,
            citation_count=len(citations),
            elapsed_ms=round((time.time() - started_at) * 1000, 2),
        )
        return ChatResponseDTO(answer=answer, citations=citations, model_used=model_name)

    def stream_answer(self, payload: ChatRequestDTO) -> Iterator[str]:
        response = self.answer(payload)
        yield self._sse("message_start", {"session_id": payload.session_id})
        yield self._sse("retrieval_result", {"citations": response.citations})
        for token in response.answer.split():
            yield self._sse("token", {"text": token + " "})
        yield self._sse("message_end", response.model_dump())

    def _search(self, kb_ids: list[str], query: str, top_k: int) -> list[dict]:
        if not kb_ids:
            return []
        query_terms = [term.lower() for term in query.split() if term.strip()]
        with get_connection() as conn:
            placeholders = ",".join(["?"] * len(kb_ids))
            rows = conn.execute(
                f"""
                SELECT dc.*, d.file_name
                FROM document_chunks dc
                JOIN documents d ON d.id = dc.document_id
                WHERE dc.kb_id IN ({placeholders})
                ORDER BY dc.created_at DESC
                """,
                tuple(kb_ids),
            ).fetchall()
        scored: list[tuple[int, dict]] = []
        for row in rows:
            content = row["content"].lower()
            file_name = str(row["file_name"]).lower()
            score = sum(content.count(term) for term in query_terms)
            score += sum(file_name.count(term) * 2 for term in query_terms)
            if score > 0 or not query_terms:
                scored.append((score, dict(row)))
        scored.sort(key=lambda item: item[0], reverse=True)
        citations: list[dict] = []
        for score, row in scored[:top_k]:
            citations.append({
                "document_id": row["document_id"],
                "chunk_id": row["id"],
                "quote_text": row["content"],
                "score": score,
                "page_no": row["page_no"],
                "file_name": row["file_name"],
            })
        return citations

    def _compose_answer(self, query: str, citations: list[dict], model_name: str, session_id: str) -> str:
        history = self._load_history(session_id)
        context = self._build_context(citations)
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "You are a local-first assistant. "
                    "Answer in the user's language. "
                    "If retrieval context is provided, use it as supporting knowledge. "
                    "Do not fabricate citations."
                ),
            }
        ]
        messages.extend(history)
        messages.append(
            {
                "role": "user",
                "content": f"Question:\n{query}\n\nKnowledge Context:\n{context}",
            }
        )
        return self.ollama_service.chat(model_name=model_name, messages=messages)

    def _save_message(self, session_id: str, role: str, content: str, model_name: str) -> str:
        message_id = new_id("msg")
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO messages (id, session_id, role, content, content_type, model_name, prompt_tokens, completion_tokens, status) VALUES (?, ?, ?, ?, 'text', ?, ?, ?, 'done')",
                (
                    message_id,
                    session_id,
                    role,
                    content,
                    model_name,
                    len(content.split()),
                    len(content.split()),
                ),
            )
            conn.execute(
                "UPDATE sessions SET last_message_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (session_id,))
        return message_id

    def list_models(self) -> list[dict]:
        return self.ollama_service.list_models()

    def _resolve_model_name(self, requested_model: str | None) -> str:
        available_models = self.ollama_service.list_models()
        available_names = [item["name"] for item in available_models]
        if requested_model:
            return requested_model
        settings = self.settings_service.get()
        if settings.default_model in available_names:
            return settings.default_model
        if available_names:
            return available_names[0]
        raise RuntimeError("No local Ollama models are available.")

    def _load_history(self, session_id: str) -> list[dict[str, str]]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT role, content
                FROM messages
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT 6
                """,
                (session_id,),
            ).fetchall()
        ordered = list(reversed(rows))
        return [{"role": row["role"], "content": row["content"]} for row in ordered]

    def _build_context(self, citations: list[dict]) -> str:
        if not citations:
            return "No local retrieval context."
        blocks = []
        for citation in citations[:4]:
            blocks.append(
                f"Source: {citation.get('file_name', 'unknown')}\n"
                f"Score: {citation.get('score', 0)}\n"
                f"Content:\n{citation.get('quote_text', '')}"
            )
        return "\n\n".join(blocks)

    def _save_citations(self, message_id: str, citations: list[dict]) -> None:
        with get_connection() as conn:
            for citation in citations:
                conn.execute(
                    "INSERT INTO message_citations (id, message_id, document_id, chunk_id, page_no, quote_text) VALUES (?, ?, ?, ?, ?, ?)",
                    (new_id("cite"), message_id, citation["document_id"],
                     citation["chunk_id"], citation["page_no"], citation["quote_text"]),
                )

    def _sse(self, event: str, payload: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def check_resources(self, model_name: str | None = None) -> dict:
        """Check hardware resources and model feasibility."""
        snapshot = get_full_resource_snapshot()
        result: dict = {"snapshot": snapshot}
        if model_name:
            result["feasibility"] = check_model_feasibility(model_name)
        result["recommendations"] = list_recommended_models()
        return result

    def get_timeout_info(self, model_name: str) -> dict:
        """Return the resolved timeout tier for a given model."""
        return self.ollama_service.get_timeout_info(model_name)
