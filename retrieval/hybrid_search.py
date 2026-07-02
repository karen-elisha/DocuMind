"""Optimized batch retrieval with shared Weaviate connection."""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

from config import Config
from retrieval.fact_scoring import apply_retrieval_adjustments
from vectorstore.weaviate_client import DocuMindWeaviateClient

logger = logging.getLogger(__name__)

RRF_K = 60

_shared_client: DocuMindWeaviateClient | None = None
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="retrieval")


def get_shared_client() -> DocuMindWeaviateClient:
    global _shared_client
    if _shared_client is None:
        _shared_client = DocuMindWeaviateClient()
    return _shared_client


def close_shared_client() -> None:
    global _shared_client
    if _shared_client is not None:
        try:
            _shared_client.close()
        except Exception:
            logger.exception("Failed to close shared Weaviate client")
        _shared_client = None


def warm_retrieval() -> None:
    """Pre-load embedder and open Weaviate connection at startup."""
    client = get_shared_client()
    client._embed_texts(["warmup query"], is_query=True)
    client.connect()
    print("[Retrieval] Embedder + Weaviate connection warmed")


def _reciprocal_rank_fusion(
    semantic_results: List[Dict],
    keyword_results: List[Dict],
    query: str,
) -> List[Dict]:
    by_id: Dict[str, Dict] = {}
    rrf_scores: Dict[str, float] = {}

    for rank, r in enumerate(semantic_results):
        nid = r.get("node_id") or r.get("uuid")
        if not nid:
            continue
        key = str(nid)
        rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (RRF_K + rank + 1)
        if key not in by_id:
            item = dict(r)
            item["_retrieval_source"] = "semantic"
            by_id[key] = item

    for rank, r in enumerate(keyword_results):
        nid = r.get("node_id") or r.get("uuid")
        if not nid:
            continue
        key = str(nid)
        rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (RRF_K + rank + 1)
        if key in by_id:
            by_id[key]["_retrieval_source"] = "both"
        else:
            item = dict(r)
            item["_retrieval_source"] = "keyword"
            by_id[key] = item

    fused = list(by_id.values())
    for c in fused:
        nid = str(c.get("node_id") or c.get("uuid") or "")
        raw_rrf = rrf_scores.get(nid, 0.0)
        c["score"] = min(0.95, raw_rrf * 15)
        c["score"] = apply_retrieval_adjustments(query, c)

    fused.sort(key=lambda x: x.get("score", 0), reverse=True)
    return fused


def _search_pair(
    client: DocuMindWeaviateClient,
    query: str,
    limit: int,
    doc_id: Optional[str],
    cross_doc: bool,
) -> List[Dict]:
    """Run semantic + BM25 in parallel, return fused results."""
    filter_doc_id = None if cross_doc else doc_id

    # Use a higher limit for table queries so multiple tables land in the same batch
    _is_table_query = bool(re.search(r'\btable\b|\bsegment\b|\bgoodwill\b|\brevenue\b|\bsales\b', query, re.I))
    effective_limit = min(limit * 2, 60) if _is_table_query else limit

    def _semantic():
        return client.hybrid_search(query=query, limit=effective_limit, doc_id=filter_doc_id, alpha=1.0)

    def _keyword():
        return client.hybrid_search(query=query, limit=effective_limit, doc_id=filter_doc_id, alpha=0.0)

    sem_future = _executor.submit(_semantic)
    kw_future = _executor.submit(_keyword)
    semantic_results = sem_future.result()
    keyword_results = kw_future.result()

    if not semantic_results and not keyword_results and not cross_doc and doc_id:
        semantic_results = client.fetch_all(doc_id=doc_id, limit=effective_limit)

    fused = _reciprocal_rank_fusion(semantic_results, keyword_results, query)

    # Boost table chunks that share a row_header token with the query
    # so "Industrial" in Note 3 and Item 7 both surface together
    query_tokens = set(re.findall(r'[A-Za-z][a-z]+', query))
    for c in fused:
        rh = str(c.get("row_headers") or "")
        if rh and c.get("type") in ("table", "table_row"):
            rh_tokens = set(re.findall(r'[A-Za-z][a-z]+', rh))
            overlap = query_tokens & rh_tokens
            if overlap:
                c["score"] = min(0.99, float(c.get("score") or 0) + 0.12 * len(overlap))

    return fused


def _is_strong_enough(candidates: List[Dict]) -> bool:
    """Skip extra query variants when the first pass already found good evidence."""
    if not candidates:
        return False
    top = candidates[0]
    top_score = float(top.get("score") or 0)
    top_type = str(top.get("type") or "").lower()
    if top_score >= Config.RETRIEVAL_STRONG_SCORE:
        return True
    if top_type == "fact" and top_score >= Config.RETRIEVAL_STRONG_SCORE - 0.08:
        return True
    top3 = candidates[:3]
    avg = sum(float(c.get("score") or 0) for c in top3) / len(top3)
    return avg >= Config.RETRIEVAL_STRONG_SCORE - 0.05


def retrieve_candidates(
    query: str,
    *,
    doc_id: Optional[str] = None,
    cross_doc: bool = False,
    limit: Optional[int] = None,
) -> List[Dict]:
    """
    Adaptive multi-query retrieval using a shared Weaviate connection.

    Starts with the original query; only runs expanded variants if the
    first pass doesn't surface strong enough evidence.
    """
    if limit is None:
        limit = Config.RETRIEVAL_LIMIT

    client = get_shared_client()
    by_id: Dict[str, Dict] = {}
    all_fused: List[Dict] = []

    def _merge(fused: List[Dict]) -> List[Dict]:
        nonlocal all_fused
        for c in fused:
            nid = c.get("node_id")
            if not nid:
                continue
            key = str(nid)
            if key not in by_id or float(c.get("score") or 0) > float(by_id[key].get("score") or 0):
                by_id[key] = c
        all_fused = sorted(by_id.values(), key=lambda x: x.get("score", 0), reverse=True)
        return all_fused

    # Pass 1: original query only (fast path for most questions)
    fused = _search_pair(client, query, limit, doc_id, cross_doc)
    candidates = _merge(fused)
    if _is_strong_enough(candidates):
        return candidates

    # Pass 2+: expanded variants (only when needed)
    from retrieval.query_expansion import expand_query

    for variant in expand_query(query)[1:]:
        fused = _search_pair(client, variant, limit, doc_id, cross_doc)
        candidates = _merge(fused)
        if _is_strong_enough(candidates):
            break

    return candidates


class HybridRetriever:
    """Backward-compatible wrapper; reuses shared connection."""

    def __init__(self):
        self.db = get_shared_client()
        self.collection_name = getattr(Config, "WEAVIATE_COLLECTION", "DocumentNode")

    def retrieve(
        self,
        query: str,
        semantic_limit: int = 50,
        keyword_limit: int = 50,
        doc_id: Optional[str] = None,
        cross_doc: bool = False,
    ) -> Dict[str, List]:
        limit = max(semantic_limit, keyword_limit)
        fused = _search_pair(self.db, query, limit, doc_id, cross_doc)
        keyword_only = [c for c in fused if c.get("_retrieval_source") in ("keyword", "both")]
        semantic_only = [c for c in fused if c.get("_retrieval_source") in ("semantic", "both")]
        return {
            "query": query,
            "cross_doc": cross_doc,
            "semantic_results": semantic_only,
            "keyword_results": keyword_only,
        }

    def close(self):
        pass  # shared connection closed on app shutdown
