"""
Memory Orchestrator — ties together short-term cache, long-term retrieval,
and context injection for chat/agent flows.
"""
from __future__ import annotations

import time
from typing import Any

from app.core.config import (
    COMPRESS_DEDUP_THRESHOLD,
    COMPRESS_IMPORTANCE_MIN,
    EXTRACT_MIN_CONFIDENCE,
    EXTRACT_TRIGGER_TURN_COUNT,
)
from app.core.database import get_connection
from app.core.logging import get_logger
from app.schemas.memory import MemoryCreateDTO, MemoryDTO, MemoryStatsDTO
from app.services.memory_retriever import MemoryRetriever, RetrievalHit
from app.services.short_term_cache import ShortTermMemoryCache, get_cache
from app.utils.ids import new_id

# Lazy import to avoid circular dependency
try:
    from app.services.compression_engine import CompressionEngine as _CompressionEngine
    from app.services.ollama_service import OllamaService as _OllamaService
    from app.services.semantic_extractor import SemanticExtractor as _SemanticExtractor
    _LLM_AVAILABLE = True
except ImportError:
    _LLM_AVAILABLE = False

logger = get_logger("app.memory.orchestrator")


class MemoryOrchestrator:
    """
    Central coordinator for the memory system.

    Responsibilities:
      - Build augmented chat context from short-term cache + retrieved long-term memories
      - Track turn counts and trigger memory extraction
      - Deduplicate and compress extracted memories (Phase 2 full impl later)
      - Provide stats and configuration
    """

    def __init__(
        self,
        cache: ShortTermMemoryCache | None = None,
        retriever: MemoryRetriever | None = None,
    ) -> None:
        self.cache = cache or get_cache()
        self.retriever = retriever or MemoryRetriever()

    # ------------------------------------------------------------------
    # Context Building (injected into chat prompt)
    # ------------------------------------------------------------------
    def build_memory_context(
        self,
        session_id: str,
        user_query: str,
        max_recall: int = 3,
        max_total_chars: int = 600,
    ) -> str:
        """
        Build a memory-augmented context string for injection into the system prompt.
        Combines:
          1. Short-term: recent conversation turns from cache
          2. Long-term: FTS5 + Jaccard retrieved memories
        """
        parts: list[str] = []

        # Short-term: last N user-assistant pairs
        recent = self.cache.get(f"session:{session_id}:recent")
        if recent and isinstance(recent, list):
            snippet = recent[-6:]  # last 3 pairs
            st_text = "\n".join(
                f"[Recent] {m['role']}: {m['content'][:200]}"
                for m in snippet
                if isinstance(m, dict)
            )
            if st_text:
                parts.append(f"Recent conversation:\n{st_text}")

        # Long-term: retrieved memories
        hits = self.retriever.search(user_query, session_id=None)
        if hits:
            lt_lines: list[str] = []
            for h in hits[:max_recall]:
                lt_lines.append(f"- [{h.memory_type}] {h.title}: {h.content}")
            lt_text = "\n".join(lt_lines)
            if len(lt_text) > max_total_chars:
                lt_text = lt_text[:max_total_chars] + "..."
            parts.append(f"Relevant memories:\n{lt_text}")

        return "\n\n".join(parts) if parts else ""

    # ------------------------------------------------------------------
    # Short-term cache helpers
    # ------------------------------------------------------------------
    def update_session_cache(
        self, session_id: str, messages: list[dict[str, str]],
    ) -> None:
        """Store recent conversation turns in short-term cache."""
        if messages:
            self.cache.set(f"session:{session_id}:recent", messages)

    def clear_session_cache(self, session_id: str) -> int:
        """Remove all cached entries for a session."""
        return self.cache.clear_session(session_id)

    # ------------------------------------------------------------------
    # Long-term memory CRUD (delegates to SQLite)
    # ------------------------------------------------------------------
    def list_memories(self) -> list[dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM memories WHERE status = 'active' ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def create_memory(self, payload: MemoryCreateDTO) -> MemoryDTO:
        import hashlib
        memory_id = new_id("mem")
        content_hash = hashlib.sha256(payload.content.encode()).hexdigest()
        tags_json = _serialize_tags(getattr(payload, "tags", []))

        with get_connection() as conn:
            conn.execute(
                """INSERT INTO memories
                   (id, memory_type, title, content, content_hash, importance,
                    confidence, write_mode, status, source_session_id, tags)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    memory_id, payload.memory_type, payload.title, payload.content,
                    content_hash, payload.importance, payload.confidence,
                    payload.write_mode, payload.status,
                    getattr(payload, "source_session_id", None) or "",
                    tags_json,
                ),
            )
            # Sync to FTS5 index
            conn.execute(
                "INSERT INTO memories_fts(rowid, title, content, tags) VALUES (?, ?, ?, ?)",
                (conn.execute("SELECT rowid FROM memories WHERE id = ?", (memory_id,)).fetchone()["rowid"],
                 payload.title, payload.content, tags_json),
            )
            row = conn.execute(
                "SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        return MemoryDTO(**dict(row))

    def update_memory(self, memory_id: str, payload: MemoryCreateDTO) -> MemoryDTO:
        import hashlib
        content_hash = hashlib.sha256(payload.content.encode()).hexdigest()
        tags_json = _serialize_tags(getattr(payload, "tags", []))

        with get_connection() as conn:
            conn.execute(
                """UPDATE memories SET memory_type = ?, title = ?, content = ?,
                   content_hash = ?, importance = ?, confidence = ?,
                   write_mode = ?, status = ?, source_session_id = ?,
                   tags = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                (
                    payload.memory_type, payload.title, payload.content,
                    content_hash, payload.importance, payload.confidence,
                    payload.write_mode, payload.status,
                    getattr(payload, "source_session_id", None) or "",
                    tags_json, memory_id,
                ),
            )
            # Re-sync FTS5
            conn.execute(
                "DELETE FROM memories_fts WHERE rowid = (SELECT rowid FROM memories WHERE id = ?)", (memory_id,))
            conn.execute(
                "INSERT INTO memories_fts(rowid, title, content, tags) VALUES (?, ?, ?, ?)",
                (conn.execute("SELECT rowid FROM memories WHERE id = ?", (memory_id,)).fetchone()["rowid"],
                 payload.title, payload.content, tags_json),
            )
            row = conn.execute(
                "SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        return MemoryDTO(**dict(row))

    def delete_memory(self, memory_id: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "DELETE FROM memories_fts WHERE rowid = (SELECT rowid FROM memories WHERE id = ?)", (memory_id,))
            conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))

    def search_memories(self, query: str, top_k: int = 5, min_similarity: float = 0.4) -> list[dict[str, Any]]:
        self.retriever.top_k = top_k
        self.retriever.min_similarity = min_similarity
        hits = self.retriever.search(query)
        return [
            {
                "id": h.id, "title": h.title, "content": h.content,
                "memory_type": h.memory_type, "importance": h.importance, "score": h.score,
            }
            for h in hits
        ]

    # ------------------------------------------------------------------
    # Lightweight extraction scheduler (Phase 1: rule-based placeholder)
    # ------------------------------------------------------------------
    def maybe_trigger_extraction(
        self, session_id: str, turn_count: int,
    ) -> bool:
        """Check if memory extraction should be triggered for this session."""
        should_extract = (
            turn_count >= EXTRACT_TRIGGER_TURN_COUNT
            and turn_count % EXTRACT_TRIGGER_TURN_COUNT == 1
        )
        if should_extract:
            logger.info(
                "Memory extraction triggered session=%s turn_count=%d",
                session_id, turn_count,
            )
        return should_extract

    def auto_extract_from_messages(
        self, session_id: str, messages: list[dict[str, str]],
    ) -> list[MemoryDTO]:
        """
        Extract memories from conversation.
        Phase 2: uses local LLM (qwen3:0.6b) when available, falls back to rules.
        """
        if _LLM_AVAILABLE:
            llm_result = self._extract_with_llm(session_id, messages)
            if llm_result:
                return llm_result
            # LLM extraction failed/empty, fall back to rules
        return self._extract_with_rules(session_id, messages)

    def _extract_with_llm(
        self, session_id: str, messages: list[dict[str, str]],
    ) -> list[MemoryDTO]:
        """LLM-powered semantic extraction (Phase 2)."""
        ollama = _OllamaService()
        extractor = _SemanticExtractor(
            ollama_service=ollama, model_name="qwen3:0.6b")
        items = extractor.extract(messages, language="zh")
        if not items:
            return []

        created: list[MemoryDTO] = []
        for item in items:
            if item["confidence"] < EXTRACT_MIN_CONFIDENCE:
                continue
            try:
                dto = MemoryCreateDTO(
                    memory_type=item["memory_type"],
                    title=item["title"],
                    content=item["content"],
                    importance=item["importance"],
                    confidence=item["confidence"],
                    write_mode="auto",
                    status="active",
                    source_session_id=session_id,
                )
                mem = self.create_memory(dto)
                created.append(mem)
            except Exception:
                logger.warning("LLM extract save failed", exc_info=True)
        return created

    def _extract_with_rules(
        self, session_id: str, messages: list[dict[str, str]],
    ) -> list[MemoryDTO]:
        """
        Rule-based extraction fallback.
        Creates memories for explicit user statements > 40 chars.
        """
        created: list[MemoryDTO] = []
        for msg in messages:
            if msg.get("role") != "user":
                continue
            content = msg.get("content", "").strip()
            if len(content) < 40:
                continue
            if any(marker in content for marker in ["我是", "我喜欢", "我需要", "我知道", "我住", "我叫"]):
                try:
                    dto = MemoryCreateDTO(
                        memory_type="fact",
                        title=f"User statement ({content[:30]}...)",
                        content=content,
                        importance=0.5,
                        confidence=0.6,
                        write_mode="auto",
                        status="active",
                        source_session_id=session_id,
                    )
                    mem = self.create_memory(dto)
                    created.append(mem)
                except Exception:
                    logger.warning(
                        "Auto-extract failed for session=%s", session_id, exc_info=True)
        return created

    # ------------------------------------------------------------------
    # Compression & Deduplication
    # ------------------------------------------------------------------
    def compact(self) -> dict[str, int]:
        """Run full memory compaction via CompressionEngine."""
        engine = _CompressionEngine() if _LLM_AVAILABLE else None
        if engine:
            return engine.compact()
        # Fallback: just hash dedup
        return {"hash_duplicates_removed": self.deduplicate_by_hash()}

    def deduplicate_by_hash(self) -> int:
        """Remove exact duplicate memories (same content_hash). Returns count removed."""
        with get_connection() as conn:
            conn.execute("""
                DELETE FROM memories WHERE rowid NOT IN (
                    SELECT MIN(rowid) FROM memories WHERE status = 'active' GROUP BY content_hash
                ) AND status = 'active'
            """)
            conn.execute(
                "DELETE FROM memories_fts WHERE rowid NOT IN (SELECT rowid FROM memories)")
            return conn.total_changes

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------
    def get_stats(self) -> MemoryStatsDTO:
        with get_connection() as conn:
            total = conn.execute(
                "SELECT COUNT(*) as c FROM memories").fetchone()["c"]
            active = conn.execute(
                "SELECT COUNT(*) as c FROM memories WHERE status = 'active'").fetchone()["c"]
            archived = conn.execute(
                "SELECT COUNT(*) as c FROM memories WHERE status = 'archived'"
            ).fetchone()["c"]
            dist = conn.execute(
                "SELECT memory_type, COUNT(*) as c FROM memories GROUP BY memory_type"
            ).fetchall()
            size_row = conn.execute(
                "SELECT SUM(LENGTH(content) + LENGTH(title)) as s FROM memories"
            ).fetchone()

        type_dist: dict[str, int] = {}
        for row in dist:
            type_dist[row["memory_type"]] = row["c"]

        return MemoryStatsDTO(
            total_count=total or 0,
            type_distribution=type_dist,
            total_size_bytes=size_row["s"] or 0,
            active_count=active or 0,
            archived_count=archived or 0,
        )

    def get_config(self) -> dict[str, Any]:
        return {
            "short_term_ttl_seconds": self.cache.ttl_seconds,
            "short_term_max_entries": self.cache.max_entries,
            "trigger_turn_count": EXTRACT_TRIGGER_TURN_COUNT,
            "extract_min_confidence": EXTRACT_MIN_CONFIDENCE,
            "dedup_threshold": COMPRESS_DEDUP_THRESHOLD,
            "top_k": self.retriever.top_k,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _serialize_tags(tags: list[str] | str) -> str:
    import json
    if isinstance(tags, list):
        return json.dumps(tags, ensure_ascii=False)
    if isinstance(tags, str):
        return tags
    return "[]"
