# retrieval/hybrid_search.py

import logging
from typing import Dict, List, Optional

from vectorstore.weaviate_client import DocuMindWeaviateClient
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
        self.db = DocuMindWeaviateClient()
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
            # Semantic search: high alpha = vector-weighted
            semantic_results = self.db.hybrid_search(
                query=query,
                limit=semantic_limit,
                doc_id=doc_id,
                alpha=0.9,
            )

            # Keyword search: low alpha = keyword-weighted
            keyword_results = self.db.hybrid_search(
                query=query,
                limit=keyword_limit,
                doc_id=doc_id,
                alpha=0.1,
            )
        except Exception:
            logger.exception("Hybrid retrieval failed for query=%r", query)
            raise
        finally:
            self.db.close()

        # Deduplicate keyword results against semantic results by node_id
        seen_ids = {r.get("node_id") for r in semantic_results}
        keyword_results = [r for r in keyword_results if r.get("node_id") not in seen_ids]

        return {
            "query": query,
            "semantic_results": semantic_results,
            "keyword_results": keyword_results,
        }

    def close(self):
        try:
            self.db.close()
        except Exception:
            logger.exception("Failed to close DocuMindWeaviateClient")
