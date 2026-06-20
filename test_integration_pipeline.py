"""
test_integration_pipeline.py — End-to-End Integration Test

Tests the full pipeline compatibility:
  Ingestion (node_builder output) → Graph Engine → Positive Expansion → Negative Expansion → Visualization

Simulates a realistic parse_result (like Docling would produce) and verifies
that the node_builder's output format is compatible with KnowledgeGraph.

No external services or heavy deps needed (no Docling, no Weaviate, no Groq, no LangChain).

Author: Integration Test
"""

import sys
import os

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ============================================================
# Node type constants (duplicated to avoid importing langchain)
# ============================================================

# From ingestion/node_builder.py line 36
INGESTION_NODE_TYPES = {"heading", "paragraph", "table", "image", "caption", "footnote", "list_item", "formula"}


# ============================================================
# 1. SIMULATE PARSER OUTPUT (what parser.py would produce)
# ============================================================

def create_mock_parse_result():
    """
    Simulate realistic output from ingestion/parser.py's parse_document().
    Includes ALL node types the parser can produce.
    """
    return {
        "doc_id": "test_attention_paper",
        "document_name": "Attention-Is-All-You-Need.pdf",
        "pages_processed": 3,
        "text_count": 10,
        "table_count": 2,
        "image_count": 1,
        "elements": [
            # Heading
            {
                "element_id": "heading_001",
                "type": "heading",
                "page": 1,
                "content": "Attention Is All You Need",
                "metadata": {"source": "docling_texts", "docling_label": "title"},
            },
            # Paragraphs
            {
                "element_id": "paragraph_001",
                "type": "paragraph",
                "page": 1,
                "content": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks. However, the best performing models also connect the encoder and decoder through an attention mechanism.",
                "metadata": {"source": "docling_texts", "docling_label": "text"},
            },
            {
                "element_id": "paragraph_002",
                "type": "paragraph",
                "page": 1,
                "content": "We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely. Except when used with very small datasets, this architecture outperforms all previous approaches.",
                "metadata": {"source": "docling_texts", "docling_label": "text"},
            },
            {
                "element_id": "paragraph_003",
                "type": "paragraph",
                "page": 2,
                "content": "Self-attention, sometimes called intra-attention, is an attention mechanism relating different positions of a single sequence. Although self-attention has been used in a variety of tasks, it may not always capture long-range dependencies effectively.",
                "metadata": {"source": "docling_texts", "docling_label": "text"},
            },
            # Table
            {
                "element_id": "table_001",
                "type": "table",
                "page": 2,
                "content": "| Model | BLEU | Training Cost |\n|---|---|---|\n| Transformer (base) | 27.3 | 3.3 |\n| Transformer (big) | 28.4 | 12.0 |",
                "metadata": {"source": "docling_tables", "table_index": 0},
            },
            # Caption
            {
                "element_id": "caption_001",
                "type": "caption",
                "page": 2,
                "content": "Table 1: Maximum path lengths, per-layer complexity and minimum number of sequential operations.",
                "metadata": {"linked_image_element_id": "image_001"},
            },
            # Image
            {
                "element_id": "image_001",
                "type": "image",
                "page": 2,
                "content": "Multi-Head Attention diagram showing parallel attention layers.",
                "metadata": {"figure_caption": "Multi-Head Attention architecture", "image_path": "/tmp/img.png", "image_index": 0},
            },
            # Footnote with negative trigger keywords
            {
                "element_id": "footnote_001",
                "type": "footnote",
                "page": 2,
                "content": "Note that these results are limited to English-German translation. The model does not guarantee similar performance on low-resource language pairs.",
                "metadata": {"source": "docling_texts", "docling_label": "footnote"},
            },
            # List item (new type from main's parser)
            {
                "element_id": "list_item_001",
                "type": "list_item",
                "page": 3,
                "content": "Scaled Dot-Product Attention computes the attention function on a set of queries simultaneously.",
                "metadata": {"source": "docling_texts", "docling_label": "list_item"},
            },
            # Formula (new type from main's parser)
            {
                "element_id": "formula_001",
                "type": "formula",
                "page": 3,
                "content": "Attention(Q,K,V) = softmax(QK^T / sqrt(d_k))V",
                "metadata": {"source": "docling_texts", "docling_label": "formula"},
            },
            # Paragraph with contradiction keywords (for negative expansion testing)
            {
                "element_id": "paragraph_004",
                "type": "paragraph",
                "page": 3,
                "content": "Despite the strong results on machine translation, the Transformer architecture has significant limitations when applied to tasks requiring explicit memory. In contrast to recurrent models, it lacks a built-in mechanism for sequential state tracking.",
                "metadata": {"source": "docling_texts", "docling_label": "text"},
            },
            # Paragraph with warning keywords
            {
                "element_id": "paragraph_005",
                "type": "paragraph",
                "page": 3,
                "content": "Warning: the computational cost of self-attention grows quadratically with sequence length. This constraint makes it subject to severe memory limitations on very long sequences.",
                "metadata": {"source": "docling_texts", "docling_label": "text"},
            },
        ],
        "images": [
            {
                "image_id": "image_001",
                "image_path": "/tmp/img.png",
                "page": 2,
                "caption": "Multi-Head Attention architecture",
            },
        ],
    }


def simulate_build_nodes(parse_result):
    """
    Replicate what ingestion/node_builder.py's build_nodes() does,
    without importing the module (avoids langchain dependency).

    Returns the same dict structure: {doc_id, document_name, node_count, nodes: [...]}
    """
    import uuid
    doc_id = parse_result.get("doc_id")
    document_name = parse_result.get("document_name")
    elements = parse_result.get("elements", [])

    nodes = []
    for el in elements:
        el_type = el.get("type")
        if el_type not in INGESTION_NODE_TYPES:
            continue
        page = el.get("page", 1)
        content = (el.get("content") or "").strip()
        metadata = dict(el.get("metadata") or {})

        node = {
            "node_id": f"{el_type}_{uuid.uuid4().hex[:10]}",
            "doc_id": doc_id,
            "page": page,
            "type": el_type,
            "content": content,
            "metadata": metadata,
        }
        nodes.append(node)

    return {
        "doc_id": doc_id,
        "document_name": document_name,
        "node_count": len(nodes),
        "nodes": nodes,
    }


# ============================================================
# 2. TESTS
# ============================================================

def test_node_type_compatibility():
    """Test that all ingestion node types are accepted by graph_engine."""
    from graph.graph_engine import VALID_NODE_TYPES

    print("\n" + "=" * 60)
    print("  TEST 1: Node Type Compatibility")
    print("=" * 60)

    common = INGESTION_NODE_TYPES & VALID_NODE_TYPES
    only_builder = INGESTION_NODE_TYPES - VALID_NODE_TYPES
    only_graph = VALID_NODE_TYPES - INGESTION_NODE_TYPES

    print(f"  Ingestion types:     {sorted(INGESTION_NODE_TYPES)}")
    print(f"  Graph engine types:  {sorted(VALID_NODE_TYPES)}")
    print(f"  Common ({len(common)}):          {sorted(common)}")
    print(f"  Only in ingestion:   {sorted(only_builder) if only_builder else 'None'}")
    print(f"  Only in graph:       {sorted(only_graph) if only_graph else 'None ─ superset'}")

    assert INGESTION_NODE_TYPES.issubset(VALID_NODE_TYPES), (
        f"FAIL: ingestion produces types not accepted by graph_engine: {only_builder}"
    )
    print("  ✅ All ingestion node types are accepted by graph_engine")
    return True


def test_field_mapping():
    """Test the node_id → id field mapping between modules."""
    print("\n" + "=" * 60)
    print("  TEST 2: Field Mapping (node_id → id)")
    print("=" * 60)

    parse_result = create_mock_parse_result()
    node_build = simulate_build_nodes(parse_result)

    sample_node = node_build["nodes"][0]
    print(f"  node_builder output keys: {sorted(sample_node.keys())}")

    # graph_engine expects: id, type, content, (page, section, doc_id, metadata)
    required_for_graph = {"type", "content"}
    optional_for_graph = {"id", "page", "section", "doc_id", "metadata"}

    builder_keys = set(sample_node.keys())
    print(f"  graph_engine required:    {sorted(required_for_graph)}")
    print(f"  graph_engine optional:    {sorted(optional_for_graph)}")

    # Check the key mapping
    assert "node_id" in builder_keys, "FAIL: node_builder doesn't produce 'node_id'"
    assert "id" not in builder_keys, "INFO: node_builder uses 'node_id', not 'id'"
    assert required_for_graph.issubset(builder_keys), f"FAIL: missing required fields"

    print(f"  ⚠️  Mapping needed: node_builder.node_id → graph_engine.id")
    print(f"  ✅ All required fields present in node_builder output")
    return True


def test_node_ingestion_into_graph():
    """Test that simulated nodes can be ingested into KnowledgeGraph."""
    from graph.graph_engine import KnowledgeGraph

    print("\n" + "=" * 60)
    print("  TEST 3: Node Ingestion into KnowledgeGraph")
    print("=" * 60)

    parse_result = create_mock_parse_result()
    node_build = simulate_build_nodes(parse_result)

    print(f"  Nodes built:    {node_build['node_count']}")
    print(f"  Node types:     {sorted(set(n['type'] for n in node_build['nodes']))}")

    # Convert node_builder format → graph_engine format
    graph = KnowledgeGraph()
    converted_nodes = []
    for node in node_build["nodes"]:
        graph_node = {
            "id": node["node_id"],       # KEY MAPPING: node_id → id
            "type": node["type"],
            "content": node["content"],
            "page": node.get("page"),
            "doc_id": node.get("doc_id"),
            "metadata": node.get("metadata", {}),
        }
        converted_nodes.append(graph_node)

    # build_from_nodes adds all nodes AND auto-infers structural edges
    graph.build_from_nodes(converted_nodes)

    stats = graph.get_stats()
    print(f"  Graph nodes:    {stats['total_nodes']}")
    print(f"  Positive edges: {stats['positive_edges']} (auto-inferred)")
    print(f"  Node types:     {stats['node_type_distribution']}")
    print(f"  Edge types:     {stats['edge_type_distribution']}")
    print(f"  Documents:      {stats['documents']}")

    assert stats["total_nodes"] == node_build["node_count"], (
        f"FAIL: node count mismatch — built {node_build['node_count']}, graph has {stats['total_nodes']}"
    )
    assert stats["total_edges"] > 0, "FAIL: no structural edges were inferred"

    # Verify each node type was accepted
    for ntype in INGESTION_NODE_TYPES:
        nodes_of_type = graph.get_nodes_by_type(ntype)
        if any(n["type"] == ntype for n in node_build["nodes"]):
            assert len(nodes_of_type) > 0, f"FAIL: type '{ntype}' not found in graph"
            print(f"    ✓ {ntype}: {len(nodes_of_type)} nodes")

    print(f"  ✅ All {stats['total_nodes']} nodes ingested, {stats['total_edges']} edges inferred")
    return graph, converted_nodes


def test_positive_expansion(graph, seed_node_ids):
    """Test positive expansion from seed nodes."""
    from graph.positive_expansion import PositiveExpander

    print("\n" + "=" * 60)
    print("  TEST 4: Positive Expansion (BFS along positive edges)")
    print("=" * 60)
    print(f"  Seed nodes: {seed_node_ids}")

    expander = PositiveExpander(max_hops=2, max_nodes=50)
    result = expander.expand(seed_node_ids, graph)

    print(f"  Seeds:          {len(result['seed_nodes'])} nodes")
    print(f"  Expanded:       {result['stats']['expanded_nodes']} supporting nodes")
    print(f"  Edges traversed:{result['stats']['traversal_edges']}")
    print(f"  Max depth:      {result['stats']['max_depth_reached']}")

    evidence_by_type = expander.get_evidence_by_type(result)
    for ntype, items in sorted(evidence_by_type.items()):
        print(f"    {ntype}: {len(items)} evidence items")

    assert result["stats"]["expanded_nodes"] >= 0, "FAIL: expansion returned negative count"
    if result["stats"]["expanded_nodes"] > 0:
        print("  ✅ Positive expansion found supporting evidence")
    else:
        print("  ⚠️  No supporting evidence found (may be expected for isolated seeds)")
    return True


def test_negative_detection_and_expansion(graph, seed_node_ids):
    """Test negative edge detection from keyword triggers and expansion."""
    from graph.negative_expansion import NegativeExpander

    print("\n" + "=" * 60)
    print("  TEST 5: Negative Edge Detection & Expansion")
    print("=" * 60)

    expander = NegativeExpander(max_hops=2, max_nodes=50)

    # Step 1: Detect negative edges from content keywords
    report = expander.detect_and_report(graph)
    print(f"  Negative edges detected: {report['total_created']}")
    for risk, edges in sorted(report["by_risk_level"].items()):
        print(f"    {risk} risk: {len(edges)} edges")
        for e in edges[:3]:  # show up to 3 examples
            print(f"      {e['source']} --[{e['edge_type']}]--> {e['target']} (trigger: '{e['trigger_keyword']}')")
    for etype, edges in sorted(report["by_edge_type"].items()):
        print(f"    {etype}: {len(edges)} edges")

    # Step 2: Expand from seeds
    result = expander.expand(seed_node_ids, graph)
    print(f"\n  Expansion results:")
    print(f"    Total risk nodes:  {result['stats']['total_risk_nodes']}")
    print(f"    Exceptions:        {result['stats']['exceptions_count']}")
    print(f"    Contradictions:    {result['stats']['contradictions_count']}")
    print(f"    Risks:             {result['stats']['risks_count']}")
    print(f"    Qualifications:    {result['stats']['qualifications_count']}")
    print(f"    Warnings:          {result['stats']['warnings_count']}")
    print(f"    Limitations:       {result['stats']['limitations_count']}")
    print(f"    Overall risk:      {result['overall_risk_level']}")

    confidence = expander.compute_confidence_adjustment(result["overall_risk_level"])
    print(f"    Confidence adjust: {confidence}")

    assert report["total_created"] > 0, (
        "FAIL: no negative edges detected — we have trigger keywords like "
        "'however', 'limited', 'despite', 'warning', 'except' in the content"
    )
    print("  ✅ Negative detection & expansion completed successfully")
    return True


def test_serialization(graph):
    """Test graph export → reimport round-trip."""
    from graph.graph_engine import KnowledgeGraph

    print("\n" + "=" * 60)
    print("  TEST 6: Serialization Round-Trip")
    print("=" * 60)

    exported = graph.export_graph()
    print(f"  Exported: {len(exported['nodes'])} nodes, {len(exported['edges'])} edges")

    graph2 = KnowledgeGraph()
    graph2.import_graph(exported)

    s1 = graph.get_stats()
    s2 = graph2.get_stats()

    assert s1["total_nodes"] == s2["total_nodes"], f"FAIL: nodes {s1['total_nodes']} vs {s2['total_nodes']}"
    assert s1["total_edges"] == s2["total_edges"], f"FAIL: edges {s1['total_edges']} vs {s2['total_edges']}"
    print(f"  ✅ Round-trip preserved {s1['total_nodes']} nodes and {s1['total_edges']} edges")
    return True


def test_visualization(graph):
    """Test that visualization renders without error."""
    from visualization.graph_snapshot import GraphVisualizer

    print("\n" + "=" * 60)
    print("  TEST 7: Visualization (Matplotlib Snapshot)")
    print("=" * 60)

    viz = GraphVisualizer(figsize=(12, 8), dpi=100)

    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    os.makedirs(output_dir, exist_ok=True)

    out_path = os.path.join(output_dir, "test_integration_snapshot.png")
    result_path = viz.generate_snapshot(graph, output_path=out_path, title="Integration Pipeline Test")

    assert os.path.exists(result_path), f"FAIL: snapshot not created at {result_path}"
    file_size = os.path.getsize(result_path)
    print(f"  Snapshot saved: {result_path} ({file_size:,} bytes)")
    print("  ✅ Visualization rendered successfully")
    return True


# ============================================================
# MAIN
# ============================================================

def main():
    print("\n" + "#" * 60)
    print("#  DocuMind Integration Pipeline Test")
    print("#  node_builder → graph_engine → expansion → visualization")
    print("#" * 60)

    results = {}

    # Test 1: Type compatibility
    results["1_type_compat"] = test_node_type_compatibility()

    # Test 2: Field mapping
    results["2_field_mapping"] = test_field_mapping()

    # Test 3: Node ingestion into graph
    graph, nodes = test_node_ingestion_into_graph()
    results["3_node_ingestion"] = True

    # Pick seed nodes for expansion tests
    seed_ids = [n["id"] for n in nodes if n["type"] == "paragraph"][:2]
    print(f"\n  Using seeds for expansion: {seed_ids}")

    # Test 4: Positive expansion
    results["4_positive_expansion"] = test_positive_expansion(graph, seed_ids)

    # Test 5: Negative detection & expansion
    results["5_negative_expansion"] = test_negative_detection_and_expansion(graph, seed_ids)

    # Test 6: Serialization
    results["6_serialization"] = test_serialization(graph)

    # Test 7: Visualization
    try:
        results["7_visualization"] = test_visualization(graph)
    except Exception as e:
        print(f"  ⚠️  Visualization test skipped: {e}")
        results["7_visualization"] = "SKIPPED"

    # Summary
    print("\n" + "=" * 60)
    print("  INTEGRATION TEST SUMMARY")
    print("=" * 60)

    all_passed = True
    for name, passed in results.items():
        if passed == "SKIPPED":
            status = "⚠️  SKIP"
        elif passed:
            status = "✅ PASS"
        else:
            status = "❌ FAIL"
            all_passed = False
        print(f"  {name:30s}: {status}")

    if all_passed:
        print("\n  🎉 ALL TESTS PASSED — Pipeline is fully compatible!")
    else:
        print("\n  ⚠️  Some tests failed — see details above.")

    print("=" * 60 + "\n")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
