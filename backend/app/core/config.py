from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    project_root: Path = Path(__file__).resolve().parents[3]
    storage_root: Path = project_root / "storage"
    files_root: Path = storage_root / "files"
    exports_root: Path = storage_root / "exports"
    logs_root: Path = storage_root / "logs"
    indexes_root: Path = storage_root / "indexes"
    db_path: Path = project_root / "storage" / "bai_edge_model.db"
    app_name: str = "BAI Edge Model"
    app_version: str = "0.1.0"
    default_language: str = "zh-CN"
    mineru_command: str = os.getenv("MINERU_COMMAND", "mineru")
    mineru_backend: str = os.getenv("MINERU_BACKEND", "pipeline")
    mineru_language: str = os.getenv("MINERU_LANGUAGE", "ch")
    mineru_device: str | None = os.getenv("MINERU_DEVICE", "cpu")
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_max_bytes: int = int(os.getenv("LOG_MAX_BYTES", str(5 * 1024 * 1024)))
    log_backup_count: int = int(os.getenv("LOG_BACKUP_COUNT", "5"))
    ollama_connect_timeout_seconds: float = float(
        os.getenv("OLLAMA_CONNECT_TIMEOUT_SECONDS", "10"))
    ollama_read_timeout_seconds: float = float(
        os.getenv("OLLAMA_READ_TIMEOUT_SECONDS", "300"))
    ollama_write_timeout_seconds: float = float(
        os.getenv("OLLAMA_WRITE_TIMEOUT_SECONDS", "30"))
    ollama_pool_timeout_seconds: float = float(
        os.getenv("OLLAMA_POOL_TIMEOUT_SECONDS", "30"))
    ollama_list_timeout_seconds: float = float(
        os.getenv("OLLAMA_LIST_TIMEOUT_SECONDS", "10"))

    # User-customizable timeout override. When set, this value overrides the
    # tiered read-timeout logic for all model sizes. Set via the settings API.
    user_timeout_override_seconds: float | None = None


# ---------------------------------------------------------------------------
# Tiered timeout presets keyed by model parameter size.
# Larger models get longer read timeouts to avoid false timeout interruptions.
# ---------------------------------------------------------------------------
TIMEOUT_TIERS: dict[str, dict[str, float]] = {
    # param_size -> {connect, read, write, pool}
    "0.6B": {"connect": 10, "read": 90,  "write": 30, "pool": 30},
    "1.5B": {"connect": 10, "read": 120, "write": 30, "pool": 30},
    "1.8B": {"connect": 10, "read": 150, "write": 30, "pool": 30},
    "3B":   {"connect": 10, "read": 240, "write": 30, "pool": 30},
    "3.8B": {"connect": 10, "read": 300, "write": 30, "pool": 30},
    "4B":   {"connect": 15, "read": 360, "write": 60, "pool": 30},
    "8B":   {"connect": 15, "read": 600, "write": 60, "pool": 30},
}
DEFAULT_TIMEOUT_TIER = {"connect": 10, "read": 300, "write": 30, "pool": 30}


config = AppConfig()
