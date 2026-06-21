"""
graph_engine.py — Core Knowledge Graph Engine

Wraps NetworkX DiGraph to provide a structured knowledge graph with:
- 8 semantic node types (heading, paragraph, table, image, figure, caption, footnote, chart)
- Positive edges (supporting relationships)
- Negative edges (risk/exception relationships)
- Cross-document edge support
- Serialization for API integration

Author: Karen
"""

import json
import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx


# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────

VALID_NODE_TYPES = {
    "heading",
    "paragraph",
    "table",
    "image",
    "figure",
    "caption",
    "footnote",
    "chart",
    "list_item",   # Added for ingestion pipeline compatibility
    "formula",     # Added for ingestion pipeline compatibility
}

POSITIVE_EDGE_TYPES = {
    "belongs_to",
    "references",
    "follows",
    "describes",
    "has_footnote",
    "caption_to_image",
    "paragraph_to_figure",
    "figure_to_table",
}

NEGATIVE_EDGE_TYPES = {
    "exception_to",
    "contradicts",
    "limits",
    "warns",
    "risk_for",
    "qualifies",
    "limitation_of",
    "warning_for",
}

RISK_LEVELS = {"Low", "Medium", "High"}


class KnowledgeGraph:
    """
    Structural memory layer built on NetworkX.

    Manages semantic nodes extracted from documents and the positive /
    negative edges that connect them.  Provides traversal helpers used
    by PositiveExpander and NegativeExpander.
    """

    def __init__(self) -> None:
        self._graph: nx.DiGraph = nx.DiGraph()
        self._doc_index: Dict[str, Set[str]] = defaultdict(set)  # doc_id -> node_ids

    # ── Properties ────────────────────────────

    @property
    def graph(self) -> nx.DiGraph:
        """Direct access to the underlying NetworkX DiGraph."""
        return self._graph

    @property
    def node_count(self) -> int:
        return self._graph.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self._graph.number_of_edges()

    @property
    def doc_ids(self) -> List[str]:
        """Return all document IDs present in the graph."""
        return list(self._doc_index.keys())

    # ── Node Operations ──────────────────────

    def add_semantic_node(self, node_data: Dict[str, Any]) -> str:
        """
        Add a semantic node to the knowledge graph.

        Parameters
        ----------
        node_data : dict
            Must contain at minimum:
                - id   : str — unique identifier (e.g. "para_12")
                - type : str — one of VALID_NODE_TYPES
                - content : str — textual content of the node
            Optional fields:
                - page     : int
                - section  : str
                - doc_id   : str
                - metadata : dict — arbitrary extra metadata

        Returns
        -------
        str : the node ID that was added.

        Raises
        ------
        ValueError : if required fields are missing or type is invalid.
        """
        node_id = node_data.get("id")
        node_type = node_data.get("type", "").lower()

        if not node_id:
            node_id = f"{node_type}_{uuid.uuid4().hex[:8]}"
            node_data["id"] = node_id

        if node_type not in VALID_NODE_TYPES:
            raise ValueError(
                f"Invalid node type '{node_type}'. "
                f"Must be one of {sorted(VALID_NODE_TYPES)}"
            )

        if "content" not in node_data:
            raise ValueError("Node data must include a 'content' field.")

        attrs = {
            "type": node_type,
            "content": node_data["content"],
            "page": node_data.get("page"),
            "section": node_data.get("section"),
            "doc_id": node_data.get("doc_id"),
            "metadata": node_data.get("metadata", {}),
        }

        self._graph.add_node(node_id, **attrs)

        # Index by doc_id for cross-document lookups
        doc_id = attrs.get("doc_id")
        if doc_id:
            self._doc_index[doc_id].add(node_id)

        return node_id

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a node and all its attributes.

        Returns None if the node does not exist.
        """
        if node_id not in self._graph:
            return None
        data = dict(self._graph.nodes[node_id])
        data["id"] = node_id
        return data

    def get_nodes_by_type(self, node_type: str) -> List[Dict[str, Any]]:
        """Return all nodes of a given type."""
        results = []
        for nid, attrs in self._graph.nodes(data=True):
            if attrs.get("type") == node_type:
                node = dict(attrs)
                node["id"] = nid
                results.append(node)
        return results

    def get_nodes_by_doc(self, doc_id: str) -> List[Dict[str, Any]]:
        """Return all nodes belonging to a specific document."""
        results = []
        for nid in self._doc_index.get(doc_id, set()):
            node = self.get_node(nid)
            if node:
                results.append(node)
        return results

    # ── Edge Operations ──────────────────────

    def add_positive_edge(
        self,
        source: str,
        target: str,
        edge_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add a positive (supporting) edge between two nodes.

        Parameters
        ----------
        source    : str — source node ID
        target    : str — target node ID
        edge_type : str — one of POSITIVE_EDGE_TYPES
        metadata  : dict, optional — additional edge metadata
        """
        if edge_type not in POSITIVE_EDGE_TYPES:
            raise ValueError(
                f"Invalid positive edge type '{edge_type}'. "
                f"Must be one of {sorted(POSITIVE_EDGE_TYPES)}"
            )
        self._validate_nodes_exist(source, target)

        self._graph.add_edge(
            source,
            target,
            edge_type=edge_type,
            polarity="positive",
            metadata=metadata or {},
        )

    def add_negative_edge(
        self,
        source: str,
        target: str,
        edge_type: str,
        risk_level: str = "Medium",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add a negative (risk / exception) edge between two nodes.

        Parameters
        ----------
        source     : str — source node ID
        target     : str — target node ID
        edge_type  : str — one of NEGATIVE_EDGE_TYPES
        risk_level : str — "Low", "Medium", or "High"
        metadata   : dict, optional — additional edge metadata
        """
        if edge_type not in NEGATIVE_EDGE_TYPES:
            raise ValueError(
                f"Invalid negative edge type '{edge_type}'. "
                f"Must be one of {sorted(NEGATIVE_EDGE_TYPES)}"
            )
        if risk_level not in RISK_LEVELS:
            raise ValueError(
                f"Invalid risk level '{risk_level}'. Must be one of {sorted(RISK_LEVELS)}"
            )
        self._validate_nodes_exist(source, target)

        self._graph.add_edge(
            source,
            target,
            edge_type=edge_type,
            polarity="negative",
            risk_level=risk_level,
            metadata=metadata or {},
        )

    def get_edges(
        self, node_id: str, polarity: Optional[str] = None, direction: str = "both"
    ) -> List[Dict[str, Any]]:
        """
        Get edges connected to a node, optionally filtered by polarity.

        Parameters
        ----------
        node_id   : str
        polarity  : "positive", "negative", or None (all)
        direction : "outgoing", "incoming", or "both"

        Returns
        -------
        List of edge dicts with keys: source, target, edge_type, polarity, ...
        """
        edges = []

        if direction in ("outgoing", "both"):
            for _, tgt, data in self._graph.out_edges(node_id, data=True):
                if polarity is None or data.get("polarity") == polarity:
                    edge = dict(data)
                    edge["source"] = node_id
                    edge["target"] = tgt
                    edges.append(edge)

        if direction in ("incoming", "both"):
            for src, _, data in self._graph.in_edges(node_id, data=True):
                if polarity is None or data.get("polarity") == polarity:
                    edge = dict(data)
                    edge["source"] = src
                    edge["target"] = node_id
                    edges.append(edge)

        return edges

    # ── Neighbor Lookups ─────────────────────

    def get_neighbors(
        self, node_id: str, polarity: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get neighboring nodes, optionally filtered by edge polarity.

        Returns a list of node dicts (with 'id' field) connected via
        edges matching the given polarity.
        """
        neighbor_ids: Set[str] = set()

        for edge in self.get_edges(node_id, polarity=polarity):
            other = edge["target"] if edge["source"] == node_id else edge["source"]
            neighbor_ids.add(other)

        return [self.get_node(nid) for nid in neighbor_ids if self.get_node(nid)]

    def get_positive_neighbors(self, node_id: str) -> List[Dict[str, Any]]:
        """Shortcut for get_neighbors with polarity='positive'."""
        return self.get_neighbors(node_id, polarity="positive")

    def get_negative_neighbors(self, node_id: str) -> List[Dict[str, Any]]:
        """Shortcut for get_neighbors with polarity='negative'."""
        return self.get_neighbors(node_id, polarity="negative")

    # ── Subgraph Extraction ──────────────────

    def get_subgraph(self, node_ids: List[str]) -> "KnowledgeGraph":
        """
        Extract a subgraph containing only the specified nodes and
        edges between them.  Returns a new KnowledgeGraph instance.
        """
        sub = KnowledgeGraph()
        sub._graph = self._graph.subgraph(node_ids).copy()

        # Rebuild doc index for the subgraph
        for nid in sub._graph.nodes:
            doc_id = sub._graph.nodes[nid].get("doc_id")
            if doc_id:
                sub._doc_index[doc_id].add(nid)

        return sub

    # ── Cross-Document Support ───────────────

    def get_cross_doc_edges(self, doc_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Return edges that span across different documents.

        If *doc_id* is given, only return cross-doc edges involving
        that document.
        """
        cross_edges = []

        for src, tgt, data in self._graph.edges(data=True):
            src_doc = self._graph.nodes[src].get("doc_id")
            tgt_doc = self._graph.nodes[tgt].get("doc_id")

            if src_doc and tgt_doc and src_doc != tgt_doc:
                if doc_id is None or doc_id in (src_doc, tgt_doc):
                    edge = dict(data)
                    edge["source"] = src
                    edge["target"] = tgt
                    edge["source_doc"] = src_doc
                    edge["target_doc"] = tgt_doc
                    cross_edges.append(edge)

        return cross_edges

    def add_cross_doc_edge(
        self,
        source: str,
        target: str,
        edge_type: str,
        polarity: str = "positive",
        risk_level: str = "Medium",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Convenience method for adding an edge between nodes from
        different documents.  Validates that nodes belong to
        different doc_ids.
        """
        self._validate_nodes_exist(source, target)

        src_doc = self._graph.nodes[source].get("doc_id")
        tgt_doc = self._graph.nodes[target].get("doc_id")

        if src_doc == tgt_doc:
            raise ValueError(
                f"Both nodes belong to the same document '{src_doc}'. "
                "Use add_positive_edge or add_negative_edge instead."
            )

        edge_attrs = {
            "edge_type": edge_type,
            "polarity": polarity,
            "cross_document": True,
            "metadata": metadata or {},
        }
        if polarity == "negative":
            edge_attrs["risk_level"] = risk_level

        self._graph.add_edge(source, target, **edge_attrs)

    # ── Graph Construction from Ingested Nodes ─

    def build_from_nodes(self, nodes_list: List[Dict[str, Any]]) -> None:
        """
        Auto-construct the graph from a list of ingested semantic nodes.

        Infers structural (positive) edges based on:
        - Page proximity and section membership
        - Type relationships (caption→image, paragraph→figure, etc.)
        - Sequential ordering (follows edges)
        - Footnote associations

        Parameters
        ----------
        nodes_list : list of dict
            Each dict must contain at least 'id', 'type', 'content'.
            Optional: 'page', 'section', 'doc_id', 'metadata'.
        """
        # 1. Add all nodes
        for node_data in nodes_list:
            self.add_semantic_node(node_data)

        # 2. Group nodes by document and section for structural inference
        doc_section_map: Dict[str, Dict[str, List[str]]] = defaultdict(
            lambda: defaultdict(list)
        )
        doc_page_map: Dict[str, Dict[int, List[str]]] = defaultdict(
            lambda: defaultdict(list)
        )

        for node_data in nodes_list:
            nid = node_data["id"]
            doc_id = node_data.get("doc_id", "default")
            section = node_data.get("section", "default")
            page = node_data.get("page")

            doc_section_map[doc_id][section].append(nid)
            if page is not None:
                doc_page_map[doc_id][page].append(nid)

        # 3. Infer structural edges
        self._infer_belongs_to_edges(doc_section_map)
        self._infer_follows_edges(doc_section_map)
        self._infer_type_based_edges(doc_page_map)

    def _infer_belongs_to_edges(
        self, doc_section_map: Dict[str, Dict[str, List[str]]]
    ) -> None:
        """Link non-heading nodes to their section heading via 'belongs_to'."""
        for doc_id, sections in doc_section_map.items():
            for section, node_ids in sections.items():
                # Find heading nodes in this section
                headings = [
                    nid
                    for nid in node_ids
                    if self._graph.nodes[nid].get("type") == "heading"
                ]
                non_headings = [
                    nid
                    for nid in node_ids
                    if self._graph.nodes[nid].get("type") != "heading"
                ]

                for heading_id in headings:
                    for nid in non_headings:
                        self._graph.add_edge(
                            nid,
                            heading_id,
                            edge_type="belongs_to",
                            polarity="positive",
                            metadata={"inferred": True},
                        )

    def _infer_follows_edges(
        self, doc_section_map: Dict[str, Dict[str, List[str]]]
    ) -> None:
        """Link sequential nodes within the same section via 'follows'."""
        for doc_id, sections in doc_section_map.items():
            for section, node_ids in sections.items():
                for i in range(len(node_ids) - 1):
                    self._graph.add_edge(
                        node_ids[i],
                        node_ids[i + 1],
                        edge_type="follows",
                        polarity="positive",
                        metadata={"inferred": True},
                    )

    def _infer_type_based_edges(
        self, doc_page_map: Dict[str, Dict[int, List[str]]]
    ) -> None:
        """Infer edges based on node type co-occurrence on the same page."""
        for doc_id, pages in doc_page_map.items():
            for page, node_ids in pages.items():
                # Collect nodes by type on this page
                by_type: Dict[str, List[str]] = defaultdict(list)
                for nid in node_ids:
                    ntype = self._graph.nodes[nid].get("type")
                    by_type[ntype].append(nid)

                # caption → image / figure
                for cap_id in by_type.get("caption", []):
                    for img_id in by_type.get("image", []) + by_type.get("figure", []):
                        self._graph.add_edge(
                            cap_id,
                            img_id,
                            edge_type="caption_to_image",
                            polarity="positive",
                            metadata={"inferred": True, "page": page},
                        )

                # paragraph → figure
                for para_id in by_type.get("paragraph", []):
                    for fig_id in by_type.get("figure", []) + by_type.get("image", []):
                        self._graph.add_edge(
                            para_id,
                            fig_id,
                            edge_type="paragraph_to_figure",
                            polarity="positive",
                            metadata={"inferred": True, "page": page},
                        )

                # figure → table (describes relationship)
                for fig_id in by_type.get("figure", []) + by_type.get("chart", []):
                    for tbl_id in by_type.get("table", []):
                        self._graph.add_edge(
                            fig_id,
                            tbl_id,
                            edge_type="figure_to_table",
                            polarity="positive",
                            metadata={"inferred": True, "page": page},
                        )

                # paragraph → footnote
                for para_id in by_type.get("paragraph", []):
                    for fn_id in by_type.get("footnote", []):
                        self._graph.add_edge(
                            para_id,
                            fn_id,
                            edge_type="has_footnote",
                            polarity="positive",
                            metadata={"inferred": True, "page": page},
                        )

    # ── Serialization ────────────────────────

    def export_graph(self) -> Dict[str, Any]:
        """
        Serialize the knowledge graph to a JSON-compatible dict.

        Returns
        -------
        dict with 'nodes' and 'edges' keys.
        """
        nodes = []
        for nid, attrs in self._graph.nodes(data=True):
            node = dict(attrs)
            node["id"] = nid
            nodes.append(node)

        edges = []
        for src, tgt, data in self._graph.edges(data=True):
            edge = dict(data)
            edge["source"] = src
            edge["target"] = tgt
            edges.append(edge)

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "node_count": self.node_count,
                "edge_count": self.edge_count,
                "doc_ids": self.doc_ids,
            },
        }

    def import_graph(self, data: Dict[str, Any]) -> None:
        """
        Deserialize and load a knowledge graph from a dict produced
        by export_graph().

        This replaces the current graph contents.
        """
        self._graph.clear()
        self._doc_index.clear()

        for node in data.get("nodes", []):
            self.add_semantic_node(node)

        for edge in data.get("edges", []):
            polarity = edge.get("polarity", "positive")
            src = edge["source"]
            tgt = edge["target"]
            edge_type = edge["edge_type"]

            if polarity == "positive":
                self.add_positive_edge(src, tgt, edge_type, edge.get("metadata"))
            else:
                self.add_negative_edge(
                    src,
                    tgt,
                    edge_type,
                    edge.get("risk_level", "Medium"),
                    edge.get("metadata"),
                )

    def export_json(self, filepath: str) -> None:
        """Export the graph to a JSON file."""
        data = self.export_graph()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def import_json(self, filepath: str) -> None:
        """Import the graph from a JSON file."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.import_graph(data)

    # ── Graph Statistics ─────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics about the knowledge graph."""
        type_counts: Dict[str, int] = defaultdict(int)
        for _, attrs in self._graph.nodes(data=True):
            type_counts[attrs.get("type", "unknown")] += 1

        positive_count = sum(
            1
            for _, _, d in self._graph.edges(data=True)
            if d.get("polarity") == "positive"
        )
        negative_count = sum(
            1
            for _, _, d in self._graph.edges(data=True)
            if d.get("polarity") == "negative"
        )

        edge_type_counts: Dict[str, int] = defaultdict(int)
        for _, _, d in self._graph.edges(data=True):
            edge_type_counts[d.get("edge_type", "unknown")] += 1

        return {
            "total_nodes": self.node_count,
            "total_edges": self.edge_count,
            "node_type_distribution": dict(type_counts),
            "positive_edges": positive_count,
            "negative_edges": negative_count,
            "edge_type_distribution": dict(edge_type_counts),
            "documents": self.doc_ids,
            "cross_doc_edges": len(self.get_cross_doc_edges()),
        }

    # ── Internal Helpers ─────────────────────

    def _validate_nodes_exist(self, *node_ids: str) -> None:
        """Raise ValueError if any node IDs are not in the graph."""
        for nid in node_ids:
            if nid not in self._graph:
                raise ValueError(f"Node '{nid}' does not exist in the graph.")

    def __repr__(self) -> str:
        return (
            f"KnowledgeGraph(nodes={self.node_count}, "
            f"edges={self.edge_count}, "
            f"docs={self.doc_ids})"
        )
