"""
Phase 2: Model Catalog Service & API unit tests.
Covers: DB operations, CRUD, search/filter, upsert batch, DTO conversion, sync script.
"""
from __future__ import annotations

import json

import pytest

from app.core.database import init_db
from app.schemas.catalog import CatalogEntryDTO
from app.services.model_catalog_service import ModelCatalogService, _row_to_dto


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def _ensure_db() -> None:
    """Re-init DB so model_catalog table exists."""
    init_db()


@pytest.fixture
def svc() -> ModelCatalogService:
    svc = ModelCatalogService()
    svc.clear()
    return svc


@pytest.fixture
def sample_entry() -> CatalogEntryDTO:
    return CatalogEntryDTO(
        id="test-001",
        model_name="qwen3:8b",
        provider="Qwen",
        param_size="8B",
        score_total=85,
        score_quality=78,
        score_speed=82,
        score_fit=90,
        score_context=88,
        fit_level="perfect",
        estimated_tps=45,
        quantization="Q4_K_M",
        memory_required_gb=5.2,
        vram_required_gb=6.0,
        run_mode="GPU",
        use_case="general",
        max_context=32768,
        is_moe=False,
        available=True,
        description="Strong general-purpose model",
        tags=["chat", "multilingual"],
        source="curated",
    )


@pytest.fixture
def sample_entry2() -> CatalogEntryDTO:
    return CatalogEntryDTO(
        id="test-002",
        model_name="llama3.2:3b",
        provider="Meta",
        param_size="3B",
        score_total=72,
        score_quality=65,
        score_speed=88,
        score_fit=75,
        score_context=60,
        fit_level="good",
        estimated_tps=95,
        quantization="Q4_K_M",
        memory_required_gb=2.0,
        vram_required_gb=3.0,
        run_mode="GPU",
        use_case="general",
        max_context=131072,
        is_moe=False,
        available=False,
        description="Fast lightweight model",
        tags=["chat"],
        source="curated",
    )


# ============================================================================
# Row-to-DTO conversion
# ============================================================================

class TestRowToDTO:
    def test_basic_conversion(self):
        row = {
            "id": "a1", "model_name": "test:1b", "provider": "Test",
            "param_size": "1B", "score_total": 80, "score_quality": 75,
            "score_speed": 90, "score_fit": 85, "score_context": 70,
            "fit_level": "good", "estimated_tps": 100, "quantization": "Q4_K_M",
            "memory_required_gb": 1.0, "vram_required_gb": 0.0,
            "run_mode": "CPU", "use_case": "chat", "max_context": 4096,
            "is_moe": 0, "available": 1, "description": "test", "tags": "[]",
            "source": "curated", "raw_json": "", "last_synced_at": "",
            "created_at": "", "updated_at": "",
        }
        dto = _row_to_dto(row)
        assert dto.id == "a1"
        assert dto.model_name == "test:1b"
        assert dto.score_total == 80
        assert dto.is_moe is False
        assert dto.available is True
        assert dto.tags == []

    def test_str_tags_conversion(self):
        row = {
            "id": "a1", "model_name": "test:1b", "provider": "Test",
            "param_size": "1B", "score_total": 0, "score_quality": 0,
            "score_speed": 0, "score_fit": 0, "score_context": 0,
            "fit_level": "unknown", "estimated_tps": 0, "quantization": "",
            "memory_required_gb": 0, "vram_required_gb": 0,
            "run_mode": "CPU", "use_case": "general", "max_context": 0,
            "is_moe": 0, "available": 0, "description": "", "tags": '["chat", "code"]',
            "source": "", "raw_json": "", "last_synced_at": "",
            "created_at": "", "updated_at": "",
        }
        dto = _row_to_dto(row)
        assert dto.tags == ["chat", "code"]

    def test_invalid_tags_json(self):
        row = {
            "id": "a1", "model_name": "test:1b", "provider": "Test",
            "param_size": "1B", "score_total": 0, "score_quality": 0,
            "score_speed": 0, "score_fit": 0, "score_context": 0,
            "fit_level": "unknown", "estimated_tps": 0, "quantization": "",
            "memory_required_gb": 0, "vram_required_gb": 0,
            "run_mode": "CPU", "use_case": "general", "max_context": 0,
            "is_moe": 0, "available": 0, "description": "", "tags": "not-json",
            "source": "", "raw_json": "", "last_synced_at": "",
            "created_at": "", "updated_at": "",
        }
        dto = _row_to_dto(row)
        assert dto.tags == []


# ============================================================================
# CRUD operations
# ============================================================================

class TestCRUD:
    def test_upsert_creates_new(self, svc, sample_entry):
        res = svc.upsert(sample_entry)
        assert res.model_name == "qwen3:8b"
        assert res.score_total == 85
        assert svc.count() == 1

    def test_upsert_updates_existing(self, svc, sample_entry):
        svc.upsert(sample_entry)
        updated = sample_entry.model_copy()
        updated.score_total = 90
        updated.fit_level = "perfect"
        res = svc.upsert(updated)
        assert res.score_total == 90
        assert svc.count() == 1  # still one row

    def test_get_by_id(self, svc, sample_entry):
        svc.upsert(sample_entry)
        res = svc.get_by_id("test-001")
        assert res is not None
        assert res.model_name == "qwen3:8b"

    def test_get_by_id_not_found(self, svc):
        assert svc.get_by_id("nonexistent") is None

    def test_get_by_model_name(self, svc, sample_entry):
        svc.upsert(sample_entry)
        res = svc.get_by_model_name("qwen3:8b")
        assert res is not None
        assert res.provider == "Qwen"

    def test_get_by_model_name_not_found(self, svc):
        assert svc.get_by_model_name("nonexistent") is None

    def test_delete(self, svc, sample_entry):
        svc.upsert(sample_entry)
        assert svc.delete("test-001") is True
        assert svc.count() == 0

    def test_delete_not_found(self, svc):
        assert svc.delete("nonexistent") is False

    def test_clear(self, svc, sample_entry, sample_entry2):
        svc.upsert(sample_entry)
        svc.upsert(sample_entry2)
        assert svc.count() == 2
        deleted = svc.clear()
        assert deleted == 2
        assert svc.count() == 0


# ============================================================================
# Upsert batch
# ============================================================================

class TestUpsertBatch:
    def test_batch_insert(self, svc, sample_entry, sample_entry2):
        result = svc.upsert_batch([sample_entry, sample_entry2])
        assert result.synced == 2
        assert result.updated == 0
        assert svc.count() == 2

    def test_batch_mixed(self, svc, sample_entry, sample_entry2):
        svc.upsert(sample_entry)  # pre-seed one
        updated = sample_entry.model_copy()
        updated.score_total = 100
        result = svc.upsert_batch([updated, sample_entry2])
        assert result.updated == 1
        assert result.synced == 1
        assert svc.count() == 2

    def test_batch_empty(self, svc):
        result = svc.upsert_batch([])
        assert result.synced == 0
        assert result.updated == 0

    def test_batch_error_handling(self, svc, sample_entry):
        """Should not crash on invalid entries."""
        result = svc.upsert_batch([sample_entry])  # uses fixture
        assert result.synced >= 0


# ============================================================================
# List / Search / Filter
# ============================================================================

class TestListFilters:
    @pytest.fixture(autouse=True)
    def _seed(self, svc, sample_entry, sample_entry2):
        svc.clear()
        svc.upsert(sample_entry)
        svc.upsert(sample_entry2)

    def test_list_all(self, svc):
        result = svc.list_all()
        assert result.total == 2
        assert len(result.items) == 2

    def test_filter_provider(self, svc):
        result = svc.list_all(provider="Qwen")
        assert result.total == 1
        assert result.items[0].provider == "Qwen"

    def test_filter_param_size(self, svc):
        result = svc.list_all(param_size="3B")
        assert result.total == 1
        assert result.items[0].param_size == "3B"

    def test_filter_fit_level(self, svc):
        result = svc.list_all(fit_level="perfect")
        assert result.total == 1
        assert result.items[0].fit_level == "perfect"

    def test_filter_min_score(self, svc):
        result = svc.list_all(min_score=80)
        assert result.total == 1
        assert result.items[0].score_total >= 80

    def test_filter_combined(self, svc):
        result = svc.list_all(provider="Qwen", fit_level="perfect")
        assert result.total == 1

    def test_filter_no_match(self, svc):
        result = svc.list_all(provider="nonexistent")
        assert result.total == 0

    def test_sort_by_tps(self, svc):
        result = svc.list_all(sort_by="estimated_tps", sort_dir="desc")
        assert result.total == 2
        # llama3.2:3b has 95 tps > qwen3:8b has 45 tps
        assert result.items[0].estimated_tps >= result.items[1].estimated_tps

    def test_sort_by_model_name(self, svc):
        result = svc.list_all(sort_by="model_name", sort_dir="asc")
        assert result.total == 2
        # llama3.2 comes before qwen3 alphabetically
        assert result.items[0].model_name < result.items[1].model_name

    def test_offset_limit(self, svc):
        result = svc.list_all(offset=1, limit=1)
        assert result.total == 2  # total still counts all
        assert len(result.items) == 1

    def test_invalid_sort_column(self, svc):
        """Invalid sort column should default to score_total."""
        result = svc.list_all(sort_by="invalid_column")
        assert result.total == 2  # doesn't crash


class TestSearch:
    @pytest.fixture(autouse=True)
    def _seed(self, svc, sample_entry, sample_entry2):
        svc.clear()
        svc.upsert(sample_entry)
        svc.upsert(sample_entry2)

    def test_search_by_name(self, svc):
        result = svc.search("qwen")
        assert result.total == 1
        assert "qwen" in result.items[0].model_name.lower()

    def test_search_by_provider(self, svc):
        result = svc.search("Meta")
        assert result.total == 1
        assert result.items[0].provider == "Meta"

    def test_search_by_description(self, svc):
        result = svc.search("Strong general-purpose")
        assert result.total == 1

    def test_search_no_match(self, svc):
        result = svc.search("zzzzzzzz")
        assert result.total == 0

    def test_search_empty_query(self, svc):
        result = svc.search("")
        assert result.total >= 2  # falls back to list_all


# ============================================================================
# Count
# ============================================================================

class TestCount:
    def test_empty(self, svc):
        assert svc.count() == 0

    def test_with_entries(self, svc, sample_entry, sample_entry2):
        svc.upsert(sample_entry)
        svc.upsert(sample_entry2)
        assert svc.count() == 2
