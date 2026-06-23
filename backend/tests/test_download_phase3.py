"""
Phase 3: multi-source download, resume state, and SSE progress tests.
"""
from __future__ import annotations
from app.services.multi_source_resolver import MultiSourceResolver
from app.services.download_resumer import DownloadResumer
from app.services.download_progress_tracker import DownloadProgressTracker
from app.services.download_orchestrator import DownloadOrchestrator
from app.schemas.download import DownloadProgressEvent
from app.main import app, download_orchestrator
from app.core.database import init_db

import asyncio
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import config


TEST_STORAGE_ROOT = config.project_root / "storage" / "test_phase3"
TEST_DB_PATH = TEST_STORAGE_ROOT / "download_phase3.db"

object.__setattr__(config, "storage_root", TEST_STORAGE_ROOT)
object.__setattr__(config, "files_root", TEST_STORAGE_ROOT / "files")
object.__setattr__(config, "exports_root", TEST_STORAGE_ROOT / "exports")
object.__setattr__(config, "logs_root", TEST_STORAGE_ROOT / "logs")
object.__setattr__(config, "indexes_root", TEST_STORAGE_ROOT / "indexes")
object.__setattr__(config, "db_path", TEST_DB_PATH)

if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()


client = TestClient(app)
init_db()


@pytest.fixture(autouse=True)
def _reset_db() -> None:
    init_db()
    # Clear phase 3 test data between tests
    from app.core.database import get_connection
    with get_connection() as conn:
        conn.execute("DELETE FROM download_jobs")


@pytest.fixture
def resolver() -> MultiSourceResolver:
    return MultiSourceResolver()


@pytest.fixture
def resumer() -> DownloadResumer:
    return DownloadResumer()


@pytest.fixture
def tracker() -> DownloadProgressTracker:
    return DownloadProgressTracker()


@pytest.fixture
def orchestrator() -> DownloadOrchestrator:
    return DownloadOrchestrator()


class TestMultiSourceResolver:
    def test_auto_plan_contains_all_sources(self, resolver):
        plan = resolver.resolve("qwen3:8b", prefer="auto")
        names = [s.name for s in plan.sources]
        assert names == ["ollama", "huggingface", "modelscope"]

    def test_prefer_modelscope_only(self, resolver):
        plan = resolver.resolve("qwen3:8b", prefer="modelscope")
        assert len(plan.sources) == 1
        assert plan.sources[0].name == "modelscope"

    def test_prefer_huggingface_only(self, resolver):
        plan = resolver.resolve("llama3.2:3b", prefer="huggingface")
        assert len(plan.sources) == 1
        assert plan.sources[0].name == "huggingface"

    def test_known_modelscope_mapping(self, resolver):
        url = resolver._build_modelscope_url("qwen3:8b")
        assert "Qwen/Qwen3-8B-GGUF" in url
        assert url.startswith("https://modelscope.cn/")

    def test_known_hf_mapping(self, resolver):
        url = resolver._build_hf_url("llama3.2:3b")
        assert "Llama-3.2-3B-Instruct-GGUF" in url
        assert url.startswith("https://huggingface.co/")

    def test_unknown_model_fallback_mapping(self, resolver):
        url = resolver._build_modelscope_url("custom:7b")
        assert "custom-7b" in url


class TestDownloadResumer:
    def test_create_job_defaults(self, resumer):
        job = resumer.create_job("qwen3:8b")
        assert job.model_name == "qwen3:8b"
        assert job.status == "pending"
        assert job.chunk_size == 1048576
        assert job.output_path.endswith("qwen3_8b.gguf")

    def test_get_job_by_model(self, resumer):
        created = resumer.create_job("qwen3:8b")
        fetched = resumer.get_job_by_model("qwen3:8b")
        assert fetched is not None
        assert fetched.id == created.id

    def test_list_jobs(self, resumer):
        resumer.create_job("qwen3:8b")
        resumer.create_job("llama3.2:3b")
        jobs = resumer.list_jobs()
        assert len(jobs) == 2

    def test_update_progress_sets_status(self, resumer):
        job = resumer.create_job("qwen3:8b")
        resumer.update_progress(job.id, 50, 100)
        updated = resumer.get_job(job.id)
        assert updated.downloaded_bytes == 50
        assert updated.total_bytes == 100
        assert updated.status == "downloading"

    def test_mark_completed(self, resumer):
        job = resumer.create_job("qwen3:8b")
        resumer.mark_completed(job.id)
        updated = resumer.get_job(job.id)
        assert updated.status == "completed"
        assert updated.completed_at != ""

    def test_mark_failed_increments_retry(self, resumer):
        job = resumer.create_job("qwen3:8b")
        resumer.mark_failed(job.id, "boom")
        updated = resumer.get_job(job.id)
        assert updated.status == "failed"
        assert updated.retry_count == 1
        assert updated.error_message == "boom"

    def test_pause_marks_paused(self, resumer):
        job = resumer.create_job("qwen3:8b")
        resumer.pause(job.id)
        updated = resumer.get_job(job.id)
        assert updated.status == "paused"

    def test_get_resume_offset(self, resumer):
        job = resumer.create_job("qwen3:8b")
        resumer.update_progress(job.id, 1234, 9999)
        assert resumer.get_resume_offset(job.id) == 1234

    def test_can_resume_true_after_pause(self, resumer):
        job = resumer.create_job("qwen3:8b")
        resumer.update_progress(job.id, 2048, 4096)
        resumer.pause(job.id)
        assert resumer.can_resume(job.id) is True

    def test_can_resume_false_when_zero_progress(self, resumer):
        job = resumer.create_job("qwen3:8b")
        assert resumer.can_resume(job.id) is False

    def test_get_job_missing_raises(self, resumer):
        with pytest.raises(ValueError):
            resumer.get_job("missing")


class TestDownloadProgressTracker:
    def test_subscribe_unsubscribe(self, tracker):
        q = tracker.subscribe("qwen3:8b")
        assert "qwen3:8b" in tracker._queues
        tracker.unsubscribe("qwen3:8b", q)
        assert "qwen3:8b" not in tracker._queues

    def test_broadcast_puts_event(self, tracker):
        q = tracker.subscribe("qwen3:8b")
        event = DownloadProgressEvent(
            model_name="qwen3:8b", status="downloading", percent=10)
        tracker.broadcast("qwen3:8b", event)
        got = q.get_nowait()
        assert got.model_name == "qwen3:8b"
        assert got.percent == 10

    def test_stream_emits_event_and_terminal(self, tracker):
        async def _run() -> list[str]:
            gen = tracker.stream("qwen3:8b", heartbeat_interval=5.0)
            first_task = asyncio.create_task(gen.__anext__())
            await asyncio.sleep(0.01)
            tracker.broadcast(
                "qwen3:8b",
                DownloadProgressEvent(
                    model_name="qwen3:8b",
                    status="completed",
                    percent=100,
                ),
            )
            first = await first_task
            second = await gen.__anext__()
            return [first, second]

        events = asyncio.run(_run())
        assert "data:" in events[0]
        assert "event: completed" in events[1]

    def test_stream_heartbeat(self, tracker):
        async def _run() -> str:
            gen = tracker.stream("qwen3:8b", heartbeat_interval=0.01)
            first = await gen.__anext__()
            return first

        event = asyncio.run(_run())
        assert ": heartbeat" in event


class TestDownloadOrchestrator:
    def test_resolve_plan(self, orchestrator):
        plan = orchestrator.resolve_plan("qwen3:8b")
        assert plan.model_name == "qwen3:8b"
        assert len(plan.sources) >= 1

    @patch("app.services.ollama_service.OllamaService.pull_model")
    def test_pull_model_ollama_success(self, mock_pull, orchestrator):
        mock_pull.return_value = {"status": "success"}
        result = orchestrator.pull_model("qwen3:8b", source="auto")
        assert result["status"] == "completed"
        assert result["source"] == "ollama"

    @patch("app.services.ollama_service.OllamaService.pull_model")
    def test_pull_model_fallback_to_http_source(self, mock_pull, orchestrator):
        mock_pull.side_effect = RuntimeError("ollama down")
        result = orchestrator.pull_model("qwen3:8b", source="modelscope")
        assert result["status"] == "completed"
        assert result["source"] == "modelscope"
        assert "job_id" in result

    def test_pause_existing_job(self, orchestrator):
        job = orchestrator.create_job("qwen3:8b")
        orchestrator.pause(job.id)
        updated = orchestrator.get_job(job.id)
        assert updated.status == "paused"

    def test_list_jobs(self, orchestrator):
        orchestrator.create_job("qwen3:8b")
        orchestrator.create_job("llama3.2:3b")
        jobs = orchestrator.list_jobs()
        assert len(jobs) == 2


class TestDownloadApi:
    def test_download_plan_endpoint(self):
        response = client.get("/api/v1/download/plan/qwen3:8b")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["model_name"] == "qwen3:8b"
        assert len(data["sources"]) >= 1

    def test_download_pull_endpoint(self):
        with patch("app.services.ollama_service.OllamaService.pull_model", side_effect=RuntimeError("down")):
            response = client.post(
                "/api/v1/download/pull",
                json={"model_name": "qwen3:8b", "source": "modelscope"},
            )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == "completed"
        assert data["source"] == "modelscope"

    def test_download_jobs_endpoint(self):
        download_orchestrator.create_job("qwen3:8b")
        response = client.get("/api/v1/download/jobs")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] >= 1

    def test_download_job_detail_404(self):
        response = client.get("/api/v1/download/jobs/missing")
        assert response.status_code == 404

    def test_download_job_pause_endpoint(self):
        job = download_orchestrator.create_job("qwen3:8b")
        response = client.post(f"/api/v1/download/jobs/{job.id}/pause")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["message"] == "paused"
