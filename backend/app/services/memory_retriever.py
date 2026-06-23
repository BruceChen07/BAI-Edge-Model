"""
Memory retrieval layer using FTS5 full-text search + Jaccard relevance ranking.
Zero external dependencies — works offline on edge devices.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from app.core.config import RETRIEVER_DEFAULT_TOP_K, RETRIEVER_SIMILARITY_THRESHOLD
from app.core.database import get_connection
from app.core.logging import get_logger

logger = get_logger("app.memory.retriever")


@dataclass
class RetrievalHit:
    id: str
    title: str
    content: str
    memory_type: str
    importance: float
    score: float          # 0.0 – 1.0 relevance


class MemoryRetriever:
    """
    Two-stage retrieval:
      1. FTS5 keyword match (fast, indexed)
      2. Jaccard similarity scoring on candidates (lightweight, no GPU)

    Complexity per query: O(FTS5_matches + candidates * avg_tokens)
    Target latency: < 5ms for 10,000 memories on consumer CPU.
    """

    def __init__(
        self,
        top_k: int = RETRIEVER_DEFAULT_TOP_K,
        min_similarity: float = RETRIEVER_SIMILARITY_THRESHOLD,
    ) -> None:
        self.top_k = top_k
        self.min_similarity = min_similarity

    def search(self, query: str, session_id: str | None = None) -> list[RetrievalHit]:
        """
        Search memories matching the query.
        Optionally scoped to a source_session_id.
        """
        started = time.perf_counter()
        with get_connection() as conn:
            candidates = self._fts5_search(conn, query, session_id)
            ranked = self._jaccard_rank(query, candidates)
            ranked.sort(key=lambda h: (-h.score, -h.importance))
            results = ranked[:self.top_k]

        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        logger.debug(
            "MemoryRetriever.search query_len=%d candidates=%d results=%d elapsed_ms=%s",
            len(query), len(candidates), len(results), elapsed_ms,
        )
        self._record_access(results)
        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _fts5_search(
        self, conn: Any, query: str, session_id: str | None,
    ) -> list[dict[str, Any]]:
        """FTS5 keyword match. Returns DB rows for active memories."""
        # Build a safe FTS5 query: OR-together the query terms
        terms = [t.strip() for t in query.split() if t.strip() and len(t.strip()) > 1]
        if not terms:
            return []

        fts_query = " OR ".join(terms)
        sql = """
            SELECT m.id, m.title, m.content, m.memory_type, m.importance, m.confidence,
                   m.content_hash, m.access_count
            FROM memories_fts f
            JOIN memories m ON m.rowid = f.rowid
            WHERE memories_fts MATCH ?
              AND m.status = 'active'
            ORDER BY rank
            LIMIT 100
        """
        try:
            if session_id:
                sql += " AND m.source_session_id = ?"
                rows = conn.execute(sql, (fts_query, session_id)).fetchall()
            else:
                rows = conn.execute(sql, (fts_query,)).fetchall()
        except Exception:
            # FTS5 parse error on special chars — fall back to empty
            logger.debug("FTS5 parse error on query=%s", query)
            return []

        return [dict(r) for r in rows]

    def _jaccard_rank(
        self, query: str, candidates: list[dict[str, Any]],
    ) -> list[RetrievalHit]:
        """Score candidates by Jaccard similarity on token sets."""
        query_tokens = set(_tokenize(query))
        if not query_tokens:
            return []

        hits: list[RetrievalHit] = []
        for row in candidates:
            text = f"{row.get('title', '')} {row.get('content', '')}"
            cand_tokens = set(_tokenize(text))
            if not cand_tokens:
                continue
            intersection = query_tokens & cand_tokens
            union = query_tokens | cand_tokens
            jaccard = len(intersection) / len(union) if union else 0.0

            if jaccard >= self.min_similarity:
                hits.append(RetrievalHit(
                    id=row["id"],
                    title=row.get("title", ""),
                    content=row.get("content", ""),
                    memory_type=row.get("memory_type", ""),
                    importance=row.get("importance", 0.5),
                    score=jaccard,
                ))
        return hits

    def _record_access(self, hits: list[RetrievalHit]) -> None:
        """Increment access_count and update last_accessed_at."""
        if not hits:
            return
        try:
            with get_connection() as conn:
                conn.executemany(
                    "UPDATE memories SET access_count = access_count + 1, "
                    "last_accessed_at = CURRENT_TIMESTAMP WHERE id = ?",
                    [(h.id,) for h in hits],
                )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _tokenize(text: str) -> list[str]:
    """Simple character-level 2-gram tokenizer for CJK + word-level for Latin."""
    tokens: list[str] = []
    # Split into CJK and non-CJK segments; use bigrams for CJK, whole words for Latin
    import re
    # Simple approach: split on whitespace, then bigram any CJK chunks
    for chunk in re.split(r"\s+", text.lower()):
        if not chunk:
            continue
        # If chunk contains CJK characters, use bigrams
        if re.search(r"[\u4e00-\u9fff]", chunk):
            for i in range(len(chunk) - 1):
                tokens.append(chunk[i:i + 2])
        else:
            # Latin — use as-is after stripping punctuation
            clean = re.sub(r"[^\w]", "", chunk)
            if clean:
                tokens.append(clean)
    return tokens
