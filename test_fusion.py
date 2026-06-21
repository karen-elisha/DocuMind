# test_fusion.py
"""
Tests evidence_fusion.fuse_evidence() with mock inputs.
No Weaviate, no Groq needed.
"""

import json
from retrieval.evidence_fusion import fuse_evidence

# --- Mock Hybrid Search output (what HybridRetriever.retrieve() returns) ---
hybrid_results = {
    "query": "What does the decoder do?",
    "semantic_results": [
        {"node_id": "para_001", "type": "paragraph", "page": 1, "doc_id": "doc_A",
         "content": "The decoder generates output sequences using attention over encoder outputs."},
        {"node_id": "table_001", "type": "table", "page": 2, "doc_id": "doc_A",
         "content": "| Layer | Input | Output |\n| Decoder | Query | Token |"},
    ],
    "keyword_results": [
        {"node_id": "para_002", "type": "paragraph", "page": 3, "doc_id": "doc_A",
         "content": "However, the decoder has limitations on very long sequences."},
    ],
}

# --- Mock Positive Expansion output (what PositiveExpander.expand() returns) ---
positive_expansion = {
    "seed_nodes": [
        {"node_id": "para_001", "type": "paragraph", "page": 1, "doc_id": "doc_A",
         "content": "The decoder generates output sequences using attention over encoder outputs."},
    ],
    "evidence": [
        {
            "node": {"node_id": "heading_001", "type": "heading", "page": 1,
                     "doc_id": "doc_A", "content": "Decoder Architecture"},
            "relationship": "belongs_to",
            "depth": 1,
            "relevance_score": 0.667,
        },
        {
            "node": {"node_id": "image_001", "type": "image", "page": 2,
                     "doc_id": "doc_A", "content": "Diagram of multi-head attention in decoder."},
            "relationship": "paragraph_to_figure",
            "depth": 1,
            "relevance_score": 0.667,
        },
    ],
    "stats": {"seeds": 1, "expanded_nodes": 2, "traversal_edges": 2, "max_depth_reached": 1},
}

# --- Mock Negative Expansion output (what NegativeExpander.expand() returns) ---
negative_expansion = {
    "exceptions": [
        {
            "node": {"node_id": "footnote_001", "type": "footnote", "page": 3,
                     "doc_id": "doc_A", "content": "Except when sequence length exceeds 512 tokens."},
            "edge_type": "exception_to", "risk_level": "Medium", "hop_distance": 1,
        }
    ],
    "contradictions": [],
    "risks": [],
    "warnings": [
        {
            "node": {"node_id": "para_002", "type": "paragraph", "page": 3,
                     "doc_id": "doc_A", "content": "Warning: decoder performance degrades on long sequences."},
            "edge_type": "warning_for", "risk_level": "Medium", "hop_distance": 1,
        }
    ],
    "limitations": [
        {
            "node": {"node_id": "para_003", "type": "paragraph", "page": 4,
                     "doc_id": "doc_A", "content": "Limited to fixed-length positional encodings."},
            "edge_type": "limitation_of", "risk_level": "Medium", "hop_distance": 1,
        }
    ],
    "qualifications": [],
    "all_risk_nodes": [],
    "overall_risk_level": "Medium",
    "stats": {
        "total_risk_nodes": 3, "exceptions_count": 1, "contradictions_count": 0,
        "risks_count": 0, "warnings_count": 1, "limitations_count": 1,
    },
}

# --- Run fusion ---
evidence = fuse_evidence(hybrid_results, positive_expansion, negative_expansion)

print(json.dumps(evidence, indent=2))
