# test_multi_doc.py
"""
Day 3 — Cross-Document Retrieval Test

Scenario:
  Doc A: Revenue growth
  Doc B: Cost increases
  Doc C: Risk warnings

Query: "Why did profit decrease despite revenue growth?"

Expected: Evidence package contains evidence from all three documents,
          cross_doc=True, documents_used=["doc_A", "doc_B", "doc_C"]
"""

import json
from retrieval.evidence_fusion import fuse_evidence

# --- Mock: HybridRetriever.retrieve(query=..., cross_doc=True) ---
# cross_doc=True -> no doc_id filter -> Weaviate returns nodes from all docs
hybrid_results = {
    "query": "Why did profit decrease despite revenue growth?",
    "cross_doc": True,
    "semantic_results": [
        {
            "node_id": "para_A01", "type": "paragraph", "page": 4,
            "doc_id": "doc_A", "score": 0.91,
            "content": "Revenue grew 18% YoY driven by strong performance in the APAC region.",
        },
        {
            "node_id": "table_B01", "type": "table", "page": 5,
            "doc_id": "doc_B", "score": 0.87,
            "content": "| Category | 2023 | 2024 |\n| Operating Expenses | $12M | $18M |\n| R&D Costs | $4M | $9M |",
        },
        {
            "node_id": "para_C01", "type": "paragraph", "page": 2,
            "doc_id": "doc_C", "score": 0.82,
            "content": "Critical risk: rising input costs may erode profit margins despite top-line growth.",
        },
    ],
    "keyword_results": [
        {
            "node_id": "para_B01", "type": "paragraph", "page": 3,
            "doc_id": "doc_B", "score": 0.74,
            "content": "Operating expenses rose 35% due to increased R&D and headcount costs.",
        },
    ],
}

# --- Mock: PositiveExpander.expand() ---
positive_expansion = {
    "seed_nodes": [
        {"node_id": "para_A01", "type": "paragraph", "page": 4, "doc_id": "doc_A",
         "content": "Revenue grew 18% YoY driven by strong performance in the APAC region."},
        {"node_id": "table_B01", "type": "table", "page": 5, "doc_id": "doc_B",
         "content": "| Category | 2023 | 2024 |\n| Operating Expenses | $12M | $18M |"},
    ],
    "evidence": [
        {
            "node": {"node_id": "heading_A01", "type": "heading", "page": 3,
                     "doc_id": "doc_A", "content": "Revenue Performance"},
            "relationship": "belongs_to", "depth": 1, "relevance_score": 0.667,
        },
        {
            "node": {"node_id": "image_B01", "type": "image", "page": 5,
                     "doc_id": "doc_B", "content": "Bar chart showing expense growth 2023 vs 2024."},
            "relationship": "figure_to_table", "depth": 1, "relevance_score": 0.667,
        },
    ],
    "stats": {"seeds": 2, "expanded_nodes": 2, "traversal_edges": 2, "max_depth_reached": 1},
}

# --- Mock: NegativeExpander.expand() ---
negative_expansion = {
    "exceptions": [
        {
            "node": {"node_id": "footnote_A01", "type": "footnote", "page": 4,
                     "doc_id": "doc_A", "content": "Excluding APAC region which reported 20% profit growth."},
            "edge_type": "exception_to", "risk_level": "Medium", "hop_distance": 1,
        },
    ],
    "contradictions": [
        {
            "node": {"node_id": "para_A02", "type": "paragraph", "page": 6,
                     "doc_id": "doc_A", "content": "Despite revenue growth, net profit fell 12% due to cost overruns."},
            "edge_type": "contradicts", "risk_level": "High", "hop_distance": 1,
        },
    ],
    "risks": [
        {
            "node": {"node_id": "para_C01", "type": "paragraph", "page": 2,
                     "doc_id": "doc_C", "content": "Critical risk: rising input costs may erode profit margins."},
            "edge_type": "risk_for", "risk_level": "High", "hop_distance": 1,
        },
    ],
    "warnings": [
        {
            "node": {"node_id": "para_C02", "type": "paragraph", "page": 3,
                     "doc_id": "doc_C", "content": "Warning: cost pressures are expected to persist into Q3 2025."},
            "edge_type": "warning_for", "risk_level": "Medium", "hop_distance": 1,
        },
    ],
    "limitations": [],
    "qualifications": [],
    "all_risk_nodes": [],
    "overall_risk_level": "High",
    "stats": {
        "total_risk_nodes": 4, "exceptions_count": 1, "contradictions_count": 1,
        "risks_count": 1, "warnings_count": 1, "limitations_count": 0,
    },
}

# --- Run fusion ---
print("Query:", hybrid_results["query"])
print("cross_doc: True\n")

evidence = fuse_evidence(hybrid_results, positive_expansion, negative_expansion)

print(json.dumps(evidence, indent=2))

# --- Assertions ---
print("\n--- Assertions ---")

assert evidence["cross_doc"] is True, "FAIL: cross_doc should be True"
print("PASS: cross_doc=True")

assert set(evidence["documents_used"]) == {"doc_A", "doc_B", "doc_C"}, \
    f"FAIL: documents_used={evidence['documents_used']}"
print(f"PASS: documents_used={evidence['documents_used']}")

assert evidence["stats"]["documents_retrieved"] == 3, \
    f"FAIL: documents_retrieved={evidence['stats']['documents_retrieved']}"
print(f"PASS: documents_retrieved=3")

assert evidence["stats"]["cross_doc"] is True, "FAIL: stats.cross_doc should be True"
print("PASS: stats.cross_doc=True")

assert len(evidence["supporting"]) > 0, "FAIL: supporting is empty"
print(f"PASS: supporting has {len(evidence['supporting'])} nodes")

assert len(evidence["exceptions"]) == 1, "FAIL: should have 1 exception"
print("PASS: exceptions=1")

assert len(evidence["contradictions"]) == 1, "FAIL: should have 1 contradiction"
print("PASS: contradictions=1")

assert len(evidence["risks"]) == 1, "FAIL: should have 1 risk"
print("PASS: risks=1")

assert len(evidence["warnings"]) == 1, "FAIL: should have 1 warning"
print("PASS: warnings=1")

assert evidence["overall_risk_level"] == "High", "FAIL: overall_risk_level should be High"
print("PASS: overall_risk_level=High")

# Verify no duplicate node_ids in supporting
supporting_ids = [n.get("node_id") for n in evidence["supporting"]]
assert len(supporting_ids) == len(set(supporting_ids)), "FAIL: duplicate node_ids in supporting"
print("PASS: no duplicate node_ids in supporting")

print("\nALL ASSERTIONS PASSED")
