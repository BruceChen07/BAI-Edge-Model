from __future__ import annotations

import json
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from app.core.config import config
from app.core.request_context import get_trace_id


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "module": getattr(record, "module_name", record.module),
            "event": getattr(record, "event", record.getMessage()),
            "message": record.getMessage(),
            "trace_id": getattr(record, "trace_id", get_trace_id()),
        }

        if hasattr(record, "context") and isinstance(record.context, dict):
            payload["context"] = record.context
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging() -> None:
    root_logger = logging.getLogger()
    if getattr(root_logger, "_bai_logging_configured", False):
        return

    log_level = getattr(logging, config.log_level, logging.INFO)
    root_logger.setLevel(log_level)

    formatter = JsonFormatter()
    app_log_path = config.logs_root / "app.log"
    error_log_path = config.logs_root / "error.log"
    _ensure_log_parent(app_log_path)

    app_handler = RotatingFileHandler(
        app_log_path,
        maxBytes=config.log_max_bytes,
        backupCount=config.log_backup_count,
        encoding="utf-8",
    )
    app_handler.setLevel(log_level)
    app_handler.setFormatter(formatter)

    error_handler = RotatingFileHandler(
        error_log_path,
        maxBytes=config.log_max_bytes,
        backupCount=config.log_backup_count,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    root_logger.handlers.clear()
    root_logger.addHandler(app_handler)
    root_logger.addHandler(error_handler)
    root_logger.addHandler(console_handler)
    root_logger._bai_logging_configured = True  # type: ignore[attr-defined]


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    message: str,
    *,
    module_name: str,
    trace_id: str | None = None,
    exc_info: Any = None,
    **context: Any,
) -> None:
    logger.log(
        level,
        message,
        extra={
            "event": event,
            "module_name": module_name,
            "trace_id": trace_id or get_trace_id(),
            "context": context,
        },
        exc_info=exc_info,
    )


def _ensure_log_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
