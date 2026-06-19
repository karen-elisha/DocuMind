"""
negative_expansion.py — Negative Graph Expansion (Core Innovation)

Implements DocuMind's unique contribution: detecting and traversing
negative edges (exceptions, contradictions, risks) to surface hidden
qualifications that traditional RAG systems miss.

Expansion path:  Paragraph → Footnote → Exception → Risk → Contradiction

Author: Karen
"""

import re
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Set, Tuple

from graph.graph_engine import KnowledgeGraph, NEGATIVE_EDGE_TYPES


# ──────────────────────────────────────────────
# Negative-Edge Trigger Keyword Configuration
# ──────────────────────────────────────────────

# Each group maps a set of trigger keywords / phrases to:
#   - edge_type  : the negative edge type to create
#   - risk_level : default risk classification

NEGATIVE_KEYWORD_RULES: List[Dict[str, Any]] = [
    # Low risk — qualifications
    {
        "keywords": [
            "however",
            "note that",
            "although",
            "nonetheless",
            "nevertheless",
            "on the other hand",
            "that said",
            "it should be noted",
            "keep in mind",
            "bear in mind",
        ],
        "edge_type": "qualifies",
        "risk_level": "Low",
    },
    # Medium risk — exceptions
    {
        "keywords": [
            "except",
            "unless",
            "excluding",
            "with the exception of",
            "other than",
            "apart from",
            "aside from",
            "barring",
            "save for",
            "not including",
        ],
        "edge_type": "exception_to",
        "risk_level": "Medium",
    },
    # Medium risk — warnings & limitations
    {
        "keywords": [
            "warning",
            "limitation",
            "caution",
            "caveat",
            "constraint",
            "restricted",
            "subject to",
            "conditional upon",
            "only applicable",
            "limited to",
        ],
        "edge_type": "warning_for",
        "risk_level": "Medium",
    },
    {
        "keywords": [
            "limited",
            "may not",
            "does not guarantee",
            "no assurance",
            "cannot ensure",
            "not always",
            "in certain cases",
            "under specific conditions",
        ],
        "edge_type": "limitation_of",
        "risk_level": "Medium",
    },
    # High risk — contradictions
    {
        "keywords": [
            "contradicts",
            "contrary",
            "despite",
            "in contrast",
            "on the contrary",
            "conflicts with",
            "inconsistent with",
            "at odds with",
            "runs counter to",
            "opposes",
        ],
        "edge_type": "contradicts",
        "risk_level": "High",
    },
    # High risk — critical risks
    {
        "keywords": [
            "critical risk",
            "does not apply",
            "not applicable",
            "void",
            "invalidates",
            "supersedes",
            "overrides",
            "nullifies",
            "renders obsolete",
            "no longer valid",
            "material weakness",
            "significant doubt",
        ],
        "edge_type": "risk_for",
        "risk_level": "High",
    },
]

# Pre-compile keyword patterns for efficient matching
_COMPILED_RULES: List[Dict[str, Any]] = []
for rule in NEGATIVE_KEYWORD_RULES:
    patterns = [re.compile(re.escape(kw), re.IGNORECASE) for kw in rule["keywords"]]
    _COMPILED_RULES.append(
        {
            "patterns": patterns,
            "keywords": rule["keywords"],
            "edge_type": rule["edge_type"],
            "risk_level": rule["risk_level"],
        }
    )


class NegativeExpander:
    """
    Core innovation of DocuMind Graph.

    1. **Detection** — scans node content for trigger keywords and
       auto-creates negative edges in the knowledge graph.
    2. **Expansion** — traverses negative edges from seed nodes to
       collect risk evidence (exceptions, contradictions, risks).
    3. **Risk Aggregation** — computes overall risk level from all
       negative paths discovered.
    """

    def __init__(self, max_hops: int = 2, max_nodes: int = 50) -> None:
        """
        Parameters
        ----------
        max_hops  : int — maximum traversal depth for negative expansion
        max_nodes : int — cap on total risk nodes returned
        """
        self.max_hops = max_hops
        self.max_nodes = max_nodes

    # ══════════════════════════════════════════
    # 1. NEGATIVE EDGE DETECTION
    # ══════════════════════════════════════════

    def detect_negative_edges(
        self, graph: KnowledgeGraph
    ) -> List[Dict[str, Any]]:
        """
        Scan all nodes in the graph for negative trigger keywords and
        auto-create negative edges.

        Heuristic strategy:
        - When a node's content matches a trigger keyword, create a
          negative edge FROM that node TO each of its positive
          neighbors (the nodes it qualifies/contradicts/limits).
        - If the node is a footnote, also link it to paragraphs on
          the same page.

        Returns
        -------
        list of dicts describing edges created, each with:
            source, target, edge_type, risk_level, trigger_keyword
        """
        created_edges: List[Dict[str, Any]] = []

        for node_id in list(graph.graph.nodes):
            node = graph.get_node(node_id)
            if node is None:
                continue

            content = node.get("content", "")
            if not content:
                continue

            # Check content against all keyword rules
            matches = self._find_keyword_matches(content)

            if not matches:
                continue

            # Find target nodes for the negative edges
            targets = self._find_negative_targets(node_id, node, graph)

            for match in matches:
                for target_id in targets:
                    if target_id == node_id:
                        continue

                    # Avoid duplicate edges
                    if graph.graph.has_edge(node_id, target_id):
                        existing = graph.graph.edges[node_id, target_id]
                        if (
                            existing.get("polarity") == "negative"
                            and existing.get("edge_type") == match["edge_type"]
                        ):
                            continue

                    try:
                        graph.add_negative_edge(
                            source=node_id,
                            target=target_id,
                            edge_type=match["edge_type"],
                            risk_level=match["risk_level"],
                            metadata={
                                "trigger_keyword": match["keyword"],
                                "auto_detected": True,
                            },
                        )

                        created_edges.append(
                            {
                                "source": node_id,
                                "target": target_id,
                                "edge_type": match["edge_type"],
                                "risk_level": match["risk_level"],
                                "trigger_keyword": match["keyword"],
                            }
                        )
                    except ValueError:
                        # Skip if edge type validation fails
                        continue

        return created_edges

    def detect_and_report(
        self, graph: KnowledgeGraph
    ) -> Dict[str, Any]:
        """
        Run detection and return a summary report.

        Returns
        -------
        dict with:
            - edges_created     : list of created edge dicts
            - by_risk_level     : edges grouped by risk level
            - by_edge_type      : edges grouped by edge type
            - total_created     : int
        """
        edges = self.detect_negative_edges(graph)

        by_risk: Dict[str, List] = defaultdict(list)
        by_type: Dict[str, List] = defaultdict(list)

        for e in edges:
            by_risk[e["risk_level"]].append(e)
            by_type[e["edge_type"]].append(e)

        return {
            "edges_created": edges,
            "by_risk_level": dict(by_risk),
            "by_edge_type": dict(by_type),
            "total_created": len(edges),
        }

    # ══════════════════════════════════════════
    # 2. NEGATIVE EXPANSION
    # ══════════════════════════════════════════

    def expand(
        self,
        seed_node_ids: List[str],
        graph: KnowledgeGraph,
        hops: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Traverse negative edges from seed nodes to collect risk evidence.

        Expansion path: Paragraph → Footnote → Exception → Risk → Contradiction

        Parameters
        ----------
        seed_node_ids : list of str — starting node IDs
        graph         : KnowledgeGraph instance
        hops          : int, optional — override max_hops

        Returns
        -------
        dict with:
            - exceptions      : list of exception evidence
            - contradictions  : list of contradiction evidence
            - risks           : list of risk evidence
            - qualifications  : list of qualification evidence
            - warnings        : list of warning evidence
            - limitations     : list of limitation evidence
            - all_risk_nodes  : flat list of all risk-related nodes
            - traversal_paths : list of traversal path dicts
            - overall_risk_level : "Low", "Medium", or "High"
            - stats           : expansion statistics
        """
        max_depth = hops if hops is not None else self.max_hops

        visited: Set[str] = set()
        risk_nodes: List[Dict[str, Any]] = []
        traversal_paths: List[Dict[str, Any]] = []

        # Categorised evidence buckets
        categorized: Dict[str, List[Dict[str, Any]]] = {
            "exceptions": [],
            "contradictions": [],
            "risks": [],
            "qualifications": [],
            "warnings": [],
            "limitations": [],
        }

        # Edge type → category mapping
        type_to_category = {
            "exception_to": "exceptions",
            "contradicts": "contradictions",
            "risk_for": "risks",
            "qualifies": "qualifications",
            "warning_for": "warnings",
            "warns": "warnings",
            "limitation_of": "limitations",
            "limits": "limitations",
        }

        # BFS queue: (node_id, depth)
        queue: deque = deque()

        for sid in seed_node_ids:
            if graph.get_node(sid) is not None:
                visited.add(sid)
                queue.append((sid, 0))

        while queue and len(risk_nodes) < self.max_nodes:
            current_id, depth = queue.popleft()

            if depth >= max_depth:
                continue

            # Get negative edges from this node
            negative_edges = graph.get_edges(
                current_id, polarity="negative", direction="both"
            )

            for edge in negative_edges:
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

                visited.add(neighbor_id)
                next_depth = depth + 1

                edge_type = edge.get("edge_type", "unknown")
                risk_level = edge.get("risk_level", "Medium")

                risk_entry = {
                    "node": neighbor,
                    "edge_type": edge_type,
                    "risk_level": risk_level,
                    "hop_distance": next_depth,
                    "source_node": current_id,
                    "trigger_keyword": edge.get("metadata", {}).get(
                        "trigger_keyword", None
                    ),
                }

                risk_nodes.append(risk_entry)

                # Categorize
                category = type_to_category.get(edge_type)
                if category:
                    categorized[category].append(risk_entry)

                traversal_paths.append(
                    {
                        "source": current_id,
                        "edge_type": edge_type,
                        "target": neighbor_id,
                        "risk_level": risk_level,
                        "depth": next_depth,
                    }
                )

                # Continue BFS along negative edges
                queue.append((neighbor_id, next_depth))

        overall_risk = self.compute_risk_level(risk_nodes)

        return {
            **categorized,
            "all_risk_nodes": risk_nodes,
            "traversal_paths": traversal_paths,
            "overall_risk_level": overall_risk,
            "stats": {
                "total_risk_nodes": len(risk_nodes),
                "exceptions_count": len(categorized["exceptions"]),
                "contradictions_count": len(categorized["contradictions"]),
                "risks_count": len(categorized["risks"]),
                "qualifications_count": len(categorized["qualifications"]),
                "warnings_count": len(categorized["warnings"]),
                "limitations_count": len(categorized["limitations"]),
                "max_depth_reached": (
                    max((e["hop_distance"] for e in risk_nodes), default=0)
                ),
            },
        }

    def expand_single(
        self,
        seed_node_id: str,
        graph: KnowledgeGraph,
        hops: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Convenience: expand from a single seed node."""
        return self.expand([seed_node_id], graph, hops=hops)

    # ══════════════════════════════════════════
    # 3. RISK LEVEL AGGREGATION
    # ══════════════════════════════════════════

    @staticmethod
    def compute_risk_level(risk_nodes: List[Dict[str, Any]]) -> str:
        """
        Aggregate risk level from all negative paths.

        Strategy:
        - If ANY node has High risk → overall is High
        - If any node has Medium risk → overall is Medium
        - If only Low risk nodes → overall is Low
        - If no risk nodes → "None"

        Also considers density: many Medium risks can escalate to High.
        """
        if not risk_nodes:
            return "None"

        risk_counts = {"Low": 0, "Medium": 0, "High": 0}
        for node in risk_nodes:
            level = node.get("risk_level", "Medium")
            if level in risk_counts:
                risk_counts[level] += 1

        # Direct High risk
        if risk_counts["High"] > 0:
            return "High"

        # Density escalation: 3+ Medium risks → High
        if risk_counts["Medium"] >= 3:
            return "High"

        # Any Medium risk
        if risk_counts["Medium"] > 0:
            return "Medium"

        # Only Low risks
        if risk_counts["Low"] > 0:
            return "Low"

        return "None"

    @staticmethod
    def compute_confidence_adjustment(overall_risk: str) -> float:
        """
        Compute a confidence adjustment factor based on overall risk.

        This is used by the generation module to adjust answer
        confidence scores.

        Returns a value between 0 and 1 to multiply against
        base confidence.
        """
        adjustments = {
            "None": 1.0,
            "Low": 0.95,
            "Medium": 0.80,
            "High": 0.60,
        }
        return adjustments.get(overall_risk, 0.80)

    # ══════════════════════════════════════════
    # INTERNAL HELPERS
    # ══════════════════════════════════════════

    @staticmethod
    def _find_keyword_matches(content: str) -> List[Dict[str, str]]:
        """
        Scan text content against all compiled keyword rules.

        Returns a list of matches, each with:
            keyword, edge_type, risk_level
        """
        matches = []
        seen_types: Set[str] = set()

        for rule in _COMPILED_RULES:
            for pattern, keyword in zip(rule["patterns"], rule["keywords"]):
                if pattern.search(content):
                    # Only take the first match per edge_type to avoid
                    # creating excessive duplicate edges
                    if rule["edge_type"] not in seen_types:
                        matches.append(
                            {
                                "keyword": keyword,
                                "edge_type": rule["edge_type"],
                                "risk_level": rule["risk_level"],
                            }
                        )
                        seen_types.add(rule["edge_type"])
                    break  # One keyword per rule is enough

        return matches

    @staticmethod
    def _find_negative_targets(
        node_id: str,
        node: Dict[str, Any],
        graph: KnowledgeGraph,
    ) -> List[str]:
        """
        Determine which nodes should be targets of negative edges
        from a node that contains trigger keywords.

        Strategy:
        - All positive neighbors (the nodes this content qualifies)
        - For footnotes: paragraphs on the same page
        - For paragraphs: other paragraphs in the same section
          (potential contradiction targets)
        """
        targets: Set[str] = set()

        # 1. All positive neighbors
        positive_neighbors = graph.get_positive_neighbors(node_id)
        for neighbor in positive_neighbors:
            targets.add(neighbor["id"])

        node_type = node.get("type", "")
        node_page = node.get("page")
        node_section = node.get("section")
        node_doc = node.get("doc_id")

        # 2. Footnotes → paragraphs on same page
        if node_type == "footnote" and node_page is not None:
            for nid, attrs in graph.graph.nodes(data=True):
                if (
                    nid != node_id
                    and attrs.get("type") == "paragraph"
                    and attrs.get("page") == node_page
                    and (node_doc is None or attrs.get("doc_id") == node_doc)
                ):
                    targets.add(nid)

        # 3. If no targets found, link to nodes in same section
        if not targets and node_section:
            for nid, attrs in graph.graph.nodes(data=True):
                if (
                    nid != node_id
                    and attrs.get("section") == node_section
                    and (node_doc is None or attrs.get("doc_id") == node_doc)
                ):
                    targets.add(nid)

        return list(targets)

    def __repr__(self) -> str:
        return f"NegativeExpander(max_hops={self.max_hops}, max_nodes={self.max_nodes})"
