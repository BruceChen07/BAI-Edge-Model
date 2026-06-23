from __future__ import annotations

import json
import os
import time
import traceback
import urllib.request
from typing import Any

import httpx

import re

from app.core.config import TIMEOUT_TIERS, DEFAULT_TIMEOUT_TIER, config
from app.core.logging import get_logger, log_event
from app.core.request_context import get_trace_id


class OllamaService:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url or os.getenv(
            "OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        self.logger = get_logger("app.ollama")

    def _extract_param_size(self, model_name: str) -> str:
        """Extract parameter-size label from model name for timeout tier lookup."""
        name_lower = model_name.lower()
        match = re.search(r'[:|\-_]?(\d+\.?\d*)[bB]', name_lower)
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
        tier = TIMEOUT_TIERS.get(param_size, DEFAULT_TIMEOUT_TIER)
        return tier

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
            # #region debug-point A:list-models-request
            exec(
                "try:\n _p='.dbg/ollama-timeout.env'; _u='http://127.0.0.1:7777/event'; _s='ollama-timeout';\n with open(_p, encoding='utf-8') as _f: _c=_f.read(); _u=next((l.split('=',1)[1] for l in _c.split('\\n') if l.startswith('DEBUG_SERVER_URL=')),_u); _s=next((l.split('=',1)[1] for l in _c.split('\\n') if l.startswith('DEBUG_SESSION_ID=')),_s)\nexcept: pass\nurllib.request.urlopen(urllib.request.Request(_u, data=json.dumps({'sessionId':_s,'runId':'pre-fix','hypothesisId':'A','location':'ollama_service.py:list_models:request','msg':'[DEBUG] issuing ollama model list request','data':{'base_url':self.base_url,'timeout_seconds':config.ollama_list_timeout_seconds},'ts':int(time.time()*1000)}).encode(), headers={'Content-Type':'application/json'}), timeout=2).read()")
            # #endregion
            with httpx.Client(timeout=config.ollama_list_timeout_seconds) as client:
                response = client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                payload = response.json()
            # #region debug-point A:list-models-response
            exec(
                "try:\n _p='.dbg/ollama-timeout.env'; _u='http://127.0.0.1:7777/event'; _s='ollama-timeout';\n with open(_p, encoding='utf-8') as _f: _c=_f.read(); _u=next((l.split('=',1)[1] for l in _c.split('\\n') if l.startswith('DEBUG_SERVER_URL=')),_u); _s=next((l.split('=',1)[1] for l in _c.split('\\n') if l.startswith('DEBUG_SESSION_ID=')),_s)\nexcept: pass\nurllib.request.urlopen(urllib.request.Request(_u, data=json.dumps({'sessionId':_s,'runId':'pre-fix','hypothesisId':'A','location':'ollama_service.py:list_models:response','msg':'[DEBUG] ollama model list request completed','data':{'base_url':self.base_url,'status_code':response.status_code,'model_count':len(payload.get('models', []))},'ts':int(time.time()*1000)}).encode(), headers={'Content-Type':'application/json'}), timeout=2).read()")
            # #endregion
        except httpx.HTTPError:
            # #region debug-point A:list-models-error
            exec(
                "try:\n _p='.dbg/ollama-timeout.env'; _u='http://127.0.0.1:7777/event'; _s='ollama-timeout';\n with open(_p, encoding='utf-8') as _f: _c=_f.read(); _u=next((l.split('=',1)[1] for l in _c.split('\\n') if l.startswith('DEBUG_SERVER_URL=')),_u); _s=next((l.split('=',1)[1] for l in _c.split('\\n') if l.startswith('DEBUG_SESSION_ID=')),_s)\nexcept: pass\nurllib.request.urlopen(urllib.request.Request(_u, data=json.dumps({'sessionId':_s,'runId':'pre-fix','hypothesisId':'A','location':'ollama_service.py:list_models:error','msg':'[DEBUG] ollama model list request failed','data':{'base_url':self.base_url,'error_stack':traceback.format_exc()},'ts':int(time.time()*1000)}).encode(), headers={'Content-Type':'application/json'}), timeout=2).read()")
            # #endregion
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
        request_payload = {"model": model_name,
                           "messages": messages, "stream": False}
        try:
            # #region debug-point B:chat-request
            exec(
                "try:\n _p='.dbg/ollama-timeout.env'; _u='http://127.0.0.1:7777/event'; _s='ollama-timeout';\n with open(_p, encoding='utf-8') as _f: _c=_f.read(); _u=next((l.split('=',1)[1] for l in _c.split('\\n') if l.startswith('DEBUG_SERVER_URL=')),_u); _s=next((l.split('=',1)[1] for l in _c.split('\\n') if l.startswith('DEBUG_SESSION_ID=')),_s)\nexcept: pass\nurllib.request.urlopen(urllib.request.Request(_u, data=json.dumps({'sessionId':_s,'runId':'pre-fix','hypothesisId':'B','location':'ollama_service.py:chat:request','msg':'[DEBUG] issuing ollama chat request','data':{'base_url':self.base_url,'model_name':model_name,'timeout_seconds':config.ollama_read_timeout_seconds,'message_count':len(messages),'last_user_chars':len(messages[-1]['content']) if messages else 0},'ts':int(time.time()*1000)}).encode(), headers={'Content-Type':'application/json'}), timeout=2).read()")
            # #endregion
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
                response = client.post(
                    f"{self.base_url}/api/chat", json=request_payload)
                response.raise_for_status()
                payload = response.json()
            # #region debug-point B:chat-response
            exec(
                "try:\n _p='.dbg/ollama-timeout.env'; _u='http://127.0.0.1:7777/event'; _s='ollama-timeout';\n with open(_p, encoding='utf-8') as _f: _c=_f.read(); _u=next((l.split('=',1)[1] for l in _c.split('\\n') if l.startswith('DEBUG_SERVER_URL=')),_u); _s=next((l.split('=',1)[1] for l in _c.split('\\n') if l.startswith('DEBUG_SESSION_ID=')),_s)\nexcept: pass\nurllib.request.urlopen(urllib.request.Request(_u, data=json.dumps({'sessionId':_s,'runId':'pre-fix','hypothesisId':'B','location':'ollama_service.py:chat:response','msg':'[DEBUG] ollama chat request completed','data':{'base_url':self.base_url,'model_name':model_name,'status_code':response.status_code,'elapsed_ms':round((time.time()-started_at)*1000,2),'response_chars':len(payload.get('message', {}).get('content', ''))},'ts':int(time.time()*1000)}).encode(), headers={'Content-Type':'application/json'}), timeout=2).read()")
            # #endregion
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
                response_chars=len(payload.get(
                    "message", {}).get("content", "")),
            )
        except Exception:
            # #region debug-point D:chat-error
            exec(
                "try:\n _p='.dbg/ollama-timeout.env'; _u='http://127.0.0.1:7777/event'; _s='ollama-timeout';\n with open(_p, encoding='utf-8') as _f: _c=_f.read(); _u=next((l.split('=',1)[1] for l in _c.split('\\n') if l.startswith('DEBUG_SERVER_URL=')),_u); _s=next((l.split('=',1)[1] for l in _c.split('\\n') if l.startswith('DEBUG_SESSION_ID=')),_s)\nexcept: pass\nurllib.request.urlopen(urllib.request.Request(_u, data=json.dumps({'sessionId':_s,'runId':'pre-fix','hypothesisId':'D','location':'ollama_service.py:chat:error','msg':'[DEBUG] ollama chat request failed','data':{'base_url':self.base_url,'model_name':model_name,'timeout_seconds':config.ollama_read_timeout_seconds,'elapsed_ms':round((time.time()-started_at)*1000,2),'message_count':len(messages),'error_stack':traceback.format_exc()},'ts':int(time.time()*1000)}).encode(), headers={'Content-Type':'application/json'}), timeout=2).read()")
            # #endregion
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
            self.logger.error("ollama.pull.failed model=%s err=%s",
                              model_name, traceback.format_exc())
            return {"model": model_name, "status": "failed", "error": traceback.format_exc()}
        elapsed = round(time.time() - started_at, 1)
        self.logger.info(
            "ollama.pull.completed model=%s elapsed=%s", model_name, elapsed)
        return {
            "model": model_name,
            "status": payload.get("status", "completed"),
            "elapsed_seconds": elapsed,
            "raw": payload,
        }

    def pull_model_stream(self, model_name: str) -> Iterator[str]:
        """Pull a model and yield NDJSON status lines for real-time progress."""
        import json as _json
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
            yield _json.dumps({"status": "error", "error": traceback.format_exc()}) + "\n"
