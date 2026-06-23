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
from app.schemas.chat import ChatResponseDTO
from app.main import app, chat_service, ingest_service

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


def _screenshot_like_ocr_text() -> str:
    return """# 1.6 深入剖析GPT架构

在本章之前，我们提到了 GPT 类模型、GPT-3 和 ChatGPT。现在让我们更深入地了解通用的 GPT 架构。
首先，GPT 是“生成预训练变换器”（Generative Pretrained Transformer）的缩写，最初是在以下论文中提出的：

- 《通过生成预训练改善语言理解》（2018）是由 OpenAI 的 Radford 等人撰写的，链接：http://cdn.openai.com/researchcovers/language-unsupervised/language_understanding_paper.pdf
""".strip()


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


def test_catalog_sync_local_upserts_models(monkeypatch) -> None:
    monkeypatch.setattr(
        chat_service.ollama_service,
        "list_models",
        lambda: [
            {"name": "qwen3.5:9b", "size": 1, "modified_at": "now", "digest": "abc"},
            {"name": "llama3.2:3b", "size": 1,
                "modified_at": "now", "digest": "def"},
            {"name": "gemma4:12b", "size": 1, "modified_at": "now", "digest": "ghi"},
        ],
    )

    sync_response = client.post(
        "/api/v1/catalog/sync", json={"source": "local"})
    assert sync_response.status_code == 200
    assert sync_response.json(
    )["data"]["message"] == "local model sync completed"

    list_response = client.get(
        "/api/v1/catalog", params={"limit": 100, "sort_by": "model_name", "sort_dir": "asc"})
    assert list_response.status_code == 200
    payload = list_response.json()["data"]
    items = payload["items"]
    names = [i["model_name"] for i in items]
    assert "qwen3.5:9b" in names
    assert "llama3.2:3b" in names
    assert "gemma4:12b" in names
    synced_item = next(i for i in items if i["model_name"] == "qwen3.5:9b")
    assert synced_item["source"] == "local"
    assert synced_item["available"] is True


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
    citations = chat_response.json()["data"]["citations"]
    assert citations
    assert citations[0]["file_name"] == "demo.txt"
    assert "source_label" in citations[0]
    assert citations[0]["chunk_index"] >= 0
    assert "quote_excerpt" in citations[0]
    assert citations[0]["matched_terms"]

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


def test_chat_completions_no_longer_depends_on_debug_server(monkeypatch) -> None:
    session_response = client.post(
        "/api/v1/sessions", json={"title": "Debug Hook Regression"})
    assert session_response.status_code == 200
    session_id = session_response.json()["data"]["id"]

    monkeypatch.setattr(
        chat_service,
        "answer",
        lambda payload: ChatResponseDTO(
            answer=f"ok: {payload.query}",
            citations=[],
            model_used=payload.model_name or "unknown",
        ),
    )

    response = client.post(
        "/api/v1/chat/completions",
        json={
            "session_id": session_id,
            "query": "ping",
            "model_name": "gemma4:12b",
            "knowledge_base_ids": [],
        },
    )
    assert response.status_code == 200
    assert response.json()["data"]["answer"] == "ok: ping"


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
    chunk_page = chunks_response.json()["data"]
    assert "items" in chunk_page
    chunk_texts = [item["content"] for item in chunk_page["items"]]
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


def test_knowledge_base_reindex_stats_and_chunk_pagination() -> None:
    kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Reindex KB", "description": "reindex"},
    )
    assert kb_response.status_code == 200
    kb_id = kb_response.json()["data"]["id"]

    upload_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files/upload?enable_ocr=true",
        files={
            "file": (
                "reindex.txt",
                io.BytesIO(
                    b"alpha beta gamma delta epsilon zeta eta theta iota"),
                "text/plain",
            )
        },
    )
    assert upload_response.status_code == 200
    document_id = upload_response.json()["data"]["document"]["id"]

    reindex_response = client.post(f"/api/v1/knowledge-bases/{kb_id}/reindex")
    assert reindex_response.status_code == 200
    task_id = reindex_response.json()["data"]["id"]

    for _ in range(40):
        task_response = client.get(f"/api/v1/tasks/{task_id}")
        assert task_response.status_code == 200
        task_payload = task_response.json()["data"]
        if task_payload["status"] == "done":
            break
    else:
        raise AssertionError("reindex task did not finish in time")

    stats_response = client.get(f"/api/v1/knowledge-bases/{kb_id}/stats")
    assert stats_response.status_code == 200
    stats = stats_response.json()["data"]
    assert stats["file_count"] == 1
    assert stats["chunk_count"] >= 1
    assert stats["token_count"] >= 1

    chunks_response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/chunks",
        params={"document_id": document_id, "offset": 0, "limit": 1},
    )
    assert chunks_response.status_code == 200
    payload = chunks_response.json()["data"]
    assert payload["limit"] == 1
    assert payload["offset"] == 0
    assert payload["total"] >= 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["document_id"] == document_id


def test_screenshot_source_question_uses_grounded_answer(monkeypatch) -> None:
    monkeypatch.setattr(
        chat_service.ollama_service,
        "list_models",
        lambda: [{"name": "qwen3.5:4b", "size": 1,
                  "modified_at": "now", "digest": "abc"}],
    )

    llm_call_count = {"value": 0}

    def _unexpected_llm_call(**_: object) -> str:
        llm_call_count["value"] += 1
        return "incorrect llm answer"

    monkeypatch.setattr(chat_service.ollama_service,
                        "chat", _unexpected_llm_call)
    monkeypatch.setattr(
        ingest_service.parser_service,
        "extract_text",
        lambda *args, **kwargs: (_screenshot_like_ocr_text(), "done"),
    )

    kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Screenshot KB", "description": "ocr"},
    )
    assert kb_response.status_code == 200
    kb_id = kb_response.json()["data"]["id"]

    upload_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files/upload?enable_ocr=true",
        files={
            "file": (
                "gpt-origin.png",
                io.BytesIO(b"fake-image-content"),
                "image/png",
            )
        },
    )
    assert upload_response.status_code == 200

    session_response = client.post(
        "/api/v1/sessions",
        json={"title": "Screenshot Session"},
    )
    assert session_response.status_code == 200
    session_id = session_response.json()["data"]["id"]

    chat_response = client.post(
        "/api/v1/chat/completions",
        json={
            "session_id": session_id,
            "query": "GPT 是生成预训练变换器的缩写，最初是在哪个论文中提出的",
            "model_name": "qwen3.5:4b",
            "knowledge_base_ids": [kb_id],
        },
    )
    assert chat_response.status_code == 200
    payload = chat_response.json()["data"]
    assert llm_call_count["value"] == 0
    assert "《通过生成预训练改善语言理解》" in payload["answer"]
    assert "2018" in payload["answer"]
    assert "Radford" in payload["answer"]
    assert "language_understanding_paper.pdf" in payload["answer"]
    assert payload["citations"]
    assert payload["citations"][0]["heading_path"] == "1.6 深入剖析GPT架构"
    assert payload["citations"][0]["matched_terms"]


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
