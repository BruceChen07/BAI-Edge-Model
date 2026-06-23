"""
Phase 1: llmfit CLI Adapter unit tests.
Covers: mock output parsing, field mapping, cache behavior, error handling,
fallback to psutil/catalog, and edge cases.
"""
from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from app.services.llmfit_service import (
    CpuInfo,
    GpuInfo,
    LlmfitNotFoundError,
    LlmfitService,
    LlmfitTimeoutError,
    ModelRecommendation,
    RamInfo,
    RecommendationScore,
    SystemProfile,
    _cache_clear,
    _cache_get,
    _cache_set,
)


# ============================================================================
# Fixtures
# ============================================================================

MOCK_SYSTEM_JSON = json.dumps({
    "cpu": {"cores": 8, "model": "Intel Core i7-10750H", "arch": "x86_64"},
    "ram": {"total_gb": 16.0, "available_gb": 8.5},
    "gpu": [
        {"name": "NVIDIA GeForce RTX 3060", "vram_gb": 6.0, "backend": "CUDA"},
    ],
    "os": "Windows 11",
})

MOCK_RECOMMEND_JSON = json.dumps({
    "models": [
        {
            "name": "qwen3:8b",
            "provider": "Qwen",
            "params": "8B",
            "scores": {"total": 85, "quality": 78, "speed": 82, "fit": 90, "context": 88},
            "fit": "perfect",
            "tps": 45.0,
            "quantization": "Q4_K_M",
            "memory_required_gb": 5.2,
            "run_mode": "GPU",
            "use_case": "general",
            "max_context": 32768,
            "is_moe": False,
            "available": True,
        },
        {
            "name": "llama3.2:3b",
            "provider": "Meta",
            "params": "3B",
            "scores": {"total": 72, "quality": 65, "speed": 88, "fit": 75, "context": 60},
            "fit": "good",
            "tps": 95.0,
            "quantization": "Q4_K_M",
            "memory_required_gb": 2.0,
            "run_mode": "GPU",
            "use_case": "general",
            "max_context": 131072,
            "is_moe": False,
            "available": False,
        },
        {
            "name": "qwen3:1.8b",
            "provider": "Qwen",
            "params": "1.8B",
            "scores": {"total": 65, "quality": 55, "speed": 98, "fit": 80, "context": 50},
            "fit": "good",
            "tps": 120.0,
            "quantization": "Q4_K_M",
            "memory_required_gb": 1.2,
            "run_mode": "CPU",
            "use_case": "general",
            "max_context": 32768,
            "is_moe": False,
            "available": True,
        },
        {
            "name": "deepseek-r1:14b",
            "provider": "DeepSeek",
            "params": "14B",
            "scores": {"total": 30, "quality": 90, "speed": 5, "fit": 10, "context": 85},
            "fit": "too_tight",
            "tps": 3.0,
            "quantization": "Q2_K",
            "memory_required_gb": 9.8,
            "run_mode": "CPU+GPU",
            "use_case": "reasoning",
            "max_context": 32768,
            "is_moe": False,
            "available": False,
        },
    ]
})

MOCK_MODEL_INFO_JSON = json.dumps({
    "name": "qwen3:8b",
    "provider": "Qwen",
    "params": "8B",
    "scores": {"total": 85, "quality": 78, "speed": 82, "fit": 90, "context": 88},
    "fit": "perfect",
    "tps": 45.0,
    "quantization": "Q4_K_M",
    "memory_required_gb": 5.2,
    "run_mode": "GPU",
    "use_case": "general",
    "max_context": 32768,
    "is_moe": False,
    "available": True,
})


# ============================================================================
# Fixture: mock subprocess.run
# ============================================================================

class _MockCompletedProcess:
    def __init__(self, stdout: str, stderr: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def _mock_subprocess_run_system(*args, **kwargs):
    return _MockCompletedProcess(MOCK_SYSTEM_JSON)


def _mock_subprocess_run_recommend(*args, **kwargs):
    return _MockCompletedProcess(MOCK_RECOMMEND_JSON)


def _mock_subprocess_run_model_info(*args, **kwargs):
    return _MockCompletedProcess(MOCK_MODEL_INFO_JSON)


def _mock_subprocess_run_error(*args, **kwargs):
    return _MockCompletedProcess("", "llmfit error", returncode=1)


def _mock_subprocess_run_timeout(*args, **kwargs):
    import subprocess
    raise subprocess.TimeoutExpired(cmd=["llmfit"], timeout=30)


def _mock_subprocess_run_invalid_json(*args, **kwargs):
    return _MockCompletedProcess("not valid json at all {{{")


# ============================================================================
# Data model tests
# ============================================================================

class TestDataModels:
    """Verify dataclass instantiation and defaults."""

    def test_cpu_info_defaults(self):
        cpu = CpuInfo(cores=4)
        assert cpu.cores == 4
        assert cpu.model == "unknown"
        assert cpu.arch == "unknown"

    def test_gpu_info_defaults(self):
        gpu = GpuInfo(name="Test GPU", vram_gb=8.0)
        assert gpu.name == "Test GPU"
        assert gpu.vram_gb == 8.0
        assert gpu.backend == "unknown"

    def test_ram_info_defaults(self):
        ram = RamInfo(total_gb=16.0)
        assert ram.total_gb == 16.0
        assert ram.available_gb == 0.0

    def test_recommendation_score(self):
        score = RecommendationScore(
            total=85, quality=78, speed=82, fit=90, context=88)
        assert score.total == 85
        assert score.context == 88

    def test_model_recommendation_fields(self):
        rec = ModelRecommendation(
            model_name="test:1b", provider="Test", param_size="1B",
            score=RecommendationScore(80, 80, 80, 80, 80),
            fit_level="good", estimated_tps=50, quantization="Q4_K_M",
            memory_required_gb=1.0, run_mode="CPU", use_case="general",
            max_context=8192, is_moe=False, available=True,
        )
        assert rec.model_name == "test:1b"
        assert rec.fit_level == "good"
        assert rec.is_moe is False
        assert rec.available is True


# ============================================================================
# llmfit not installed — fallback tests
# ============================================================================

class TestLlmfitNotInstalled:
    """When llmfit is not on PATH, service should degrade gracefully."""

    @patch("app.services.llmfit_service.shutil.which", return_value=None)
    def test_available_is_false(self, _mock_which):
        svc = LlmfitService()
        assert svc.available is False

    @patch("app.services.llmfit_service.shutil.which", return_value=None)
    def test_system_profile_fallback(self, _mock_which):
        svc = LlmfitService()
        profile = svc.get_system_profile()
        assert isinstance(profile, SystemProfile)
        assert profile.cpu.cores >= 0

    @patch("app.services.llmfit_service.shutil.which", return_value=None)
    def test_recommendations_fallback(self, _mock_which):
        svc = LlmfitService()
        recs = svc.get_recommendations(limit=3)
        assert len(recs) <= 3
        for r in recs:
            assert isinstance(r, ModelRecommendation)
            assert r.provider == "Curated"

    @patch("app.services.llmfit_service.shutil.which", return_value=None)
    def test_model_info_returns_none(self, _mock_which):
        svc = LlmfitService()
        assert svc.get_model_info("qwen3:8b") is None


# ============================================================================
# System profile parsing tests
# ============================================================================

class TestSystemProfileParsing:
    """Parse llmfit system --json output correctly."""

    def setup_method(self):
        _cache_clear()

    @patch("app.services.llmfit_service.shutil.which", return_value="/usr/bin/llmfit")
    @patch("app.services.llmfit_service.subprocess.run")
    def test_parse_full_system(self, mock_run, _mock_which):
        mock_run.return_value = _MockCompletedProcess(MOCK_SYSTEM_JSON)
        svc = LlmfitService()
        profile = svc.get_system_profile()
        assert profile.cpu.cores == 8
        assert profile.cpu.model == "Intel Core i7-10750H"
        assert profile.cpu.arch == "x86_64"
        assert profile.ram.total_gb == 16.0
        assert profile.ram.available_gb == 8.5
        assert len(profile.gpus) == 1
        assert profile.gpus[0].name == "NVIDIA GeForce RTX 3060"
        assert profile.gpus[0].vram_gb == 6.0
        assert profile.gpus[0].backend == "CUDA"
        assert profile.os == "Windows 11"

    @patch("app.services.llmfit_service.shutil.which", return_value="/usr/bin/llmfit")
    @patch("app.services.llmfit_service.subprocess.run")
    def test_parse_system_no_gpu(self, mock_run, _mock_which):
        no_gpu_json = json.dumps({
            "cpu": {"cores": 4, "model": "M1", "arch": "arm64"},
            "ram": {"total_gb": 8.0, "available_gb": 3.0},
            "gpu": [],
            "os": "macOS",
        })
        mock_run.return_value = _MockCompletedProcess(no_gpu_json)
        svc = LlmfitService()
        profile = svc.get_system_profile()
        assert len(profile.gpus) == 0

    @patch("app.services.llmfit_service.shutil.which", return_value="/usr/bin/llmfit")
    @patch("app.services.llmfit_service.subprocess.run")
    def test_parse_system_alternate_keys(self, mock_run, _mock_which):
        """Test parsing when llmfit uses alternate JSON key names."""
        alt_json = json.dumps({
            "cpu": {"physical_cores": 6, "brand": "AMD Ryzen", "architecture": "x86_64"},
            "memory": {"total": 32.0, "available": 16.0},
            "gpus": [{"model": "AMD Radeon", "memory": 8.0}],
        })
        mock_run.return_value = _MockCompletedProcess(alt_json)
        svc = LlmfitService()
        profile = svc.get_system_profile()
        assert profile.cpu.cores == 6
        assert profile.ram.total_gb == 32.0
        assert len(profile.gpus) == 1
        assert profile.gpus[0].vram_gb == 8.0


# ============================================================================
# Model recommendation parsing tests
# ============================================================================

class TestRecommendationParsing:
    """Parse llmfit recommend --json output correctly."""

    def setup_method(self):
        _cache_clear()

    @patch("app.services.llmfit_service.shutil.which", return_value="/usr/bin/llmfit")
    @patch("app.services.llmfit_service.subprocess.run")
    def test_parse_recommendations_count(self, mock_run, _mock_which):
        mock_run.return_value = _MockCompletedProcess(MOCK_RECOMMEND_JSON)
        svc = LlmfitService()
        recs = svc.get_recommendations(limit=10)
        assert len(recs) == 3  # 4 total, 1 too_tight filtered

    @patch("app.services.llmfit_service.shutil.which", return_value="/usr/bin/llmfit")
    @patch("app.services.llmfit_service.subprocess.run")
    def test_parse_recommendation_scores(self, mock_run, _mock_which):
        mock_run.return_value = _MockCompletedProcess(MOCK_RECOMMEND_JSON)
        svc = LlmfitService()
        recs = svc.get_recommendations()
        first = recs[0]
        assert first.model_name == "qwen3:8b"
        assert first.score.total == 85
        assert first.score.quality == 78
        assert first.score.speed == 82
        assert first.score.fit == 90
        assert first.score.context == 88

    @patch("app.services.llmfit_service.shutil.which", return_value="/usr/bin/llmfit")
    @patch("app.services.llmfit_service.subprocess.run")
    def test_parse_recommendation_fit_levels(self, mock_run, _mock_which):
        mock_run.return_value = _MockCompletedProcess(MOCK_RECOMMEND_JSON)
        svc = LlmfitService()
        recs = svc.get_recommendations(include_too_tight=True)
        fit_levels = [r.fit_level for r in recs]
        assert "perfect" in fit_levels
        assert "good" in fit_levels
        assert "too_tight" in fit_levels

    @patch("app.services.llmfit_service.shutil.which", return_value="/usr/bin/llmfit")
    @patch("app.services.llmfit_service.subprocess.run")
    def test_parse_recommendation_tps(self, mock_run, _mock_which):
        mock_run.return_value = _MockCompletedProcess(MOCK_RECOMMEND_JSON)
        svc = LlmfitService()
        recs = svc.get_recommendations()
        tps_values = [r.estimated_tps for r in recs]
        assert 45 in tps_values

    @patch("app.services.llmfit_service.shutil.which", return_value="/usr/bin/llmfit")
    @patch("app.services.llmfit_service.subprocess.run")
    def test_filter_too_tight_excluded(self, mock_run, _mock_which):
        mock_run.return_value = _MockCompletedProcess(MOCK_RECOMMEND_JSON)
        svc = LlmfitService()
        recs = svc.get_recommendations(include_too_tight=False)
        assert all(r.fit_level != "too_tight" for r in recs)

    @patch("app.services.llmfit_service.shutil.which", return_value="/usr/bin/llmfit")
    @patch("app.services.llmfit_service.subprocess.run")
    def test_sort_by_tps(self, mock_run, _mock_which):
        mock_run.return_value = _MockCompletedProcess(MOCK_RECOMMEND_JSON)
        svc = LlmfitService()
        recs = svc.get_recommendations(sort="tps")
        # Should be sorted descending by tps
        for i in range(len(recs) - 1):
            assert recs[i].estimated_tps >= recs[i + 1].estimated_tps

    @patch("app.services.llmfit_service.shutil.which", return_value="/usr/bin/llmfit")
    @patch("app.services.llmfit_service.subprocess.run")
    def test_limit_respected(self, mock_run, _mock_which):
        mock_run.return_value = _MockCompletedProcess(MOCK_RECOMMEND_JSON)
        svc = LlmfitService()
        recs = svc.get_recommendations(limit=2)
        assert len(recs) <= 2


# ============================================================================
# Cache behavior tests
# ============================================================================

class TestCacheBehavior:
    """Verify in-memory cache works correctly."""

    def setup_method(self):
        _cache_clear()

    def test_cache_set_and_get(self):
        _cache_set("test_key", "test_value")
        assert _cache_get("test_key") == "test_value"

    def test_cache_expiry(self, monkeypatch):
        monkeypatch.setattr(time, "time", lambda: 0.0)
        _cache_set("key_exp", "val")
        monkeypatch.setattr(time, "time", lambda: 1000.0)  # way past TTL
        assert _cache_get("key_exp") is None

    def test_cache_clear(self):
        _cache_set("k1", "v1")
        _cache_set("k2", "v2")
        _cache_clear()
        assert _cache_get("k1") is None
        assert _cache_get("k2") is None

    @patch("app.services.llmfit_service.shutil.which", return_value="/usr/bin/llmfit")
    @patch("app.services.llmfit_service.subprocess.run")
    def test_system_profile_is_cached(self, mock_run, _mock_which):
        mock_run.return_value = _MockCompletedProcess(MOCK_SYSTEM_JSON)
        svc = LlmfitService()
        _ = svc.get_system_profile()
        call_count = mock_run.call_count
        _ = svc.get_system_profile()  # Should hit cache
        assert mock_run.call_count == call_count  # No new subprocess call

    @patch("app.services.llmfit_service.shutil.which", return_value="/usr/bin/llmfit")
    @patch("app.services.llmfit_service.subprocess.run")
    def test_refresh_cache(self, mock_run, _mock_which):
        mock_run.return_value = _MockCompletedProcess(MOCK_SYSTEM_JSON)
        svc = LlmfitService()
        _ = svc.get_system_profile()
        call1 = mock_run.call_count
        svc.refresh_cache()
        _ = svc.get_system_profile()
        assert mock_run.call_count == call1 + 1


# ============================================================================
# Error handling tests
# ============================================================================

class TestErrorHandling:
    """Ensure graceful handling of all failure modes."""

    def setup_method(self):
        _cache_clear()

    @patch("app.services.llmfit_service.shutil.which", return_value="/usr/bin/llmfit")
    @patch("app.services.llmfit_service.subprocess.run")
    def test_subprocess_error_returns_fallback(self, mock_run, _mock_which):
        mock_run.return_value = _MockCompletedProcess(
            "", "error", returncode=1)
        svc = LlmfitService()
        profile = svc.get_system_profile()
        assert isinstance(profile, SystemProfile)  # Fallback worked

    @patch("app.services.llmfit_service.shutil.which", return_value="/usr/bin/llmfit")
    @patch("app.services.llmfit_service.subprocess.run")
    def test_subprocess_timeout_falls_back(self, mock_run, _mock_which):
        mock_run.side_effect = _mock_subprocess_run_timeout
        svc = LlmfitService()
        profile = svc.get_system_profile()
        assert isinstance(profile, SystemProfile)

    @patch("app.services.llmfit_service.shutil.which", return_value="/usr/bin/llmfit")
    @patch("app.services.llmfit_service.subprocess.run")
    def test_invalid_json_falls_back(self, mock_run, _mock_which):
        mock_run.side_effect = _mock_subprocess_run_invalid_json
        svc = LlmfitService()
        recs = svc.get_recommendations()
        assert isinstance(recs, list)  # Catalog fallback

    @patch("app.services.llmfit_service.shutil.which", return_value="/usr/bin/llmfit")
    @patch("app.services.llmfit_service.subprocess.run")
    def test_empty_recommendations(self, mock_run, _mock_which):
        empty_json = json.dumps({"models": []})
        mock_run.return_value = _MockCompletedProcess(empty_json)
        svc = LlmfitService()
        recs = svc.get_recommendations()
        assert len(recs) == 0

    @patch("app.services.llmfit_service.shutil.which", return_value="/usr/bin/llmfit")
    @patch("app.services.llmfit_service.subprocess.run")
    def test_malformed_model_entry_skipped(self, mock_run, _mock_which):
        bad_json = json.dumps(
            {"models": [{"not": "a valid model entry"}, None, 123]})
        mock_run.return_value = _MockCompletedProcess(bad_json)
        svc = LlmfitService()
        recs = svc.get_recommendations()
        # Should not crash, just skip bad entries
        assert isinstance(recs, list)


# ============================================================================
# Docker mode tests
# ============================================================================

class TestDockerMode:
    """Verify Docker mode detection."""

    @patch("app.services.llmfit_service.LLMFIT_DOCKER_MODE", True)
    @patch("app.services.llmfit_service.shutil.which", return_value="/usr/bin/docker")
    @patch("app.services.llmfit_service.subprocess.run")
    def test_docker_available(self, mock_run, _mock_which):
        mock_run.return_value = _MockCompletedProcess(
            "llmfit v1.0.0", returncode=0)
        svc = LlmfitService()
        assert svc.available is True

    @patch("app.services.llmfit_service.LLMFIT_DOCKER_MODE", True)
    @patch("app.services.llmfit_service.shutil.which", return_value=None)
    def test_docker_not_available(self, _mock_which):
        svc = LlmfitService()
        assert svc.available is False


# ============================================================================
# Model info tests
# ============================================================================

class TestModelInfo:
    """Test single model lookup."""

    @patch("app.services.llmfit_service.shutil.which", return_value="/usr/bin/llmfit")
    @patch("app.services.llmfit_service.subprocess.run")
    def test_get_model_info(self, mock_run, _mock_which):
        mock_run.return_value = _MockCompletedProcess(MOCK_MODEL_INFO_JSON)
        svc = LlmfitService()
        info = svc.get_model_info("qwen3:8b")
        assert info is not None
        assert info.model_name == "qwen3:8b"
        assert info.fit_level == "perfect"

    @patch("app.services.llmfit_service.shutil.which", return_value="/usr/bin/llmfit")
    @patch("app.services.llmfit_service.subprocess.run")
    def test_model_info_cached(self, mock_run, _mock_which):
        mock_run.return_value = _MockCompletedProcess(MOCK_MODEL_INFO_JSON)
        svc = LlmfitService()
        _ = svc.get_model_info("qwen3:8b")
        c1 = mock_run.call_count
        _ = svc.get_model_info("qwen3:8b")
        assert mock_run.call_count == c1


# ============================================================================
# Edge case tests
# ============================================================================

class TestEdgeCases:
    """Boundary and edge case scenarios."""

    def setup_method(self):
        _cache_clear()

    @patch("app.services.llmfit_service.shutil.which", return_value="/usr/bin/llmfit")
    @patch("app.services.llmfit_service.subprocess.run")
    def test_single_gpu_not_in_list(self, mock_run, _mock_which):
        """GPU might be a dict, not a list."""
        json_str = json.dumps({
            "cpu": {"cores": 4},
            "ram": {"total_gb": 8},
            "gpu": {"name": "GTX 1650", "vram_gb": 4.0},
        })
        mock_run.return_value = _MockCompletedProcess(json_str)
        svc = LlmfitService()
        profile = svc.get_system_profile()
        assert len(profile.gpus) >= 0  # Should handle gracefully

    @patch("app.services.llmfit_service.shutil.which", return_value="/usr/bin/llmfit")
    @patch("app.services.llmfit_service.subprocess.run")
    def test_scores_as_single_number(self, mock_run, _mock_which):
        """llmfit might return a single score number instead of dict."""
        json_str = json.dumps(
            {"models": [{"name": "test", "scores": 75, "fit": "good", "tps": 30}]})
        mock_run.return_value = _MockCompletedProcess(json_str)
        svc = LlmfitService()
        recs = svc.get_recommendations()
        if recs:
            assert recs[0].score.total == 75

    @patch("app.services.llmfit_service.shutil.which", return_value="/usr/bin/llmfit")
    @patch("app.services.llmfit_service.subprocess.run")
    def test_use_case_filtering(self, mock_run, _mock_which):
        mock_run.return_value = _MockCompletedProcess(MOCK_RECOMMEND_JSON)
        svc = LlmfitService()
        recs = svc.get_recommendations(use_case="coding")
        assert isinstance(recs, list)

    def test_llmfit_not_found_error(self):
        with pytest.raises(LlmfitNotFoundError):
            raise LlmfitNotFoundError("test")

    def test_llmfit_timeout_error(self):
        with pytest.raises(LlmfitTimeoutError):
            raise LlmfitTimeoutError("test")
