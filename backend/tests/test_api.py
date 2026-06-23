from __future__ import annotations

import io
import logging
from pathlib import Path

import httpx
from fastapi.testclient import TestClient
from docx import Document
from openpyxl import Workbook

from app.core.database import init_db
from app.core.config import config
from app.core.logging import setup_logging
from app.main import app, chat_service

test_db_path = config.project_root / "storage" / "test_bai_edge_model.db"
object.__setattr__(config, "db_path", test_db_path)
if config.db_path.exists():
    config.db_path.unlink()

client = TestClient(app)
init_db()
setup_logging()


def _create_docx_bytes() -> bytes:
    buffer = io.BytesIO()
    document = Document()
    document.add_heading("Deployment", level=1)
    document.add_paragraph("Edge deployment with local rag memory.")
    document.save(buffer)
    return buffer.getvalue()


def _create_xlsx_bytes() -> bytes:
    buffer = io.BytesIO()
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Plan"
    sheet["A1"] = "Topic"
    sheet["B1"] = "Value"
    sheet["A2"] = "RAG"
    sheet["B2"] = "Local retrieval"
    workbook.save(buffer)
    return buffer.getvalue()


def test_system_info() -> None:
    response = client.get("/api/v1/system/info")
    assert response.status_code == 200
    assert response.json()["data"]["app_name"] == "BAI Edge Model"


def test_models_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        chat_service.ollama_service,
        "list_models",
        lambda: [
            {"name": "qwen3.5:9b", "size": 1, "modified_at": "now", "digest": "abc"},
            {"name": "qwen3.5:4b", "size": 1, "modified_at": "now", "digest": "def"},
        ],
    )
    response = client.get("/api/v1/models")
    assert response.status_code == 200
    assert response.json()["data"][0]["name"] == "qwen3.5:9b"


def test_knowledge_base_chat_export_flow(monkeypatch) -> None:
    monkeypatch.setattr(
        chat_service.ollama_service,
        "list_models",
        lambda: [{"name": "qwen3.5:4b", "size": 1,
                  "modified_at": "now", "digest": "abc"}],
    )
    monkeypatch.setattr(
        chat_service.ollama_service,
        "chat",
        lambda **kwargs: f"mocked ollama reply from {kwargs['model_name']}",
    )

    kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Demo KB", "description": "test"},
    )
    assert kb_response.status_code == 200
    kb_id = kb_response.json()["data"]["id"]

    upload_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files/upload?enable_ocr=true",
        files={
            "file": (
                "demo.txt",
                io.BytesIO(b"edge deployment rag agent memory export"),
                "text/plain",
            )
        },
    )
    assert upload_response.status_code == 200

    session_response = client.post(
        "/api/v1/sessions", json={"title": "Demo Session"})
    assert session_response.status_code == 200
    session_id = session_response.json()["data"]["id"]

    chat_response = client.post(
        "/api/v1/chat/completions",
        json={
            "session_id": session_id,
            "query": "deployment rag",
            "model_name": "qwen3.5:4b",
            "knowledge_base_ids": [kb_id],
        },
    )
    assert chat_response.status_code == 200
    assert "mocked ollama reply from qwen3.5:4b" in chat_response.json()[
        "data"]["answer"]
    assert chat_response.json()["data"]["model_used"] == "qwen3.5:4b"

    export_response = client.post(
        "/api/v1/exports/markdown",
        json={
            "source_type": "session",
            "source_id": session_id,
            "title": "session-export",
        },
    )
    assert export_response.status_code == 200
    export_path = Path(export_response.json()["data"]["file_path"])
    assert export_path.exists()


def test_docx_xlsx_ingest_and_delete() -> None:
    kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Parser KB", "description": "parser"},
    )
    assert kb_response.status_code == 200
    kb_id = kb_response.json()["data"]["id"]

    docx_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files/upload?enable_ocr=true",
        files={
            "file": (
                "plan.docx",
                io.BytesIO(_create_docx_bytes()),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert docx_response.status_code == 200
    docx_id = docx_response.json()["data"]["document"]["id"]

    xlsx_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files/upload?enable_ocr=true",
        files={
            "file": (
                "plan.xlsx",
                io.BytesIO(_create_xlsx_bytes()),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert xlsx_response.status_code == 200

    chunks_response = client.get(f"/api/v1/knowledge-bases/{kb_id}/chunks")
    assert chunks_response.status_code == 200
    chunk_texts = [item["content"] for item in chunks_response.json()["data"]]
    assert any(
        "Edge deployment with local rag memory." in text for text in chunk_texts)
    assert any("Local retrieval" in text for text in chunk_texts)

    delete_response = client.delete(
        f"/api/v1/knowledge-bases/{kb_id}/files/{docx_id}")
    assert delete_response.status_code == 200
    files_response = client.get(f"/api/v1/knowledge-bases/{kb_id}/files")
    assert files_response.status_code == 200
    remaining_ids = [item["id"] for item in files_response.json()["data"]]
    assert docx_id not in remaining_ids


def test_ollama_timeout_logs_are_queryable(monkeypatch) -> None:
    for path in config.logs_root.glob("app.log*"):
        path.write_text("", encoding="utf-8")

    monkeypatch.setattr(
        chat_service.ollama_service,
        "list_models",
        lambda: [{"name": "gemma4:12b", "size": 1,
                  "modified_at": "now", "digest": "abc"}],
    )

    def _raise_timeout(**_: object) -> str:
        raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr(chat_service.ollama_service, "chat", _raise_timeout)

    trace_id = "trace-timeout-test"
    session_response = client.post(
        "/api/v1/sessions", json={"title": "Timeout Session"})
    session_id = session_response.json()["data"]["id"]

    response = client.post(
        "/api/v1/chat/completions",
        json={
            "session_id": session_id,
            "query": "trigger timeout",
            "model_name": "gemma4:12b",
            "knowledge_base_ids": [],
        },
        headers={"X-Trace-Id": trace_id},
    )
    assert response.status_code == 502

    logs_response = client.get(
        "/api/v1/logs",
        params={"module": "chat", "trace_id": trace_id, "limit": 20},
    )
    assert logs_response.status_code == 200
    events = logs_response.json()["data"]
    assert any(item["event"] == "chat.unexpected_error" for item in events)
    timeout_entries = [
        item for item in events if item["event"] == "chat.unexpected_error"]
    assert timeout_entries
    assert timeout_entries[-1]["trace_id"] == trace_id
    assert timeout_entries[-1]["context"]["session_id"] == session_id
    assert "timed out" in timeout_entries[-1]["message"].lower(
    ) or "timed out" in timeout_entries[-1].get("exception", "").lower()
