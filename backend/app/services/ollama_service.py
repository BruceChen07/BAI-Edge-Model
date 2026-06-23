from __future__ import annotations

import json
import os
import re
import time
import traceback
from collections.abc import Iterator
from typing import Any

import httpx

from app.core.config import DEFAULT_TIMEOUT_TIER, TIMEOUT_TIERS, config
from app.core.logging import get_logger, log_event
from app.core.request_context import get_trace_id


class OllamaService:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        self.logger = get_logger("app.ollama")

    def _extract_param_size(self, model_name: str) -> str:
        """Extract parameter-size label from model name for timeout tier lookup."""
        name_lower = model_name.lower()
        match = re.search(r"[:|\-_]?(\d+\.?\d*)[bB]", name_lower)
        if match:
            return f"{match.group(1)}B"
        return "unknown"

    def _resolve_timeout_tier(self, model_name: str) -> dict[str, float]:
        """Resolve timeout values: user override > tiered preset > defaults."""
        if config.user_timeout_override_seconds is not None:
            return {
                "connect": config.ollama_connect_timeout_seconds,
                "read": config.user_timeout_override_seconds,
                "write": config.ollama_write_timeout_seconds,
                "pool": config.ollama_pool_timeout_seconds,
            }
        param_size = self._extract_param_size(model_name)
        return TIMEOUT_TIERS.get(param_size, DEFAULT_TIMEOUT_TIER)

    def _chat_timeout(self, model_name: str = "unknown") -> httpx.Timeout:
        tier = self._resolve_timeout_tier(model_name)
        return httpx.Timeout(
            connect=tier["connect"],
            read=tier["read"],
            write=tier["write"],
            pool=tier["pool"],
        )

    def list_models(self) -> list[dict[str, Any]]:
        started_at = time.time()
        try:
            with httpx.Client(timeout=config.ollama_list_timeout_seconds) as client:
                response = client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError:
            log_event(
                self.logger,
                40,
                "ollama.list_models.failed",
                "Ollama model list request failed",
                module_name="ollama",
                trace_id=get_trace_id(),
                base_url=self.base_url,
                timeout_seconds=config.ollama_list_timeout_seconds,
                elapsed_ms=round((time.time() - started_at) * 1000, 2),
                exc_info=True,
            )
            return []

        log_event(
            self.logger,
            20,
            "ollama.list_models.succeeded",
            "Ollama model list request completed",
            module_name="ollama",
            trace_id=get_trace_id(),
            base_url=self.base_url,
            timeout_seconds=config.ollama_list_timeout_seconds,
            elapsed_ms=round((time.time() - started_at) * 1000, 2),
            status_code=response.status_code,
            model_count=len(payload.get("models", [])),
        )

        models: list[dict[str, Any]] = []
        for item in payload.get("models", []):
            models.append(
                {
                    "name": item.get("name", ""),
                    "size": item.get("size", 0),
                    "modified_at": item.get("modified_at", ""),
                    "digest": item.get("digest", ""),
                }
            )
        return models

    def chat(self, *, model_name: str, messages: list[dict[str, str]]) -> str:
        started_at = time.time()
        timeout = self._chat_timeout(model_name=model_name)
        request_payload = {"model": model_name, "messages": messages, "stream": False}
        try:
            tier = self._resolve_timeout_tier(model_name)
            log_event(
                self.logger,
                20,
                "ollama.chat.request",
                "Issuing Ollama chat request",
                module_name="ollama",
                trace_id=get_trace_id(),
                base_url=self.base_url,
                model_name=model_name,
                timeout_seconds=tier,
                message_count=len(messages),
                request_payload=request_payload,
            )
            with httpx.Client(timeout=timeout) as client:
                response = client.post(f"{self.base_url}/api/chat", json=request_payload)
                response.raise_for_status()
                payload = response.json()
            log_event(
                self.logger,
                20,
                "ollama.chat.response",
                "Ollama chat request completed",
                module_name="ollama",
                trace_id=get_trace_id(),
                base_url=self.base_url,
                model_name=model_name,
                elapsed_ms=round((time.time() - started_at) * 1000, 2),
                status_code=response.status_code,
                response_chars=len(payload.get("message", {}).get("content", "")),
            )
        except Exception:
            tier = self._resolve_timeout_tier(model_name)
            log_event(
                self.logger,
                40,
                "ollama.chat.failed",
                "Ollama chat request failed",
                module_name="ollama",
                trace_id=get_trace_id(),
                base_url=self.base_url,
                model_name=model_name,
                timeout_seconds=tier,
                elapsed_ms=round((time.time() - started_at) * 1000, 2),
                message_count=len(messages),
                request_payload=request_payload,
                exc_info=True,
            )
            raise
        return payload.get("message", {}).get("content", "").strip()

    def get_timeout_info(self, model_name: str) -> dict[str, Any]:
        """Return the resolved timeout tier info for a given model name."""
        param_size = self._extract_param_size(model_name)
        tier = self._resolve_timeout_tier(model_name)
        return {
            "model_name": model_name,
            "param_size": param_size,
            "timeout": tier,
            "user_override": config.user_timeout_override_seconds is not None,
        }

    def pull_model(self, model_name: str) -> dict[str, Any]:
        """Pull (download) a model from the Ollama library. Returns summary dict."""
        started_at = time.time()
        self.logger.info("ollama.pull.started model=%s", model_name)
        try:
            with httpx.Client(timeout=httpx.Timeout(connect=30, read=1800, write=60, pool=30)) as client:
                response = client.post(
                    f"{self.base_url}/api/pull",
                    json={"name": model_name, "stream": False},
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError:
            self.logger.error(
                "ollama.pull.failed model=%s err=%s",
                model_name,
                traceback.format_exc(),
            )
            return {
                "model": model_name,
                "status": "failed",
                "error": traceback.format_exc(),
            }
        elapsed = round(time.time() - started_at, 1)
        self.logger.info("ollama.pull.completed model=%s elapsed=%s", model_name, elapsed)
        return {
            "model": model_name,
            "status": payload.get("status", "completed"),
            "elapsed_seconds": elapsed,
            "raw": payload,
        }

    def pull_model_stream(self, model_name: str) -> Iterator[str]:
        """Pull a model and yield NDJSON status lines for real-time progress."""
        self.logger.info("ollama.pull_stream.started model=%s", model_name)
        try:
            with httpx.Client(timeout=httpx.Timeout(connect=30, read=1800, write=60, pool=30)) as client:
                with client.stream(
                    "POST",
                    f"{self.base_url}/api/pull",
                    json={"name": model_name, "stream": True},
                ) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if line:
                            yield line + "\n"
        except httpx.HTTPError:
            yield json.dumps({"status": "error", "error": traceback.format_exc()}) + "\n"

    def iter_pull_progress(self, model_name: str) -> Iterator[dict[str, Any]]:
        """Yield parsed Ollama pull progress events from the NDJSON stream."""
        for line in self.pull_model_stream(model_name):
            payload_line = line.strip()
            if not payload_line:
                continue
            try:
                payload = json.loads(payload_line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                yield payload
