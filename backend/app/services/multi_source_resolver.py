"""
MultiSourceResolver — resolves download URLs in priority order:
Ollama registry → HuggingFace → ModelScope.
"""
from __future__ import annotations

from app.core.logging import get_logger
from app.schemas.download import MultiSourceEntry, MultiSourcePlan

logger = get_logger("app.download.resolver")

# Model name → ModelScope GGUF path mapping
_MODELSCOPE_MAP: dict[str, str] = {
    "qwen3:8b": "Qwen/Qwen3-8B-GGUF",
    "gemma3:4b": "LLM-Research/gemma-3-4b-it-GGUF",
    "phi4-mini:3.8b": "LLM-Research/Phi-4-mini-instruct-GGUF",
    "llama3.2:3b": "LLM-Research/Llama-3.2-3B-Instruct-GGUF",
    "qwen3:1.8b": "Qwen/Qwen3-1.8B-GGUF",
    "qwen3:0.6b": "Qwen/Qwen3-0.6B-GGUF",
}

_MODELSCOPE_BASE = "https://modelscope.cn/models/{repo}/resolve/master"
_HF_BASE = "https://huggingface.co/{repo}/resolve/main"


class MultiSourceResolver:
    """
    Resolve download URL chain for a model.
    Priority: Ollama pull (via local API) > HuggingFace GGUF > ModelScope GGUF
    """

    def resolve(self, model_name: str, prefer: str = "auto") -> MultiSourcePlan:
        sources: list[MultiSourceEntry] = []

        if prefer in ("auto", "ollama"):
            sources.append(MultiSourceEntry(
                name="ollama",
                url=f"ollama://pull/{model_name}",
                priority=0,
                timeout_seconds=300,
            ))

        if prefer in ("auto", "huggingface"):
            hf_url = self._build_hf_url(model_name)
            if hf_url:
                sources.append(MultiSourceEntry(
                    name="huggingface",
                    url=hf_url,
                    priority=1,
                    timeout_seconds=600,
                ))

        if prefer in ("auto", "modelscope"):
            ms_url = self._build_modelscope_url(model_name)
            if ms_url:
                sources.append(MultiSourceEntry(
                    name="modelscope",
                    url=ms_url,
                    priority=2,
                    timeout_seconds=600,
                ))

        # Sort by priority
        sources.sort(key=lambda s: s.priority)

        return MultiSourcePlan(model_name=model_name, sources=sources)

    def _build_modelscope_url(self, model_name: str) -> str:
        repo = _MODELSCOPE_MAP.get(model_name)
        if repo:
            return _MODELSCOPE_BASE.format(repo=repo)
        # Generic fallback: try treating model_name as repo/model
        clean = model_name.replace(":", "-")
        return _MODELSCOPE_BASE.format(repo=clean)

    def _build_hf_url(self, model_name: str) -> str:
        """Map model name to HuggingFace GGUF repo."""
        hf_map: dict[str, str] = {
            "qwen3:8b": "Qwen/Qwen3-8B-GGUF",
            "llama3.2:3b": "unsloth/Llama-3.2-3B-Instruct-GGUF",
            "qwen3:1.8b": "Qwen/Qwen3-1.8B-GGUF",
        }
        repo = hf_map.get(model_name)
        if repo:
            return _HF_BASE.format(repo=repo)
        clean = model_name.replace(":", "-")
        return _HF_BASE.format(repo=clean)
