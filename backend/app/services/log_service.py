from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import config


class LogService:
    def query(
        self,
        *,
        level: str | None = None,
        module: str | None = None,
        trace_id: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        entries = self._read_entries()
        start_dt = self._parse_time(start_time)
        end_dt = self._parse_time(end_time)

        filtered: list[dict[str, Any]] = []
        for entry in entries:
            if level and entry.get("level") != level.lower():
                continue
            if module and entry.get("module") != module:
                continue
            if trace_id and entry.get("trace_id") != trace_id:
                continue
            timestamp = self._parse_time(entry.get("timestamp"))
            if start_dt and timestamp and timestamp < start_dt:
                continue
            if end_dt and timestamp and timestamp > end_dt:
                continue
            filtered.append(entry)
        return filtered[-limit:]

    def _read_entries(self) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        log_files = sorted(config.logs_root.glob("app.log*"))
        for log_file in log_files:
            entries.extend(self._read_file(log_file))
        return entries

    def _read_file(self, path: Path) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if not path.exists():
            return rows
        with path.open("r", encoding="utf-8", errors="ignore") as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows

    def _parse_time(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
