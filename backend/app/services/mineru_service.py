from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.core.config import config


class MinerUService:
    def __init__(self) -> None:
        self.command = config.mineru_command
        self.backend = config.mineru_backend
        self.language = config.mineru_language
        self.device = config.mineru_device

    def is_available(self) -> bool:
        return shutil.which(self.command) is not None

    def supports_file(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg"}

    def parse_file(self, file_path: Path, enable_ocr: bool = True) -> str:
        if not self.is_available():
            raise RuntimeError("MinerU CLI is not installed or not available in PATH.")
        if not self.supports_file(file_path):
            raise ValueError(f"MinerU CLI does not support {file_path.suffix.lower()} input.")

        with tempfile.TemporaryDirectory(prefix="mineru-output-") as temp_dir:
            output_dir = Path(temp_dir)
            command = [
                self.command,
                "-p",
                str(file_path),
                "-o",
                str(output_dir),
                "-b",
                self.backend,
                "-l",
                self.language,
            ]

            if file_path.suffix.lower() == ".pdf":
                command.extend(["-m", "auto" if enable_ocr else "txt"])
            if self.device:
                command.extend(["-d", self.device])

            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
            )

            markdown_text = self._read_markdown_output(output_dir)
            if markdown_text:
                return markdown_text

            json_text = self._read_json_output(output_dir)
            if json_text:
                return json_text

            raise RuntimeError("MinerU completed, but no markdown or JSON output was found.")

    def _read_markdown_output(self, output_dir: Path) -> str:
        candidates = sorted(
            output_dir.rglob("*.md"),
            key=lambda item: (item.stat().st_size, item.name),
            reverse=True,
        )
        for candidate in candidates:
            if candidate.stat().st_size == 0:
                continue
            return candidate.read_text(encoding="utf-8", errors="ignore").strip()
        return ""

    def _read_json_output(self, output_dir: Path) -> str:
        candidates = sorted(
            output_dir.rglob("*.json"),
            key=lambda item: (item.stat().st_size, item.name),
            reverse=True,
        )
        for candidate in candidates:
            if candidate.stat().st_size == 0:
                continue
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8", errors="ignore"))
            except json.JSONDecodeError:
                continue
            extracted = self._extract_text_from_json(payload)
            if extracted:
                return extracted
        return ""

    def _extract_text_from_json(self, payload: object) -> str:
        chunks: list[str] = []

        def walk(value: object) -> None:
            if isinstance(value, dict):
                for key, nested in value.items():
                    if key in {"text", "content", "markdown", "html", "latex"} and isinstance(nested, str):
                        cleaned = nested.strip()
                        if cleaned:
                            chunks.append(cleaned)
                    else:
                        walk(nested)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(payload)
        return "\n\n".join(chunks).strip()
