"""Disk cache for parsed documents — skips Docling + vision + embeddings on re-upload."""

from __future__ import annotations

import json
import os
import time
from typing import Any

CACHE_TTL_SECONDS = 3 * 60 * 60  # 3 hours

from config import Config


def _cache_path(doc_id: str) -> str:
    os.makedirs(Config.CACHE_DIR, exist_ok=True)
    return os.path.join(Config.CACHE_DIR, f"{doc_id}.json")


def save(doc_id: str, parse_result: dict[str, Any], vision_results: dict[str, Any], insight: dict[str, Any]) -> None:
    """Persist ingestion outputs to disk after a successful upload."""
    payload = {
        "parse_result": parse_result,
        "vision_results": vision_results,
        "insight": insight,
        "saved_at": time.time(),
    }
    try:
        with open(_cache_path(doc_id), "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        print(f"[DocCache] Saved cache for doc_id={doc_id}")
    except Exception as exc:
        print(f"[DocCache] Failed to save cache for {doc_id}: {exc}")


def load(doc_id: str) -> tuple[dict, dict, dict] | None:
    """Return (parse_result, vision_results, insight) from disk, or None if not cached."""
    path = _cache_path(doc_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        age = time.time() - payload.get("saved_at", 0)
        if age > CACHE_TTL_SECONDS:
            os.remove(path)
            print(f"[DocCache] Cache expired for doc_id={doc_id} ({age/3600:.1f}h old)")
            return None
        print(f"[DocCache] Cache hit for doc_id={doc_id} — skipping parse + vision + embeddings")
        return payload["parse_result"], payload["vision_results"], payload["insight"]
    except Exception as exc:
        print(f"[DocCache] Cache load failed for {doc_id}: {exc}")
        return None


def delete(doc_id: str) -> None:
    path = _cache_path(doc_id)
    if os.path.exists(path):
        os.remove(path)
        print(f"[DocCache] Deleted cache for doc_id={doc_id}")
