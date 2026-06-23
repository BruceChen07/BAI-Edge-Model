"""
Sync script: populate model_catalog DB from llmfit CLI output
or from the curated catalog in resource_monitor.py.

Usage:
    python -m scripts.sync_model_catalog [--source llmfit|curated] [--limit 200]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from pathlib import Path

# Add backend to path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import init_db
from app.schemas.catalog import CatalogEntryDTO
from app.services.model_catalog_service import ModelCatalogService


def sync_from_llmfit(svc: ModelCatalogService, limit: int = 200) -> int:
    """Pull model data from llmfit recommend --json and upsert into catalog."""
    try:
        result = subprocess.run(
            ["llmfit", "recommend", "--json", "--limit", str(limit)],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            print(f"[WARN] llmfit exited {result.returncode}: {result.stderr[:200]}")
            return 0
        data = json.loads(result.stdout)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"[WARN] llmfit not available: {e}")
        return 0
    except json.JSONDecodeError:
        print("[WARN] llmfit returned invalid JSON")
        return 0

    models = data.get("models", data.get("recommendations", []))
    if not models:
        models = [data] if isinstance(data, dict) and "name" in data else []

    entries = []
    for m in models:
        if not isinstance(m, dict):
            continue
        scores = m.get("scores", m.get("score", {}))
        if isinstance(scores, (int, float)):
            scores = {"total": scores}

        entries.append(CatalogEntryDTO(
            id=str(uuid.uuid4()),
            model_name=m.get("name", m.get("model_name", "unknown")),
            provider=m.get("provider", m.get("author", "unknown")),
            param_size=m.get("params", m.get("param_size", "unknown")),
            score_total=float(scores.get("total", scores.get("overall", 0))),
            score_quality=float(scores.get("quality", 0)),
            score_speed=float(scores.get("speed", 0)),
            score_fit=float(scores.get("fit", 0)),
            score_context=float(scores.get("context", 0)),
            fit_level=m.get("fit", m.get("fit_level", "unknown")),
            estimated_tps=float(m.get("tps", m.get("estimated_tps", 0))),
            quantization=m.get("quantization", m.get("quant", "Q4_K_M")),
            memory_required_gb=float(m.get("memory_required_gb", m.get("memory_gb", m.get("vram_gb", 0)))),
            vram_required_gb=float(m.get("vram_required_gb", m.get("vram_gb", 0))),
            run_mode=m.get("run_mode", m.get("mode", "CPU")),
            use_case=m.get("use_case", m.get("category", "general")),
            max_context=int(m.get("max_context", m.get("context", 8192))),
            is_moe=bool(m.get("is_moe", m.get("moe", False))),
            available=bool(m.get("available", m.get("installed", False))),
            description=m.get("description", ""),
            tags=m.get("tags", []) if isinstance(m.get("tags"), list) else [],
            source="llmfit",
            raw_json=json.dumps(m),
        ))

    if entries:
        result = svc.upsert_batch(entries)
        print(f"[OK] llmfit sync: {result.synced} new, {result.updated} updated, {len(result.errors)} errors")
        if result.errors:
            for e in result.errors[:5]:
                print(f"  [ERR] {e}")
        return result.synced + result.updated

    print("[WARN] llmfit returned 0 models")
    return 0


def sync_from_curated(svc: ModelCatalogService) -> int:
    """Populate catalog from the curated model list in resource_monitor.py."""
    from app.services.resource_monitor import CURATED_CATALOG

    entries = []
    for req in CURATED_CATALOG:
        entries.append(CatalogEntryDTO(
            id=str(uuid.uuid4()),
            model_name=req.ollama_name,
            provider=req.display_name.split(" ")[0] if " " in req.display_name else req.display_name,
            param_size=req.param_size,
            score_total=70,
            score_quality=70,
            score_speed=70,
            score_fit=70,
            score_context=70,
            fit_level="good",
            estimated_tps=20,
            memory_required_gb=req.approx_size_gb,
            vram_required_gb=req.vram_gb or 0,
            run_mode="GPU" if req.vram_gb else "CPU",
            max_context=8192,
            description=req.description,
            tags=req.tags,
            source="curated",
        ))

    if entries:
        result = svc.upsert_batch(entries)
        print(f"[OK] curated sync: {result.synced} new, {result.updated} updated")
        return result.synced + result.updated

    print("[WARN] curated catalog returned 0 models")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync model catalog from llmfit or curated catalog")
    parser.add_argument("--source", choices=["llmfit", "curated", "all"], default="curated")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    init_db()
    svc = ModelCatalogService()

    total = 0
    if args.source in ("curated", "all"):
        total += sync_from_curated(svc)
    if args.source in ("llmfit", "all"):
        total += sync_from_llmfit(svc, args.limit)

    print(f"\nDone. {total} total models in catalog (table: {svc.count()})")


if __name__ == "__main__":
    main()
