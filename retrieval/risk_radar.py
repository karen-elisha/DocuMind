"""Build Risk Radar graph payload for the frontend visualization."""

from __future__ import annotations

from typing import Any, Dict, List, Set

from graph.graph_engine import KnowledgeGraph


RISK_CONTENT_KEYWORDS = (
    "however", "except", "foreign currency", "adversely affect",
    "risk factor", "fluctuation", "exchange rate", "subject to",
    "limitation", "warning", "although", "note that",
)


def _synthetic_risk_from_evidence(seed_nodes: List[Dict[str, Any]]) -> tuple[List[Dict], List[Dict]]:
    """Fallback when graph traversal_paths are empty — detect risk language in evidence."""
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    seed_id = None

    for n in seed_nodes[:3]:
        nid = str(n.get("node_id") or n.get("id") or "")
        if nid:
            seed_id = nid
            nodes.append({
                "id": nid,
                "type": n.get("type", "paragraph"),
                "role": "seed",
                "page": n.get("page"),
                "label": _node_label(n),
            })
            break

    if not seed_id:
        return nodes, edges

    risk_idx = 0
    for n in seed_nodes:
        content = str(n.get("content") or "").lower()
        if not any(kw in content for kw in RISK_CONTENT_KEYWORDS):
            continue
        nid = str(n.get("node_id") or n.get("id") or f"risk_ev_{risk_idx}")
        if nid == seed_id:
            continue
        nodes.append({
            "id": nid,
            "type": n.get("type", "paragraph"),
            "role": "qualification",
            "page": n.get("page"),
            "label": _node_label(n),
            "risk_level": "Medium",
        })
        edges.append({
            "source": seed_id,
            "target": nid,
            "edge_type": "qualifies",
            "risk_level": "Medium",
            "polarity": "negative",
            "depth": 1,
        })
        risk_idx += 1
        if risk_idx >= 3:
            break

    return nodes, edges


def _node_label(node: Dict[str, Any], max_len: int = 50) -> str:
    content = str(node.get("content") or "")
    content = content.replace("\n", " ").strip()
    if len(content) > max_len:
        return content[:max_len] + "..."
    return content or str(node.get("type") or "node")


def _flatten_risk_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(entry.get("node"), dict):
        inner = dict(entry["node"])
        inner["edge_type"] = entry.get("edge_type")
        inner["risk_level"] = entry.get("risk_level")
        inner["role"] = "risk"
        return inner
    out = dict(entry)
    out["role"] = "risk"
    return out


def build_risk_radar(
    seed_nodes: List[Dict[str, Any]],
    neg_result: Dict[str, Any],
    kg: KnowledgeGraph,
) -> Dict[str, Any]:
    """
    Build a focused subgraph for Risk Radar UI:
    seed retrieval nodes → negative edges → risk/exception nodes.
    """
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()

    def _add_node(nid: str, attrs: Dict[str, Any], role: str) -> None:
        if nid in seen_ids:
            return
        seen_ids.add(nid)
        nodes.append({
            "id": nid,
            "type": attrs.get("type", "paragraph"),
            "role": role,
            "page": attrs.get("page"),
            "label": _node_label(attrs),
            "risk_level": attrs.get("risk_level"),
            "edge_type": attrs.get("edge_type"),
        })

    # Seed nodes from retrieval (top supporting evidence)
    for n in seed_nodes[:4]:
        nid = n.get("node_id") or n.get("id")
        if not nid:
            continue
        _add_node(str(nid), n, "seed")

    # Traversal paths from negative graph expansion
    for path in neg_result.get("traversal_paths", []):
        src = str(path.get("source", ""))
        tgt = str(path.get("target", ""))
        if not src or not tgt:
            continue

        src_attrs = kg.get_node(src) or {}
        tgt_attrs = kg.get_node(tgt) or {}

        if src_attrs:
            _add_node(src, src_attrs, "seed" if src in seen_ids else "bridge")
        if tgt_attrs:
            _add_node(tgt, {**tgt_attrs, "risk_level": path.get("risk_level"), "edge_type": path.get("edge_type")}, "risk")

        edges.append({
            "source": src,
            "target": tgt,
            "edge_type": path.get("edge_type", "negative"),
            "risk_level": path.get("risk_level", "Medium"),
            "polarity": "negative",
            "depth": path.get("depth", 1),
        })

    # Risk bucket nodes (when graph IDs don't match Weaviate chunks)
    if not edges:
        for bucket, role in [
            ("qualifications", "qualification"),
            ("exceptions", "exception"),
            ("warnings", "warning"),
            ("contradictions", "contradiction"),
            ("risks", "risk"),
        ]:
            for i, entry in enumerate(neg_result.get(bucket, [])[:3]):
                flat = _flatten_risk_entry(entry)
                nid = flat.get("node_id") or flat.get("id") or f"{bucket}_{i}"
                _add_node(str(nid), flat, role)
                if nodes and nodes[0]["role"] == "seed":
                    edges.append({
                        "source": nodes[0]["id"],
                        "target": str(nid),
                        "edge_type": flat.get("edge_type", bucket),
                        "risk_level": flat.get("risk_level", "Medium"),
                        "polarity": "negative",
                        "depth": 1,
                    })

    # Synthetic fallback from risk language in retrieved evidence
    if not edges and seed_nodes:
        syn_nodes, syn_edges = _synthetic_risk_from_evidence(seed_nodes)
        for sn in syn_nodes:
            if sn["id"] not in seen_ids:
                nodes.append(sn)
                seen_ids.add(sn["id"])
        edges.extend(syn_edges)

    overall = neg_result.get("overall_risk_level", "None")
    active = len(edges) > 0
    if not active and overall not in ("None", "", "Low"):
        active = True
    if active and overall in ("None", ""):
        overall = "Medium" if edges else overall

    trigger_keywords = _collect_trigger_keywords(neg_result)
    if not trigger_keywords and active:
        trigger_keywords = ["foreign currency", "exchange rate", "risk factor"]

    return {
        "active": active,
        "overall_risk_level": overall,
        "nodes": nodes,
        "edges": edges,
        "stats": neg_result.get("stats", {}),
        "trigger_keywords": trigger_keywords[:5],
    }


def _collect_trigger_keywords(neg_result: Dict[str, Any]) -> List[str]:
    keywords: List[str] = []
    for entry in neg_result.get("all_risk_nodes", []):
        kw = entry.get("trigger_keyword")
        if kw and kw not in keywords:
            keywords.append(kw)
    return keywords
