from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.core.database import get_connection
from app.utils.ids import new_id


class BaseService:
    def log_operation(self, module: str, action: str, target_id: str, result: str, detail: dict[str, Any]) -> None:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO operation_logs (id, module, action, target_id, result, detail) VALUES (?, ?, ?, ?, ?, ?)",
                (new_id("log"), module, action, target_id, result, json.dumps(detail, ensure_ascii=False)),
            )


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def chunk_text(content: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    if not content.strip():
        return []
    chunks: list[str] = []
    start = 0
    while start < len(content):
        end = min(len(content), start + chunk_size)
        chunks.append(content[start:end])
        if end == len(content):
            break
        start = max(0, end - overlap)
    return chunks


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
