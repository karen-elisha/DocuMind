# retrieval/evidence_fusion.py
"""
Rakshitha — Day 2 Task: feature/evidence-fusion

Evidence Fusion takes:
  - Hybrid Search results     (from HybridRetriever.retrieve())
  - Positive Expansion results (from PositiveExpander.expand())
  - Negative Expansion results (from NegativeExpander.expand())

...and converts them into a single structured Evidence Package for the LLM.

Output:
{
  "supporting":         [...],  # seed nodes + positively expanded nodes
  "exceptions":         [...],
  "contradictions":     [...],
  "risks":              [...],
  "warnings":           [...],
  "limitations":        [...],
  "overall_risk_level": "None|Low|Medium|High",
  "seed_node_ids":      [...],
  "stats":              {...}
}
"""

from typing import Any, Dict, List, Optional


def _get_id(node: Dict[str, Any]) -> Optional[str]:
    return node.get("node_id") or node.get("id")


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
                         expects keys: "semantic_results", "keyword_results"
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

    # ── Supporting: seed nodes (hybrid search) + positive expansion ───
    seed_nodes: List[Dict[str, Any]] = (
        hybrid_results.get("semantic_results", [])
        + hybrid_results.get("keyword_results", [])
    )

    seen_ids = set()
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

    return {
        "supporting": supporting,
        "exceptions": exceptions,
        "contradictions": contradictions,
        "risks": risks,
        "warnings": warnings,
        "limitations": limitations,
        "overall_risk_level": negative_expansion.get("overall_risk_level", "None"),
        "seed_node_ids": seed_node_ids,
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
        },
    }
