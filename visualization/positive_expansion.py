"""
positive_expansion.py — Positive Graph Expansion

Traverses supporting (positive) edges in the knowledge graph to gather
contextual evidence around seed nodes.

Expansion path:  Paragraph → Table → Heading → Image

Author: Karen
"""

from collections import deque
from typing import Any, Dict, List, Optional, Set

from graph.graph_engine import KnowledgeGraph


class PositiveExpander:
    """
    Performs BFS traversal along positive edges to collect supporting
    evidence for a set of seed nodes retrieved by hybrid search.

    Each expanded node receives a relevance score inversely proportional
    to its hop distance from the seed.
    """

    def __init__(self, max_hops: int = 2, max_nodes: int = 50) -> None:
        """
        Parameters
        ----------
        max_hops  : int — maximum BFS depth (default 2)
        max_nodes : int — cap on total nodes returned (default 50)
        """
        self.max_hops = max_hops
        self.max_nodes = max_nodes

    def expand(
        self,
        seed_node_ids: List[str],
        graph: KnowledgeGraph,
        hops: Optional[int] = None,
        filter_types: Optional[Set[str]] = None,
        filter_doc_id: Optional[str] = None,
        filter_section: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Expand seed nodes along positive edges using BFS.

        Parameters
        ----------
        seed_node_ids  : list of str — starting node IDs (from hybrid search)
        graph          : KnowledgeGraph instance
        hops           : int, optional — override max_hops for this call
        filter_types   : set of str, optional — only include nodes of these types
        filter_doc_id  : str, optional — restrict to a single document
        filter_section : str, optional — restrict to a single section

        Returns
        -------
        dict with keys:
            - seed_nodes       : list of seed node data
            - supporting_nodes : list of expanded node data with relevance scores
            - traversal_paths  : list of (source, edge_type, target) tuples
            - evidence         : list of structured evidence dicts
            - stats            : expansion statistics
        """
        max_depth = hops if hops is not None else self.max_hops

        visited: Set[str] = set()
        supporting_nodes: List[Dict[str, Any]] = []
        traversal_paths: List[Dict[str, Any]] = []
        evidence: List[Dict[str, Any]] = []

        # BFS queue: (node_id, depth)
        queue: deque = deque()

        # Initialize with seed nodes
        seed_data = []
        for sid in seed_node_ids:
            node = graph.get_node(sid)
            if node is None:
                continue
            seed_data.append(node)
            visited.add(sid)
            queue.append((sid, 0))

        # BFS traversal
        while queue and len(supporting_nodes) < self.max_nodes:
            current_id, depth = queue.popleft()

            if depth >= max_depth:
                continue

            # Get positive edges from this node
            positive_edges = graph.get_edges(
                current_id, polarity="positive", direction="both"
            )

            for edge in positive_edges:
                # Determine the neighbor node
                neighbor_id = (
                    edge["target"]
                    if edge["source"] == current_id
                    else edge["source"]
                )

                if neighbor_id in visited:
                    continue

                neighbor = graph.get_node(neighbor_id)
                if neighbor is None:
                    continue

                # Apply filters
                if not self._passes_filters(
                    neighbor, filter_types, filter_doc_id, filter_section
                ):
                    continue

                visited.add(neighbor_id)

                # Compute relevance score: closer nodes score higher
                next_depth = depth + 1
                relevance_score = self._compute_relevance(next_depth, max_depth)

                # Record the expansion
                node_with_score = dict(neighbor)
                node_with_score["relevance_score"] = relevance_score
                node_with_score["hop_distance"] = next_depth
                supporting_nodes.append(node_with_score)

                traversal_paths.append(
                    {
                        "source": current_id,
                        "edge_type": edge["edge_type"],
                        "target": neighbor_id,
                        "depth": next_depth,
                    }
                )

                evidence.append(
                    {
                        "node": neighbor,
                        "relationship": edge["edge_type"],
                        "depth": next_depth,
                        "relevance_score": relevance_score,
                        "source_node": current_id,
                    }
                )

                # Continue BFS
                queue.append((neighbor_id, next_depth))

        # Sort supporting nodes by relevance (highest first)
        supporting_nodes.sort(key=lambda n: n["relevance_score"], reverse=True)
        evidence.sort(key=lambda e: e["relevance_score"], reverse=True)

        return {
            "seed_nodes": seed_data,
            "supporting_nodes": supporting_nodes,
            "traversal_paths": traversal_paths,
            "evidence": evidence,
            "stats": {
                "seeds": len(seed_data),
                "expanded_nodes": len(supporting_nodes),
                "traversal_edges": len(traversal_paths),
                "max_depth_reached": (
                    max(
                        (e["depth"] for e in evidence),
                        default=0,
                    )
                ),
            },
        }

    def expand_single(
        self,
        seed_node_id: str,
        graph: KnowledgeGraph,
        hops: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Convenience method: expand from a single seed node.
        """
        return self.expand([seed_node_id], graph, hops=hops)

    def get_evidence_by_type(
        self, expansion_result: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Group the evidence from an expansion result by node type.

        Returns a dict like:
        {
            "paragraph": [...],
            "table": [...],
            "image": [...],
            ...
        }
        """
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for item in expansion_result.get("evidence", []):
            node_type = item["node"].get("type", "unknown")
            if node_type not in grouped:
                grouped[node_type] = []
            grouped[node_type].append(item)
        return grouped

    # ── Internal Helpers ─────────────────────

    @staticmethod
    def _compute_relevance(depth: int, max_depth: int) -> float:
        """
        Compute relevance score inversely proportional to hop distance.

        Score ranges from 1.0 (depth=1, closest) down to a minimum
        based on max_depth.  Seed nodes themselves are not scored
        (they are always relevant).
        """
        if max_depth <= 0:
            return 1.0
        return round(1.0 - (depth / (max_depth + 1)), 4)

    @staticmethod
    def _passes_filters(
        node: Dict[str, Any],
        filter_types: Optional[Set[str]],
        filter_doc_id: Optional[str],
        filter_section: Optional[str],
    ) -> bool:
        """Check whether a node passes all active filters."""
        if filter_types and node.get("type") not in filter_types:
            return False
        if filter_doc_id and node.get("doc_id") != filter_doc_id:
            return False
        if filter_section and node.get("section") != filter_section:
            return False
        return True

    def __repr__(self) -> str:
        return f"PositiveExpander(max_hops={self.max_hops}, max_nodes={self.max_nodes})"
