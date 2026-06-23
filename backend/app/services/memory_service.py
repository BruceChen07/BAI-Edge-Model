from __future__ import annotations

from app.core.database import get_connection
from app.schemas.memory import MemoryCreateDTO, MemoryDTO
from app.utils.ids import new_id


class MemoryService:
    def list_all(self) -> list[MemoryDTO]:
        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM memories ORDER BY created_at DESC").fetchall()
        return [MemoryDTO(**dict(row)) for row in rows]

    def create(self, payload: MemoryCreateDTO) -> MemoryDTO:
        memory_id = new_id("mem")
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO memories (id, memory_type, title, content, importance, confidence, write_mode, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (memory_id, payload.memory_type, payload.title, payload.content, payload.importance, payload.confidence, payload.write_mode, payload.status),
            )
            row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        return MemoryDTO(**dict(row))

    def update(self, memory_id: str, payload: MemoryCreateDTO) -> MemoryDTO:
        with get_connection() as conn:
            conn.execute(
                "UPDATE memories SET memory_type = ?, title = ?, content = ?, importance = ?, confidence = ?, write_mode = ?, status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (payload.memory_type, payload.title, payload.content, payload.importance, payload.confidence, payload.write_mode, payload.status, memory_id),
            )
            row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        return MemoryDTO(**dict(row))

    def delete(self, memory_id: str) -> None:
        with get_connection() as conn:
            conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
