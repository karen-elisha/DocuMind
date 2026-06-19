# retrieval/hybrid_search.py

import logging
from typing import Dict, List, Optional

from ingestion.node_builder import _get_embeddings
from vectorstore.weaviate_client import WeaviateClient
from config import Config

logger = logging.getLogger(__name__)


class HybridRetriever:
    """
    Hybrid Retrieval:
    1. Semantic Search (vector)
    2. Keyword Search (BM25)
    3. Return both result sets for Evidence Fusion layer
    """

    def __init__(self):
        self.db = WeaviateClient()
        self.collection_name = getattr(
            Config,
            "WEAVIATE_COLLECTION",
            "DocumentNode",
        )

    def retrieve(
        self,
        query: str,
        semantic_limit: int = 10,
        keyword_limit: int = 10,
        doc_id: Optional[str] = None,
    ) -> Dict[str, List]:
        try:
            model = _get_embeddings(
                getattr(Config, "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
            )
            query_vector = model.embed_query(query)

            semantic_results = self.db.semantic_search(
                query_vector=query_vector,
                collection_name=self.collection_name,
                limit=semantic_limit,
            )

            keyword_results = self.db.keyword_search(
                query=query,
                collection_name=self.collection_name,
                limit=keyword_limit,
            )
        except Exception:
            logger.exception("Hybrid retrieval failed for query=%r", query)
            raise

        # Filter by doc_id if provided (cross_doc=False path)
        if doc_id:
            semantic_results = [r for r in semantic_results if r.properties.get("doc_id") == doc_id]
            keyword_results = [r for r in keyword_results if r.properties.get("doc_id") == doc_id]

        # Deduplicate keyword results against semantic results by node_id
        seen_ids = {r.properties.get("node_id") for r in semantic_results}
        keyword_results = [r for r in keyword_results if r.properties.get("node_id") not in seen_ids]

        return {
            "query": query,
            "semantic_results": semantic_results,
            "keyword_results": keyword_results,
        }

    def close(self):
        try:
            self.db.close()
        except Exception:
            logger.exception("Failed to close WeaviateClient")