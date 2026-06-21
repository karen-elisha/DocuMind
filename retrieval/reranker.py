from __future__ import annotations
import math
from typing import Dict, List, Optional
from sentence_transformers import CrossEncoder
import logging

logger = logging.getLogger(__name__)

_RERANKER: Optional[CrossEncoder] = None


def _get_reranker() -> CrossEncoder:
    global _RERANKER
    if _RERANKER is None:
        logger.info("Loading CrossEncoder: cross-encoder/ms-marco-MiniLM-L-6-v2")
        _RERANKER = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _RERANKER


def _sigmoid(x: float) -> float:
    """Convert logit to probability in [0, 1]."""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    else:
        z = math.exp(x)
        return z / (1.0 + z)


def _safe_str(x: object) -> str:
    return str(x) if x is not None else ""


def _prepend_metadata(candidate: Dict, content: str) -> str:
    """Prepend normalized metadata fields to content for cross-encoder scoring.

    Required metadata schema (best-effort):
      - document_name
      - page_number
      - node_type
      - section_title
      - parent_heading
      - caption
      - table_id
      - figure_id
    """
    parts: list[str] = []

    document_name = _safe_str(candidate.get("document_name", ""))
    page_number = _safe_str(candidate.get("page_number", candidate.get("page", "")))
    node_type = _safe_str(candidate.get("node_type", candidate.get("node_type", "") or candidate.get("type", "")))
    section_title = _safe_str(candidate.get("section_title", candidate.get("section", "")))
    parent_heading = _safe_str(candidate.get("parent_heading", ""))
    caption = _safe_str(candidate.get("caption", candidate.get("caption_text", "")))
    table_id = _safe_str(candidate.get("table_id", candidate.get("table_number", "")))
    figure_id = _safe_str(candidate.get("figure_id", candidate.get("figure_number", "")))

    if document_name:
        parts.append(f"[Document: {document_name}]")
    if page_number:
        parts.append(f"[Page: {page_number}]")
    if node_type:
        parts.append(f"[NodeType: {node_type}]")
    if section_title:
        parts.append(f"[SectionTitle: {section_title}]")
    if parent_heading:
        parts.append(f"[ParentHeading: {parent_heading}]")
    if caption:
        parts.append(f"[Caption: {caption}]")
    if figure_id:
        parts.append(f"[FigureID: {figure_id}]")
    if table_id:
        parts.append(f"[TableID: {table_id}]")

    # Keep content last
    parts.append(_safe_str(content))

    return " ".join(p for p in parts if p)


def rerank(query: str, candidates: List[Dict], top_k: int = 10) -> List[Dict]:
    """Rerank candidate chunks using a cross-encoder.

    Each candidate dict must have a 'content' key.
    Prepends metadata (section, type, figure/table number) to the content
    so the cross-encoder has richer context.

    Returns top_k candidates sorted by relevance score (descending),
    with 'score' and '_rerank_score' fields updated.
    """
    if not candidates:
        return []

    model = _get_reranker()

    # Build input pairs: metadata-augmented content vs query
    augmented = [_prepend_metadata(c, c.get("content", "") or "") for c in candidates]
    pairs = [(query, aug) for aug in augmented]

    try:
        scores = model.predict(pairs, show_progress_bar=False)
    except Exception as e:
        logger.warning("Reranker predict failed (%s); falling back to original order", e)
        return candidates[:top_k]

    if len(scores) != len(candidates):
        logger.warning("Reranker returned %d scores for %d candidates; falling back", len(scores), len(candidates))
        return candidates[:top_k]

    for c, s in zip(candidates, scores):
        # s is a raw logit — sigmoid to [0, 1]
        prob = _sigmoid(float(s))

        # Blend: 70% reranker probability + 30% original retrieval score
        prev = c.get("score", 0.5)
        if isinstance(prev, (int, float)) and prev > 0:
            blended = 0.7 * prob + 0.3 * prev
        else:
            blended = prob

        c["score"] = max(0.01, min(blended, 0.99))
        c["_rerank_score"] = prob

    candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
    return candidates[:top_k]
