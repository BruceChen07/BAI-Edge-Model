"""
Semantic memory extraction using the local LLM (smallest model).
Fully offline — uses the same Ollama instance already running.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from app.core.logging import get_logger

logger = get_logger("app.memory.extractor")

# Prompt template for memory extraction. Designed for smallest models (0.6B+).
EXTRACTION_PROMPT = """You are a memory extraction system. Extract key facts, preferences, and events from the conversation below.

Output ONLY valid JSON array. Each item must have:
- memory_type: one of "fact", "preference", "event", "rule"
- title: short title (max 20 words)
- content: the extracted fact (keep original wording, max 200 chars)
- importance: 0.0 to 1.0 (how important to remember)
- confidence: 0.0 to 1.0 (how certain you are)

Rules:
- Extract at most 5 items per conversation chunk
- Skip trivial greetings and small talk
- Prefer concrete statements over vague ones
- Do NOT invent information not present in the conversation

Conversation:
{conversation}

JSON output:
"""

EXTRACTION_PROMPT_CN = """你是记忆提取系统。从以下对话中提取关键事实、偏好和事件。

只输出合法的 JSON 数组。每个元素包含:
- memory_type: "fact"(事实) / "preference"(偏好) / "event"(事件) / "rule"(规则)
- title: 简短标题 (最多20字)
- content: 提取的事实 (保留原文措辞, 最多200字)
- importance: 0.0到1.0 (记忆重要性)
- confidence: 0.0到1.0 (置信度)

规则:
- 每次最多提取5条
- 忽略问候和闲聊
- 优先提取具体陈述
- 不要编造未在对话中出现的信息

对话:
{conversation}

JSON 输出:
"""


class SemanticExtractor:
    """
    Calls the local Ollama LLM (smallest model) to extract structured memories
    from conversation transcripts.

    Design constraints for edge devices:
      - Uses the smallest available model (default: qwen3:0.6b)
      - Single-turn call per extraction window (no multi-turn overhead)
      - Timeout: 30s (extraction is async, non-blocking to chat)
      - Fallback: returns empty list on any failure
    """

    def __init__(self, ollama_service: Any, model_name: str = "qwen3:0.6b") -> None:
        self.ollama = ollama_service
        self.model_name = model_name

    def extract(self, messages: list[dict[str, str]], language: str = "zh") -> list[dict[str, Any]]:
        """
        Extract memories from conversation messages.

        Args:
            messages: list of {"role": "...", "content": "..."}
            language: "zh" for Chinese prompt, otherwise English

        Returns:
            list of dicts with keys: memory_type, title, content, importance, confidence
        """
        if not messages:
            return []

        transcript = self._format_conversation(messages)
        if len(transcript) < 80:
            return []

        prompt = EXTRACTION_PROMPT_CN if language.startswith("zh") else EXTRACTION_PROMPT
        full_prompt = prompt.format(conversation=transcript)

        started = time.time()
        try:
            raw = self.ollama.chat(
                model_name=self.model_name,
                messages=[{"role": "user", "content": full_prompt}],
            )
        except Exception:
            logger.warning("SemanticExtractor LLM call failed", exc_info=True)
            return []

        elapsed = round(time.time() - started, 1)
        logger.debug(
            "SemanticExtractor completed in %ss, raw_len=%d",
            elapsed, len(raw),
        )

        return self._parse_response(raw)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _format_conversation(self, messages: list[dict[str, str]]) -> str:
        lines: list[str] = []
        for msg in messages[-40:]:  # last 40 messages max
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if not content.strip():
                continue
            prefix = "用户" if role == "user" else "助手" if role == "assistant" else role
            lines.append(f"[{prefix}] {content}")
        return "\n".join(lines)

    def _parse_response(self, raw: str) -> list[dict[str, Any]]:
        import json

        # Strip markdown code fences if present
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:]) if len(lines) > 1 else text
            if text.endswith("```"):
                text = text[:-3]

        try:
            items = json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON array within the response
            import re
            match = re.search(r"\[.*\]", text, re.DOTALL)
            if match:
                try:
                    items = json.loads(match.group())
                except json.JSONDecodeError:
                    logger.debug("Failed to parse extraction response: %s...", text[:200])
                    return []
            else:
                logger.debug("No JSON found in extraction response: %s...", text[:200])
                return []

        if not isinstance(items, list):
            return []

        results: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            results.append({
                "memory_type": str(item.get("memory_type", "fact")),
                "title": str(item.get("title", "Extracted"))[:100],
                "content": str(item.get("content", ""))[:500],
                "importance": float(item.get("importance", 0.5)),
                "confidence": float(item.get("confidence", 0.5)),
            })
        return results
