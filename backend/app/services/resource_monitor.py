"""
Hardware resource monitor for edge-model scenarios.
Monitors CPU, RAM, and GPU (NVIDIA) to determine if local hardware
can support a given LLM model size. Also includes a curated catalog of
real Ollama library models for auto-download on first deployment.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger("app.resource_monitor")


# ---------------------------------------------------------------------------
# Model resource requirement registry
# ---------------------------------------------------------------------------
# Each entry maps a real Ollama library model to its hardware requirements.
# `ollama_name` = pullable name (e.g. "qwen3:1.8b")
# `param_size`  = canonical size label (e.g. "1.8B", "4B")
# `ram_gb`      = recommended system RAM
# `vram_gb`     = minimum GPU VRAM (None if CPU-only is acceptable)
# `cpu_cores`   = recommended CPU core count
# `approx_size_gb` = approximate download size on disk
# ---------------------------------------------------------------------------
@dataclass
class ModelRequirement:
    # actual name for `ollama pull` (e.g. "qwen3:1.8b")
    ollama_name: str
    param_size: str          # canonical size label (e.g. "12B", "7B", "1.8B")
    display_name: str        # human-friendly name
    ram_gb: float            # recommended system RAM
    vram_gb: float | None    # recommended GPU VRAM (None = CPU only)
    cpu_cores: int           # recommended CPU cores
    approx_size_gb: float    # approximate download size
    description: str         # brief scenario description
    tags: list[str] = field(default_factory=list)  # e.g. ["reasoning", "code"]
    # e.g. "Qwen/Qwen3-1.8B-GGUF" for ModelScope fallback
    modelscope_name: str | None = None


# ---------------------------------------------------------------------------
# Curated catalog — top rated edge models from https://ollama.com/library
# Ordered by capability (largest to smallest). The auto-downloader picks
# the largest feasible model for the detected hardware.
# ---------------------------------------------------------------------------
CURATED_CATALOG: list[ModelRequirement] = [
    ModelRequirement(
        ollama_name="qwen3:8b",
        param_size="8B",
        display_name="Qwen3 8B",
        ram_gb=10, vram_gb=8, cpu_cores=4,
        approx_size_gb=5.2,
        description="Strong general-purpose model. Chat, translation, summarization, light code.",
        tags=["chat", "multilingual", "reasoning"],
        modelscope_name="Qwen/Qwen3-8B-GGUF",
    ),
    ModelRequirement(
        ollama_name="gemma3:4b",
        param_size="4B",
        display_name="Gemma 3 4B",
        ram_gb=5, vram_gb=4, cpu_cores=4,
        approx_size_gb=2.6,
        description="Google's efficient mid-tier model. Great for chat, Q&A, structured output.",
        tags=["chat", "instruction-following", "multilingual"],
        modelscope_name="LLM-Research/gemma-3-4b-it-GGUF",
    ),
    ModelRequirement(
        ollama_name="phi4-mini:3.8b",
        param_size="3.8B",
        display_name="Phi-4 Mini 3.8B",
        ram_gb=5, vram_gb=4, cpu_cores=4,
        approx_size_gb=2.3,
        description="Microsoft's efficient reasoning model. Excellent at math and logic.",
        tags=["reasoning", "math", "code"],
        modelscope_name="LLM-Research/Phi-4-mini-instruct-GGUF",
    ),
    ModelRequirement(
        ollama_name="llama3.2:3b",
        param_size="3B",
        display_name="Llama 3.2 3B",
        ram_gb=4, vram_gb=3, cpu_cores=2,
        approx_size_gb=2.0,
        description="Meta's popular lightweight model. Solid all-rounder for chat and text tasks.",
        tags=["chat", "instruction-following"],
        modelscope_name="LLM-Research/Llama-3.2-3B-Instruct-GGUF",
    ),
    ModelRequirement(
        ollama_name="deepseek-r1:1.5b",
        param_size="1.5B",
        display_name="DeepSeek-R1 1.5B",
        ram_gb=3, vram_gb=2, cpu_cores=2,
        approx_size_gb=1.1,
        description="Reasoning-focused lightweight model. Chain-of-thought for complex questions.",
        tags=["reasoning", "chain-of-thought"],
        modelscope_name="deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B-GGUF",
    ),
    ModelRequirement(
        ollama_name="qwen3:1.8b",
        param_size="1.8B",
        display_name="Qwen3 1.8B",
        ram_gb=2.5, vram_gb=2, cpu_cores=2,
        approx_size_gb=1.3,
        description="Ultra-lightweight multilingual model. Fast response, basic Q&A, edge-friendly.",
        tags=["chat", "multilingual", "edge"],
        modelscope_name="Qwen/Qwen3-1.8B-GGUF",
    ),
    ModelRequirement(
        ollama_name="qwen3:0.6b",
        param_size="0.6B",
        display_name="Qwen3 0.6B",
        ram_gb=1.5, vram_gb=1, cpu_cores=2,
        approx_size_gb=0.5,
        description="Smallest viable model. Embedded devices, simple classification, latency-critical.",
        tags=["edge", "embedded", "fast"],
        modelscope_name="Qwen/Qwen3-0.6B-GGUF",
    ),
]

# Alias for backward compatibility — MODEL_REGISTRY is the curated catalog
MODEL_REGISTRY = CURATED_CATALOG
# ---------------------------------------------------------------------------


def _get_cpu_info() -> dict[str, Any]:
    try:
        import psutil
    except ImportError:
        return {"cpu_percent": None, "cpu_cores_physical": None, "cpu_cores_logical": None, "error": "psutil not installed"}
    return {
        "cpu_percent": round(psutil.cpu_percent(interval=0.1), 1),
        "cpu_cores_physical": psutil.cpu_count(logical=False),
        "cpu_cores_logical": psutil.cpu_count(logical=True),
    }


def _get_memory_info() -> dict[str, Any]:
    try:
        import psutil
    except ImportError:
        return {"total_gb": None, "available_gb": None, "used_gb": None, "percent": None, "error": "psutil not installed"}
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        "total_gb": round(mem.total / (1024**3), 1),
        "available_gb": round(mem.available / (1024**3), 1),
        "used_gb": round(mem.used / (1024**3), 1),
        "percent": mem.percent,
        "swap_total_gb": round(swap.total / (1024**3), 1),
        "swap_used_gb": round(swap.used / (1024**3), 1),
    }


def _get_gpu_info() -> dict[str, Any]:
    """Query NVIDIA GPU stats via nvidia-smi."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return {"available": False, "error": result.stderr.strip()}
        gpus = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 5:
                gpus.append({
                    "name": parts[0],
                    "memory_total_mb": float(parts[1]),
                    "memory_used_mb": float(parts[2]),
                    "memory_free_mb": float(parts[3]),
                    "utilization_percent": float(parts[4]),
                })
        return {"available": len(gpus) > 0, "gpus": gpus}
    except FileNotFoundError:
        return {"available": False, "error": "nvidia-smi not found (no NVIDIA GPU / driver)"}
    except Exception as exc:
        return {"available": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_full_resource_snapshot() -> dict[str, Any]:
    """Return a comprehensive snapshot of system resources."""
    return {
        "cpu": _get_cpu_info(),
        "memory": _get_memory_info(),
        "gpu": _get_gpu_info(),
    }


def get_model_requirement(identifier: str) -> ModelRequirement | None:
    """Look up the resource requirement by param_size or ollama_name."""
    for req in MODEL_REGISTRY:
        if req.param_size == identifier or req.ollama_name == identifier:
            return req
    return None


def extract_param_size(model_name: str) -> str:
    """Extract parameter-size label from a model name like 'qwen3:8b' -> '8B'."""
    name_lower = model_name.lower()
    import re
    match = re.search(r'[:|\-_]?(\d+\.?\d*)[bB]', name_lower)
    if match:
        size = match.group(1)
        return f"{size}B"
    # Fallback: search catalog by ollama_name or display_name
    for req in MODEL_REGISTRY:
        if req.ollama_name in name_lower or req.display_name.lower().replace(" ", "") in name_lower:
            return req.param_size
    return "unknown"


def check_model_feasibility(model_name: str) -> dict[str, Any]:
    """
    Check whether the current system can run the specified model.
    Tries ollama_name match first, then param_size extraction.
    Returns a dict with:
      - feasible: bool
      - warnings: list[str]
      - current_resources: dict
      - model_requirement: dict | None
      - recommendation: dict | None (if infeasible, suggest downgrade)
    """
    snapshot = get_full_resource_snapshot()

    # Try direct ollama_name match first
    requirement = get_model_requirement(model_name)
    if requirement is None:
        param_size = extract_param_size(model_name)
        requirement = get_model_requirement(param_size)

    if requirement is None:
        return {
            "feasible": True,
            "warnings": [],
            "current_resources": snapshot,
            "model_requirement": None,
            "recommendation": None,
            "param_size": extract_param_size(model_name),
        }

    param_size = requirement.param_size
    warnings: list[str] = []

    # --- RAM check ---
    mem = snapshot["memory"]
    if mem.get("available_gb") is not None and mem["available_gb"] < requirement.ram_gb:
        warnings.append(
            f"Insufficient RAM: {mem['available_gb']} GB available, "
            f"{requirement.ram_gb} GB required for {requirement.display_name}"
        )

    # --- GPU VRAM check ---
    gpu = snapshot["gpu"]
    if requirement.vram_gb is not None and gpu.get("available"):
        vram_available = 0.0
        for g in gpu.get("gpus", []):
            vram_available += g["memory_free_mb"] / 1024.0
        if vram_available < requirement.vram_gb:
            warnings.append(
                f"Insufficient VRAM: {vram_available:.1f} GB free, "
                f"{requirement.vram_gb} GB required for {requirement.display_name}"
            )
    elif requirement.vram_gb is not None and not gpu.get("available"):
        warnings.append(
            f"No dedicated GPU detected. {requirement.display_name} may run very slowly on CPU."
        )

    # --- CPU core check (soft) ---
    cpu = snapshot["cpu"]
    if cpu.get("cpu_cores_logical") is not None and cpu["cpu_cores_logical"] < requirement.cpu_cores:
        warnings.append(
            f"Low CPU core count: {cpu['cpu_cores_logical']} logical cores available, "
            f"{requirement.cpu_cores} recommended for {requirement.display_name}"
        )

    # For strict infeasibility: RAM or VRAM hard-limit warnings make it infeasible
    hard_warnings = [
        w for w in warnings if "Insufficient RAM" in w or "Insufficient VRAM" in w]
    feasible = len(hard_warnings) == 0

    recommendation = None
    if not feasible:
        recommendation = _recommend_downgrade(requirement, snapshot)

    return {
        "feasible": feasible,
        "warnings": warnings,
        "current_resources": snapshot,
        "model_requirement": {
            "ollama_name": requirement.ollama_name,
            "param_size": requirement.param_size,
            "display_name": requirement.display_name,
            "ram_gb": requirement.ram_gb,
            "vram_gb": requirement.vram_gb,
            "cpu_cores": requirement.cpu_cores,
            "approx_size_gb": requirement.approx_size_gb,
            "description": requirement.description,
            "modelscope_name": requirement.modelscope_name,
        },
        "recommendation": recommendation,
        "param_size": param_size,
    }


def _recommend_downgrade(
    current_req: ModelRequirement, snapshot: dict[str, Any]
) -> dict[str, Any] | None:
    """Recommend a smaller model that fits current hardware."""
    mem = snapshot["memory"]
    available_ram = mem.get("available_gb", 0) or 0
    gpu = snapshot["gpu"]
    available_vram = 0.0
    if gpu.get("available"):
        for g in gpu.get("gpus", []):
            available_vram += g["memory_free_mb"] / 1024.0

    # Find models smaller than current one that fit
    current_idx = next(
        (i for i, r in enumerate(MODEL_REGISTRY)
         if r.param_size == current_req.param_size),
        len(MODEL_REGISTRY),
    )
    candidates = []
    for req in MODEL_REGISTRY[current_idx + 1:]:
        ram_ok = available_ram >= req.ram_gb * 0.8  # 80% threshold
        vram_ok = req.vram_gb is None or available_vram >= req.vram_gb * 0.8
        if ram_ok and vram_ok:
            candidates.append(req)

    if not candidates:
        # Fallback: suggest the smallest model in the registry
        candidates = [MODEL_REGISTRY[-1]]

    best = candidates[0]
    return {
        "suggested_model": best.param_size,
        "suggested_display_name": best.display_name,
        "suggested_ollama_name": best.ollama_name,
        "suggested_modelscope_name": best.modelscope_name,
        "ram_required_gb": best.ram_gb,
        "vram_required_gb": best.vram_gb,
        "approx_size_gb": best.approx_size_gb,
        "description": best.description,
        "reason": (
            f"Your device has insufficient resources for {current_req.display_name} ({current_req.param_size}). "
            f"Switch to {best.display_name} ({best.param_size}) which only requires "
            f"{best.ram_gb} GB RAM"
            + (f" / {best.vram_gb} GB VRAM" if best.vram_gb else " (CPU-friendly)")
            + f". {best.description}."
        ),
    }


def list_recommended_models() -> list[dict[str, Any]]:
    """Return all models ranked by suitability for current hardware."""
    snapshot = get_full_resource_snapshot()
    results = []
    for req in MODEL_REGISTRY:
        feasibility = check_model_feasibility(req.ollama_name)
        results.append({
            "ollama_name": req.ollama_name,
            "param_size": req.param_size,
            "display_name": req.display_name,
            "ram_gb": req.ram_gb,
            "vram_gb": req.vram_gb,
            "cpu_cores": req.cpu_cores,
            "approx_size_gb": req.approx_size_gb,
            "description": req.description,
            "tags": req.tags,
            "modelscope_name": req.modelscope_name,
            "feasible": feasibility["feasible"],
            "warnings": feasibility["warnings"],
        })
    return results


def select_best_model_for_hardware() -> ModelRequirement | None:
    """
    Pick the most capable model from the catalog that fits current hardware.
    Returns None if even the smallest model won't fit.
    """
    snapshot = get_full_resource_snapshot()
    mem = snapshot["memory"]
    available_ram = mem.get("available_gb", 0) or 0
    gpu = snapshot["gpu"]
    available_vram = 0.0
    if gpu.get("available"):
        for g in gpu.get("gpus", []):
            available_vram += g["memory_free_mb"] / 1024.0

    best: ModelRequirement | None = None
    for req in MODEL_REGISTRY:
        ram_ok = available_ram >= req.ram_gb * 0.8
        vram_ok = req.vram_gb is None or available_vram >= req.vram_gb * 0.8
        if ram_ok and vram_ok:
            best = req
            break  # Catalog is ordered largest→smallest, first fit is best
    return best


def find_catalog_entry(identifier: str) -> ModelRequirement | None:
    """Find a catalog entry by ollama_name or param_size."""
    for req in MODEL_REGISTRY:
        if req.ollama_name == identifier or req.param_size == identifier:
            return req
    return None


def build_pull_fallbacks(model_name: str, prefer_modelscope: bool = False) -> list[str]:
    """
    Build an ordered list of pull names to try: Ollama registry first,
    then ModelScope if the catalog has a modelscope_name entry.
    When prefer_modelscope=True, ModelScope is tried first.
    """
    pull_names: list[str] = []
    entry = find_catalog_entry(model_name)

    if entry and entry.modelscope_name:
        ms_name = f"modelscope.cn/{entry.modelscope_name}"
        if prefer_modelscope:
            pull_names = [ms_name, model_name]
        else:
            pull_names = [model_name, ms_name]
    else:
        pull_names = [model_name]

    return pull_names
