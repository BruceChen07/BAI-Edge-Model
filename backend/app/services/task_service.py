from __future__ import annotations

from app.core.database import get_connection
from app.schemas.task import TaskDTO
from app.utils.ids import new_id


class TaskService:
    def create(self, task_type: str, related_id: str, status: str = "pending", progress: float = 0) -> TaskDTO:
        task_id = new_id("task")
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO parse_tasks (id, task_type, related_id, status, progress) VALUES (?, ?, ?, ?, ?)",
                (task_id, task_type, related_id, status, progress),
            )
            row = conn.execute("SELECT * FROM parse_tasks WHERE id = ?", (task_id,)).fetchone()
        return TaskDTO(**dict(row))

    def update(self, task_id: str, *, status: str, progress: float, error_code: str = "", error_message: str = "") -> TaskDTO:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE parse_tasks
                SET status = ?, progress = ?, error_code = ?, error_message = ?,
                    finished_at = CASE WHEN ? IN ('done', 'failed', 'cancelled') THEN CURRENT_TIMESTAMP ELSE finished_at END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, progress, error_code, error_message, status, task_id),
            )
            row = conn.execute("SELECT * FROM parse_tasks WHERE id = ?", (task_id,)).fetchone()
        return TaskDTO(**dict(row))

    def list_all(self) -> list[TaskDTO]:
        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM parse_tasks ORDER BY created_at DESC").fetchall()
        return [TaskDTO(**dict(row)) for row in rows]

    def get(self, task_id: str) -> TaskDTO:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM parse_tasks WHERE id = ?", (task_id,)).fetchone()
        return TaskDTO(**dict(row))
