"""
llmfit CLI Adapter — wraps `llmfit` as a subprocess for hardware detection
and model recommendation within the FastAPI service.

Graceful fallback to existing resource_monitor.py if llmfit is not installed.
"""
from __future__ import annotations

import json as _json
import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger("app.llmfit")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
LLMFIT_BINARY = os.environ.get("LLMFIT_BINARY", "llmfit")
LLMFIT_CACHE_TTL = int(os.environ.get("LLMFIT_CACHE_TTL", "300"))
LLMFIT_TIMEOUT = int(os.environ.get("LLMFIT_TIMEOUT", "30"))
LLMFIT_DOCKER_MODE = LLMFIT_BINARY.lower() == "docker"
LLMFIT_DOCKER_IMAGE = os.environ.get(
    "LLMFIT_DOCKER_IMAGE", "ghcr.io/alexsjones/llmfit",
)


class LlmfitNotFoundError(RuntimeError):
    """Raised when llmfit binary is not found on the system."""


class LlmfitTimeoutError(RuntimeError):
    """Raised when the llmfit subprocess times out."""


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class GpuInfo:
    name: str
    vram_gb: float
    backend: str = "unknown"


@dataclass
class CpuInfo:
    cores: int
    model: str = "unknown"
    arch: str = "unknown"


@dataclass
class RamInfo:
    total_gb: float
    available_gb: float = 0.0


@dataclass
class SystemProfile:
    cpu: CpuInfo
    ram: RamInfo
    gpus: list[GpuInfo] = field(default_factory=list)
    os: str = "unknown"


@dataclass
class RecommendationScore:
    total: float
    quality: float
    speed: float
    fit: float
    context: float


@dataclass
class ModelRecommendation:
    model_name: str
    provider: str
    param_size: str
    score: RecommendationScore
    fit_level: str          # perfect / good / marginal / too_tight
    estimated_tps: float
    quantization: str
    memory_required_gb: float
    run_mode: str           # GPU / MoE / CPU+GPU / CPU
    use_case: str
    max_context: int
    is_moe: bool = False
    available: bool = False


# ---------------------------------------------------------------------------
# In-memory cache
# ---------------------------------------------------------------------------
_cache: dict[str, tuple[float, Any]] = {}


def _cache_get(key: str) -> Any | None:
    ts, val = _cache.get(key, (0, None))
    if time.time() - ts < LLMFIT_CACHE_TTL:
        return val
    return None


def _cache_set(key: str, val: Any) -> None:
    _cache[key] = (time.time(), val)


def _cache_clear() -> None:
    _cache.clear()


# ---------------------------------------------------------------------------
# LlmfitService
# ---------------------------------------------------------------------------

class LlmfitService:
    """
    Wraps `llmfit` CLI for hardware detection and model recommendation.

    Attributes:
        available: bool — whether the llmfit binary is usable
    """

    def __init__(self) -> None:
        self.available = self._check_available()

    # ------------------------------------------------------------------
    # Public API — System Info
    # ------------------------------------------------------------------
    def get_system_profile(self) -> SystemProfile:
        """Return full system hardware profile from llmfit (cached 5 min)."""
        cache_key = "system_profile"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        if not self.available:
            return self._system_from_psutil()

        try:
            raw = self._run_json(["system", "--json"])
        except (LlmfitNotFoundError, LlmfitTimeoutError, Exception):
            logger.warning("llmfit system failed, falling back to psutil")
            return self._system_from_psutil()

        profile = self._parse_system(raw)
        _cache_set(cache_key, profile)
        return profile

    # ------------------------------------------------------------------
    # Public API — Model Recommendations
    # ------------------------------------------------------------------
    def get_recommendations(
        self,
        limit: int = 10,
        use_case: str = "general",
        min_fit: str = "marginal",
        sort: str = "score",
        include_too_tight: bool = False,
    ) -> list[ModelRecommendation]:
        """
        Get scored model recommendations from llmfit.

        Args:
            limit: max models to return (default 10)
            use_case: general|coding|reasoning|chat|multimodal|embedding
            min_fit: perfect|good|marginal — minimum fit level
            sort: score|tps|params|mem|ctx|date
            include_too_tight: whether to include models that won't fit
        """
        cache_key = f"recs:{limit}:{use_case}:{min_fit}:{sort}:{include_too_tight}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        if not self.available:
            return self._recommendations_from_catalog(limit, use_case)

        args = [
            "recommend", "--json",
            "--limit", str(limit),
            "--use-case", use_case,
        ]
        if min_fit != "marginal":
            args.extend(["--min-fit", min_fit])

        try:
            raw = self._run_json(args)
        except (LlmfitNotFoundError, LlmfitTimeoutError, Exception):
            logger.warning("llmfit recommend failed, falling back to catalog")
            return self._recommendations_from_catalog(limit, use_case)

        results = self._parse_recommendations(raw)
        # Filter out None entries from malformed data
        results = [r for r in results if r is not None]
        if not include_too_tight:
            results = [r for r in results if r.fit_level != "too_tight"]
        if sort == "tps":
            results.sort(key=lambda r: -r.estimated_tps)
        elif sort == "score":
            results.sort(key=lambda r: -r.score.total)

        # Ensure limit is respected even if llmfit returns more
        results = results[:limit]

        _cache_set(cache_key, results)
        return results

    def get_model_info(self, model_name: str) -> ModelRecommendation | None:
        """Get detailed info for a specific model."""
        cache_key = f"model_info:{model_name}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        if not self.available:
            return None

        try:
            raw = self._run_json(["info", model_name])
        except Exception:
            return None

        rec = self._parse_single_recommendation(raw)
        _cache_set(cache_key, rec)
        return rec

    def refresh_cache(self) -> None:
        """Clear the in-memory cache to force fresh data."""
        _cache_clear()
        logger.info("llmfit cache cleared")

    # ------------------------------------------------------------------
    # Internal — subprocess
    # ------------------------------------------------------------------
    def _check_available(self) -> bool:
        if LLMFIT_DOCKER_MODE:
            return self._check_docker_available()
        if not shutil.which(LLMFIT_BINARY):
            logger.info("llmfit binary '%s' not found on PATH", LLMFIT_BINARY)
            return False
        try:
            result = subprocess.run(
                [LLMFIT_BINARY, "--version"],
                capture_output=True, text=True, timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _check_docker_available(self) -> bool:
        if not shutil.which("docker"):
            logger.info("docker not found on PATH")
            return False
        try:
            result = subprocess.run(
                ["docker", "run", "--rm", LLMFIT_DOCKER_IMAGE, "--version"],
                capture_output=True, text=True, timeout=30,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _run_json(self, args: list[str]) -> dict[str, Any]:
        """Execute llmfit and return parsed JSON."""
        if LLMFIT_DOCKER_MODE:
            cmd = ["docker", "run", "--rm", LLMFIT_DOCKER_IMAGE] + args
        else:
            cmd = [LLMFIT_BINARY] + args

        started = time.time()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=LLMFIT_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            elapsed = round(time.time() - started, 1)
            logger.error("llmfit subprocess timed out after %ss", elapsed)
            raise LlmfitTimeoutError(
                f"llmfit timed out after {LLMFIT_TIMEOUT}s") from None
        except FileNotFoundError:
            raise LlmfitNotFoundError(
                f"llmfit binary not found: {cmd[0]}") from None

        elapsed = round(time.time() - started, 1)
        logger.debug("llmfit completed in %ss, args=%s", elapsed, args)

        if result.returncode != 0:
            logger.error("llmfit exited %d: %s",
                         result.returncode, result.stderr[:500])
            raise RuntimeError(
                f"llmfit error (code {result.returncode}): {result.stderr[:200]}")

        try:
            return _json.loads(result.stdout)
        except _json.JSONDecodeError:
            logger.error("llmfit returned invalid JSON: %s",
                         result.stdout[:500])
            raise RuntimeError("llmfit returned invalid JSON output") from None

    # ------------------------------------------------------------------
    # Internal — parsing
    # ------------------------------------------------------------------
    def _parse_system(self, raw: dict) -> SystemProfile:
        cpu_raw = raw.get("cpu", {})
        ram_raw = raw.get("ram", raw.get("memory", {}))
        gpu_list = raw.get("gpu", raw.get("gpus", []))

        cpu = CpuInfo(
            cores=cpu_raw.get("cores", cpu_raw.get("physical_cores", 0)),
            model=cpu_raw.get("model", cpu_raw.get("brand", "unknown")),
            arch=cpu_raw.get("arch", cpu_raw.get("architecture", "unknown")),
        )

        ram = RamInfo(
            total_gb=float(ram_raw.get("total_gb", ram_raw.get("total", 0))),
            available_gb=float(ram_raw.get(
                "available_gb", ram_raw.get("available", 0))),
        )

        gpus = []
        for g in (gpu_list if isinstance(gpu_list, list) else [gpu_list]):
            gpus.append(GpuInfo(
                name=g.get("name", g.get("model", "unknown GPU")),
                vram_gb=float(g.get("vram_gb", g.get(
                    "memory_gb", g.get("memory", 0)))),
                backend=g.get("backend", "unknown"),
            ))

        return SystemProfile(
            cpu=cpu, ram=ram, gpus=gpus,
            os=raw.get("os", raw.get("platform", "unknown")),
        )

    def _parse_recommendations(self, raw: dict) -> list[ModelRecommendation]:
        models = raw.get("models", raw.get("recommendations", []))
        if not isinstance(models, list):
            models = []
        return [self._parse_single_recommendation(m) for m in models]

    def _parse_single_recommendation(self, raw: dict) -> ModelRecommendation | None:
        if not isinstance(raw, dict):
            return None
        try:
            scores = raw.get("scores", raw.get("score", {}))
            if isinstance(scores, (int, float)):
                scores = {"total": scores}

            return ModelRecommendation(
                model_name=raw.get("name", raw.get("model_name", "unknown")),
                provider=raw.get("provider", raw.get("author", "unknown")),
                param_size=raw.get("params", raw.get("param_size", "unknown")),
                score=RecommendationScore(
                    total=float(scores.get("total", scores.get("overall", 0))),
                    quality=float(scores.get("quality", 0)),
                    speed=float(scores.get("speed", 0)),
                    fit=float(scores.get("fit", 0)),
                    context=float(scores.get("context", 0)),
                ),
                fit_level=raw.get("fit", raw.get("fit_level", "unknown")),
                estimated_tps=float(
                    raw.get("tps", raw.get("estimated_tps", 0))),
                quantization=raw.get(
                    "quantization", raw.get("quant", "unknown")),
                memory_required_gb=float(
                    raw.get("memory_required_gb", raw.get(
                        "memory_gb", raw.get("vram_gb", 0)))
                ),
                run_mode=raw.get("run_mode", raw.get("mode", "CPU")),
                use_case=raw.get("use_case", raw.get("category", "general")),
                max_context=int(raw.get("max_context", raw.get("context", 0))),
                is_moe=bool(raw.get("is_moe", raw.get("moe", False))),
                available=bool(
                    raw.get("available", raw.get("installed", False))),
            )
        except (KeyError, ValueError, TypeError):
            logger.debug("Failed to parse recommendation: %s", raw)
            return None

    # ------------------------------------------------------------------
    # Fallback: use existing resource_monitor.py + curated catalog
    # ------------------------------------------------------------------
    def _system_from_psutil(self) -> SystemProfile:
        from app.services.resource_monitor import get_full_resource_snapshot
        snap = get_full_resource_snapshot()

        cpu = snap.get("cpu", {})
        mem = snap.get("memory", {})
        gpu_data = snap.get("gpu", {})

        gpus = []
        if gpu_data.get("available"):
            for g in gpu_data.get("gpus", []):
                gpus.append(GpuInfo(
                    name=g.get("name", "GPU"),
                    vram_gb=g.get("memory_free_mb", 0) / 1024,
                    backend="CUDA" if "nvidia" in g.get(
                        "name", "").lower() else "unknown",
                ))

        return SystemProfile(
            cpu=CpuInfo(
                cores=cpu.get("cpu_cores_logical", 0),
                model="unknown (psutil)",
                arch="unknown",
            ),
            ram=RamInfo(
                total_gb=mem.get("total_gb", 0) or 0,
                available_gb=mem.get("available_gb", 0) or 0,
            ),
            gpus=gpus,
            os="unknown",
        )

    def _recommendations_from_catalog(
        self, limit: int, use_case: str,
    ) -> list[ModelRecommendation]:
        from app.services.resource_monitor import CURATED_CATALOG
        results = []
        for req in CURATED_CATALOG[:limit]:
            results.append(ModelRecommendation(
                model_name=req.ollama_name,
                provider="Curated",
                param_size=req.param_size,
                score=RecommendationScore(
                    total=70, quality=70, speed=70, fit=70, context=70),
                fit_level="good",
                estimated_tps=20,
                quantization="Q4_K_M",
                memory_required_gb=req.approx_size_gb,
                run_mode="CPU",
                use_case=use_case,
                max_context=8192,
            ))
        return results
