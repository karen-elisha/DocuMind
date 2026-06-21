import logging
from typing import Dict, List, Optional

from vectorstore.weaviate_client import DocuMindWeaviateClient
from config import Config

logger = logging.getLogger(__name__)


class HybridRetriever:
    def __init__(self):
        self.db = DocuMindWeaviateClient()
        self.collection_name = getattr(Config, "WEAVIATE_COLLECTION", "DocumentNode")

    def retrieve(
        self,
        query: str,
        semantic_limit: int = 50,
        keyword_limit: int = 50,
        doc_id: Optional[str] = None,
        cross_doc: bool = False,
    ) -> Dict[str, List]:
        filter_doc_id = None if cross_doc else doc_id

        try:
            # Pure vector search (alpha=1.0) — semantic similarity
            semantic_results = self.db.hybrid_search(
                query=query,
                limit=semantic_limit,
                doc_id=filter_doc_id,
                alpha=1.0,
            )

            # Pure BM25 keyword search (alpha=0.0) — lexical match
            keyword_results = self.db.hybrid_search(
                query=query,
                limit=keyword_limit,
                doc_id=filter_doc_id,
                alpha=0.0,
            )
        except Exception:
            logger.exception("Hybrid retrieval failed for query=%r", query)
            raise
        finally:
            self.db.close()

        seen_ids = {r.get("node_id") for r in semantic_results}
        keyword_results = [r for r in keyword_results if r.get("node_id") not in seen_ids]

        # Fallback: if both searches returned empty, fetch all nodes for the doc
        all_results_list = semantic_results + keyword_results
        if not all_results_list and not cross_doc and doc_id is not None:
            logger.info("Both searches returned empty for query=%r — fetching all nodes for doc_id=%s", query, doc_id)
            try:
                fallback_results = self.db.fetch_all(doc_id=doc_id, limit=50)
                semantic_results = fallback_results
            except Exception as fallback_exc:
                logger.warning("Fallback fetch_all failed: %s", fallback_exc)

        # Combine and sort by score descending
        combined = semantic_results + keyword_results
        combined.sort(key=lambda x: x.get("score", 0), reverse=True)

        return {
            "query": query,
            "cross_doc": cross_doc,
            "semantic_results": semantic_results,
            "keyword_results": keyword_results,
        }

    def close(self):
        try:
            self.db.close()
        except Exception:
            logger.exception("Failed to close DocuMindWeaviateClient")
