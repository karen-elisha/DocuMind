# retrieval/evidence_fusion.py
"""
Rakshitha — Day 2/3 Task: feature/evidence-fusion + feature/cross-doc-retrieval

Evidence Fusion takes:
  - Hybrid Search results      (from HybridRetriever.retrieve())
  - Positive Expansion results (from PositiveExpander.expand())
  - Negative Expansion results (from NegativeExpander.expand())

...and converts them into a single structured Evidence Package for the LLM.

Output:
{
  "supporting":         [...],
  "exceptions":         [...],
  "contradictions":     [...],
  "risks":              [...],
  "warnings":           [...],
  "limitations":        [...],
  "overall_risk_level": "None|Low|Medium|High",
  "seed_node_ids":      [...],
  "cross_doc":          True|False,
  "documents_used":     ["doc_A", "doc_B", ...],
  "stats": {
      "seeds":                int,
      "supporting_count":     int,
      "positive_expanded":    int,
      "risk_nodes_total":     int,
      "exceptions_count":     int,
      "contradictions_count": int,
      "risks_count":          int,
      "warnings_count":       int,
      "limitations_count":    int,
      "documents_retrieved":  int,
      "cross_doc":            True|False,
  }
}
"""

from typing import Any, Dict, List, Optional


def _get_id(node: Dict[str, Any]) -> Optional[str]:
    return node.get("node_id") or node.get("id")


def _collect_doc_ids(*node_lists: List[Dict[str, Any]]) -> List[str]:
    """Collect unique doc_ids from any number of node lists, preserving order."""
    seen = set()
    doc_ids = []
    for nodes in node_lists:
        for node in nodes:
            did = node.get("doc_id")
            if did and did not in seen:
                seen.add(did)
                doc_ids.append(did)
    return doc_ids


def fuse_evidence(
    hybrid_results: Dict[str, Any],
    positive_expansion: Dict[str, Any],
    negative_expansion: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Fuse pre-computed retrieval results into a structured Evidence Package.

    Parameters
    ----------
    hybrid_results     : output of HybridRetriever.retrieve()
                         expects keys: "semantic_results", "keyword_results", "cross_doc"
    positive_expansion : output of PositiveExpander.expand()
                         expects keys: "seed_nodes", "evidence", "stats"
    negative_expansion : output of NegativeExpander.expand()
                         expects keys: "exceptions", "contradictions", "risks",
                                       "warnings", "limitations",
                                       "overall_risk_level", "stats"

    Returns
    -------
    Structured Evidence Package dict ready for the generation layer.
    """
    cross_doc: bool = hybrid_results.get("cross_doc", False)

    # ── Supporting: seed nodes (hybrid search) + positive expansion ───
    seed_nodes: List[Dict[str, Any]] = (
        hybrid_results.get("semantic_results", [])
        + hybrid_results.get("keyword_results", [])
    )

    seen_ids: set = set()
    supporting: List[Dict[str, Any]] = []

    for node in seed_nodes:
        nid = _get_id(node)
        if nid and nid not in seen_ids:
            seen_ids.add(nid)
            supporting.append(node)

    for item in positive_expansion.get("evidence", []):
        node = item["node"]
        nid = _get_id(node)
        if nid and nid not in seen_ids:
            seen_ids.add(nid)
            supporting.append(node)

    # ── Seed node IDs (from positive expansion's seed_nodes) ──────────
    seed_node_ids: List[str] = [
        _get_id(n) for n in positive_expansion.get("seed_nodes", [])
        if _get_id(n)
    ]

    # ── Risk evidence from negative expansion ─────────────────────────
    def _extract(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [item["node"] for item in items]

    exceptions     = _extract(negative_expansion.get("exceptions", []))
    contradictions = _extract(negative_expansion.get("contradictions", []))
    risks          = _extract(negative_expansion.get("risks", []))
    warnings       = _extract(negative_expansion.get("warnings", []))
    limitations    = _extract(negative_expansion.get("limitations", []))

    # ── Collect unique doc_ids from ALL result sets ────────────────────
    pos_expanded_nodes = [item["node"] for item in positive_expansion.get("evidence", [])]
    neg_risk_nodes = exceptions + contradictions + risks + warnings + limitations

    documents_used: List[str] = _collect_doc_ids(
        hybrid_results.get("semantic_results", []),
        hybrid_results.get("keyword_results", []),
        pos_expanded_nodes,
        neg_risk_nodes,
    )

    # ── Edges from traversal paths ────────────────────────────────────
    edges: List[Dict[str, Any]] = (
        positive_expansion.get("traversal_paths", []) +
        negative_expansion.get("traversal_paths", [])
    )

    return {
        "supporting": supporting,
        "exceptions": exceptions,
        "contradictions": contradictions,
        "risks": risks,
        "warnings": warnings,
        "limitations": limitations,
        "edges": edges,
        "overall_risk_level": negative_expansion.get("overall_risk_level", "None"),
        "seed_node_ids": seed_node_ids,
        "cross_doc": cross_doc,
        "documents_used": documents_used,
        "stats": {
            "seeds": len(seed_node_ids),
            "supporting_count": len(supporting),
            "positive_expanded": positive_expansion.get("stats", {}).get("expanded_nodes", 0),
            "risk_nodes_total": negative_expansion.get("stats", {}).get("total_risk_nodes", 0),
            "exceptions_count": len(exceptions),
            "contradictions_count": len(contradictions),
            "risks_count": len(risks),
            "warnings_count": len(warnings),
            "limitations_count": len(limitations),
            "documents_retrieved": len(documents_used),
            "cross_doc": cross_doc,
        },
    }
