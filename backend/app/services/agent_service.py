from __future__ import annotations

import json
from typing import Iterator

from app.core.database import get_connection
from app.schemas.agent import AgentRequestDTO
from app.services.chat_service import ChatService
from app.services.memory_service import MemoryService
from app.utils.ids import new_id


class AgentService:
    def __init__(self) -> None:
        self.chat_service = ChatService()
        self.memory_service = MemoryService()

    def tools(self) -> list[str]:
        return [
            "knowledge_base_search",
            "memory_read",
            "memory_write",
            "calculator",
            "export_markdown",
            "export_docx",
            "list_workspace_files",
        ]

    def run(self, payload: AgentRequestDTO) -> dict:
        run_id = new_id("run")
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO agent_runs (id, session_id, task_text, status, step_count) VALUES (?, ?, ?, 'running', 0)",
                (run_id, payload.session_id, payload.task),
            )
        steps = self._build_steps(payload)
        with get_connection() as conn:
            for index, step in enumerate(steps, start=1):
                conn.execute(
                    "INSERT INTO agent_steps (id, run_id, step_no, step_type, tool_name, tool_input, tool_output, status) VALUES (?, ?, ?, ?, ?, ?, ?, 'done')",
                    (new_id("step"), run_id, index, step["step_type"], step["tool_name"], step["tool_input"], step["tool_output"]),
                )
            conn.execute(
                "UPDATE agent_runs SET status = 'done', step_count = ?, final_answer = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (len(steps), steps[-1]["tool_output"], run_id),
            )
        return {"run_id": run_id, "steps": steps, "final_answer": steps[-1]["tool_output"]}

    def stream(self, payload: AgentRequestDTO) -> Iterator[str]:
        result = self.run(payload)
        yield self._sse("message_start", {"run_id": result["run_id"]})
        for step in result["steps"]:
            yield self._sse("tool_call", {"tool_name": step["tool_name"], "input": step["tool_input"]})
            yield self._sse("tool_result", {"tool_name": step["tool_name"], "output": step["tool_output"]})
        yield self._sse("message_end", {"final_answer": result["final_answer"], "run_id": result["run_id"]})

    def get_run(self, run_id: str) -> dict:
        with get_connection() as conn:
            run = conn.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,)).fetchone()
            steps = conn.execute("SELECT * FROM agent_steps WHERE run_id = ? ORDER BY step_no ASC", (run_id,)).fetchall()
        return {"run": dict(run), "steps": [dict(step) for step in steps]}

    def _build_steps(self, payload: AgentRequestDTO) -> list[dict]:
        memories = self.memory_service.list_all()
        memory_summary = memories[0].content if memories else "No memory available."
        return [
            {
                "step_type": "tool",
                "tool_name": "memory_read",
                "tool_input": payload.task,
                "tool_output": memory_summary,
            },
            {
                "step_type": "tool",
                "tool_name": "knowledge_base_search",
                "tool_input": payload.task,
                "tool_output": f"Search completed for task: {payload.task}",
            },
            {
                "step_type": "final",
                "tool_name": "final_answer",
                "tool_input": payload.task,
                "tool_output": f"Agent completed task '{payload.task}' with {len(payload.tools or self.tools())} tool definitions available.",
            },
        ]

    def _sse(self, event: str, payload: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
