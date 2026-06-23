"""
Short-term memory cache with LRU eviction and TTL expiry.
Designed for edge devices: pure in-process memory, no external dependencies.
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from app.core.config import SHORT_TERM_MAX_BYTES, SHORT_TERM_MAX_ENTRIES, SHORT_TERM_TTL_SECONDS
from app.core.logging import get_logger

logger = get_logger("app.memory.cache")


@dataclass
class CacheEntry:
    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at

    @property
    def idle_seconds(self) -> float:
        return time.time() - self.accessed_at


class ShortTermMemoryCache:
    """
    Thread-safe LRU cache with TTL-based expiry for session context.

    Limits:
      - max_entries: maximum number of cached items (default 100)
      - max_bytes: approximate memory ceiling (default 10 MB)
      - ttl_seconds: entries older than this are considered expired (default 300s)

    Usage:
        cache = ShortTermMemoryCache()
        cache.set("session:abc123:recent", [...])    # store
        val = cache.get("session:abc123:recent")      # retrieve (refreshes access time)
        cache.prune()                                  # remove expired entries
    """

    def __init__(
        self,
        max_entries: int = SHORT_TERM_MAX_ENTRIES,
        max_bytes: int = SHORT_TERM_MAX_BYTES,
        ttl_seconds: int = SHORT_TERM_TTL_SECONDS,
    ) -> None:
        self._store: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self.ttl_seconds = ttl_seconds
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get(self, key: str) -> Any | None:
        """Retrieve a value by key. Returns None on miss or expiry."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            if entry.age_seconds > self.ttl_seconds:
                self._store.pop(key)
                self._evictions += 1
                self._misses += 1
                return None
            entry.accessed_at = time.time()
            self._store.move_to_end(key)
            self._hits += 1
            return entry.value

    def set(self, key: str, value: Any) -> None:
        """Store a value. Evicts LRU entries if limits are exceeded."""
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            entry = CacheEntry(key=key, value=value)
            self._store[key] = entry
            self._enforce_limits()

    def delete(self, key: str) -> bool:
        """Remove a key. Returns True if deleted."""
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def clear_session(self, session_id: str) -> int:
        """Remove all entries for a given session. Returns count removed."""
        prefix = f"session:{session_id}:"
        with self._lock:
            keys = [k for k in self._store if k.startswith(prefix)]
            for k in keys:
                del self._store[k]
            return len(keys)

    def prune(self) -> int:
        """Remove all expired entries. Returns count removed."""
        with self._lock:
            expired = [
                k for k, e in self._store.items()
                if e.age_seconds > self.ttl_seconds
            ]
            for k in expired:
                del self._store[k]
            self._evictions += len(expired)
            return len(expired)

    def stats(self) -> dict[str, Any]:
        """Return cache statistics for monitoring."""
        with self._lock:
            return {
                "size": len(self._store),
                "max_entries": self.max_entries,
                "max_bytes": self.max_bytes,
                "ttl_seconds": self.ttl_seconds,
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "hit_rate": (
                    self._hits / (self._hits + self._misses)
                    if (self._hits + self._misses) > 0
                    else 0.0
                ),
            }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _enforce_limits(self) -> None:
        """Evict oldest entries until within limits."""
        # Evict by count
        while len(self._store) > self.max_entries:
            oldest_key, _ = self._store.popitem(last=False)
            self._evictions += 1
            logger.debug("Cache eviction (count) key=%s", oldest_key)

        # Evict by approximate byte size
        while self._estimate_bytes() > self.max_bytes and len(self._store) > 1:
            oldest_key, _ = self._store.popitem(last=False)
            self._evictions += 1
            logger.debug("Cache eviction (bytes) key=%s", oldest_key)

    def _estimate_bytes(self) -> int:
        """Rough memory estimate (quick, no deep serialization)."""
        total = 0
        for entry in self._store.values():
            total += len(str(entry.key)) + len(str(entry.value))
        return total


# ---------------------------------------------------------------------------
# Global singleton for the application lifetime
# ---------------------------------------------------------------------------
_cache: ShortTermMemoryCache | None = None


def get_cache() -> ShortTermMemoryCache:
    global _cache
    if _cache is None:
        _cache = ShortTermMemoryCache()
    return _cache
