from __future__ import annotations

from pydantic import BaseModel


class SettingsDTO(BaseModel):
    language: str
    theme: str
    default_model: str
    embedding_model: str
    ocr_enabled: bool
    storage_root: str
    web_search_enabled: bool


class SettingsUpdateDTO(BaseModel):
    language: str
    theme: str
    default_model: str
    embedding_model: str
    ocr_enabled: bool
    web_search_enabled: bool
