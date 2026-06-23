"""
Memory compression engine — deduplication, merging, importance-based archival.
Designed for edge devices: works offline, minimal computation.
"""
from __future__ import annotations

import logging
from typing import Any

from app.core.config import COMPRESS_DEDUP_THRESHOLD, COMPRESS_IMPORTANCE_MIN
from app.core.database import get_connection
from app.core.logging import get_logger

logger = get_logger("app.memory.compression")


class CompressionEngine:
    """
    Compresses the memory store to control storage growth.

    1. Hash dedup (Phase 1): remove exact-content duplicates
    2. Jaccard dedup (Phase 2): merge highly similar memories
    3. Importance archival (Phase 2): archive low-importance old memories

    Target: ≥60% reduction in duplicate/redundant memory records.
    """

    def __init__(
        self,
        dedup_threshold: float = COMPRESS_DEDUP_THRESHOLD,
        importance_min: float = COMPRESS_IMPORTANCE_MIN,
    ) -> None:
        self.dedup_threshold = dedup_threshold
        self.importance_min = importance_min

    def compact(self) -> dict[str, int]:
        """
        Run a full compaction pass. Returns counts of each operation.
        """
        stats = {
            "hash_duplicates_removed": 0,
            "similar_merged_pairs": 0,
            "low_importance_archived": 0,
        }

        stats["hash_duplicates_removed"] = self._dedup_by_hash()
        stats["similar_merged_pairs"] = self._dedup_by_similarity()
        stats["low_importance_archived"] = self._archive_low_importance()

        total = sum(stats.values())
        if total > 0:
            logger.info("Compression engine compacted %d records: %s", total, stats)
        return stats

    # ------------------------------------------------------------------
    # Compression operations
    # ------------------------------------------------------------------
    def _dedup_by_hash(self) -> int:
        """Remove exact duplicates (same content_hash)."""
        with get_connection() as conn:
            conn.execute("""
                DELETE FROM memories WHERE rowid NOT IN (
                    SELECT MIN(rowid) FROM memories
                    WHERE status = 'active'
                    GROUP BY content_hash
                ) AND status = 'active'
            """)
            # Also clean FTS5
            conn.execute("DELETE FROM memories_fts WHERE rowid NOT IN (SELECT rowid FROM memories)")
            return conn.total_changes

    def _dedup_by_similarity(self) -> int:
        """
        Merge memories with high Jaccard similarity within the same memory_type.
        For edge performance: only compare memories created within 7 days of each other.
        """
        with get_connection() as conn:
            # Get active memories grouped by type, ordered by recency
            rows = conn.execute(
                "SELECT id, title, content, memory_type, importance, created_at "
                "FROM memories WHERE status = 'active' ORDER BY memory_type, created_at DESC"
            ).fetchall()

        merged = 0
        seen: set[str] = set()
        for i in range(len(rows)):
            if rows[i]["id"] in seen:
                continue
            for j in range(i + 1, min(i + 20, len(rows))):  # windowed comparison
                if rows[j]["id"] in seen:
                    continue
                if rows[i]["memory_type"] != rows[j]["memory_type"]:
                    continue
                sim = self._jaccard(
                    f'{rows[i]["title"]} {rows[i]["content"]}',
                    f'{rows[j]["title"]} {rows[j]["content"]}',
                )
                if sim >= self.dedup_threshold:
                    # Merge: keep the more important one, absorb the other
                    winner, loser = (rows[i], rows[j]) if rows[i]["importance"] >= rows[j]["importance"] else (rows[j], rows[i])
                    self._merge_memories(winner, loser)
                    seen.add(loser["id"])
                    merged += 1

        return merged

    def _archive_low_importance(self) -> int:
        """Archive memories with importance below threshold and created > 30 days ago."""
        with get_connection() as conn:
            conn.execute(
                "UPDATE memories SET status = 'archived' "
                "WHERE status = 'active' AND importance < ? "
                "AND created_at < datetime('now', '-30 days')",
                (self.importance_min,),
            )
            return conn.total_changes

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _merge_memories(self, winner: dict[str, Any], loser: dict[str, Any]) -> None:
        """Keep winner, bump its importance, delete loser."""
        new_importance = min(1.0, max(winner["importance"], loser["importance"]) + 0.1)
        with get_connection() as conn:
            conn.execute(
                "UPDATE memories SET importance = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (new_importance, winner["id"]),
            )
            conn.execute("DELETE FROM memories_fts WHERE rowid = (SELECT rowid FROM memories WHERE id = ?)", (loser["id"],))
            conn.execute("DELETE FROM memories WHERE id = ?", (loser["id"],))

    @staticmethod
    def _jaccard(text_a: str, text_b: str) -> float:
        """Token-based Jaccard similarity."""
        tokens_a = set(_tokenize(text_a))
        tokens_b = set(_tokenize(text_b))
        if not tokens_a or not tokens_b:
            return 0.0
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        return len(intersection) / len(union) if union else 0.0


def _tokenize(text: str) -> list[str]:
    """Simple tokenizer: 2-gram for CJK, word-level for Latin."""
    import re
    tokens: list[str] = []
    for chunk in re.split(r"\s+", text.lower()):
        if not chunk:
            continue
        if re.search(r"[\u4e00-\u9fff]", chunk):
            for i in range(len(chunk) - 1):
                tokens.append(chunk[i:i + 2])
        else:
            clean = re.sub(r"[^\w]", "", chunk)
            if clean:
                tokens.append(clean)
    return tokens
