from __future__ import annotations

from app.core.database import get_connection
from app.schemas.settings import SettingsDTO, SettingsUpdateDTO
from app.services.base import BaseService


class SettingsService(BaseService):
    def get(self) -> SettingsDTO:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM app_settings WHERE id = 1").fetchone()
        return SettingsDTO(
            language=row["language"],
            theme=row["theme"],
            default_model=row["default_model"],
            embedding_model=row["embedding_model"],
            ocr_enabled=bool(row["ocr_enabled"]),
            storage_root=row["storage_root"],
            web_search_enabled=bool(row["web_search_enabled"]),
        )

    def update(self, payload: SettingsUpdateDTO) -> SettingsDTO:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE app_settings
                SET language = ?, theme = ?, default_model = ?, embedding_model = ?,
                    ocr_enabled = ?, web_search_enabled = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
                """,
                (
                    payload.language,
                    payload.theme,
                    payload.default_model,
                    payload.embedding_model,
                    int(payload.ocr_enabled),
                    int(payload.web_search_enabled),
                ),
            )
        self.log_operation("settings", "update", "1", "success", payload.model_dump())
        return self.get()
