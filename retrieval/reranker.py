from __future__ import annotations

import math
from typing import Dict, List, Optional

from sentence_transformers import CrossEncoder
import logging

from config import Config
from retrieval.fact_scoring import apply_rerank_adjustments, is_commentary_heavy

logger = logging.getLogger(__name__)

_RERANKER: Optional[CrossEncoder] = None
RERANKER_MODEL = "BAAI/bge-reranker-base"


def _get_reranker() -> CrossEncoder:
    global _RERANKER
    if _RERANKER is None:
        logger.info("Loading CrossEncoder: %s", RERANKER_MODEL)
        _RERANKER = CrossEncoder(RERANKER_MODEL)
    return _RERANKER


def warm_reranker() -> None:
    """Pre-load cross-encoder at startup to avoid cold-start latency."""
    model = _get_reranker()
    model.predict([("warmup", "warmup")], show_progress_bar=False)
    print(f"[Reranker] {RERANKER_MODEL} warmed")


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    z = math.exp(x)
    return z / (1.0 + z)


def _safe_str(x: object) -> str:
    return str(x) if x is not None else ""


def _prepend_metadata(candidate: Dict, content: str) -> str:
    parts: list[str] = []

    section_title = _safe_str(candidate.get("section_title", candidate.get("section", "")))
    node_type = _safe_str(candidate.get("type", ""))
    page_number = _safe_str(candidate.get("page", ""))

    if section_title:
        parts.append(f"[Section: {section_title[:80]}]")
    if node_type:
        parts.append(f"[Type: {node_type}]")
    if page_number:
        parts.append(f"[Page: {page_number}]")

    max_chars = Config.RERANK_MAX_CHARS
    if len(content) > max_chars:
        content = content[:max_chars]
    parts.append(content)
    return " ".join(p for p in parts if p)


def rerank(query: str, candidates: List[Dict], top_k: int | None = None) -> List[Dict]:
    """Rerank top retrieval candidates with cross-encoder (prefiltered for speed)."""
    if not candidates:
        return []

    if top_k is None:
        top_k = Config.RERANK_TOP_K

    pool_size = Config.RERANK_POOL_SIZE
    if len(candidates) > pool_size:
        candidates = sorted(candidates, key=lambda x: x.get("score", 0), reverse=True)[:pool_size]

    model = _get_reranker()
    augmented = [_prepend_metadata(c, c.get("content", "") or "") for c in candidates]
    pairs = [(query, aug) for aug in augmented]

    try:
        scores = model.predict(pairs, batch_size=16, show_progress_bar=False)
    except Exception as e:
        logger.warning("Reranker predict failed (%s); falling back to retrieval order", e)
        return candidates[:top_k]

    if len(scores) != len(candidates):
        logger.warning("Reranker score mismatch; falling back")
        return candidates[:top_k]

    for c, s in zip(candidates, scores):
        prob = _sigmoid(float(s))
        content = str(c.get("content") or "")
        if is_commentary_heavy(content):
            prob *= 0.75
        c["score"] = apply_rerank_adjustments(query, c, prob)
        c["_rerank_score"] = prob

    candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
    return candidates[:top_k]
