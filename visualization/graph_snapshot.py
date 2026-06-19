"""
graph_snapshot.py — Knowledge Graph Visualization

Renders knowledge graph snapshots using Matplotlib (static PNG) and
PyVis (interactive HTML).  Follows the DocuMind color scheme:

Node colors by type:
    Heading   → Blue      (#4A90D9)
    Paragraph → Purple    (#9B59B6)
    Table     → Green     (#2ECC71)
    Image     → Yellow    (#F1C40F)
    Figure    → Yellow    (#F1C40F)
    Caption   → Orange    (#E67E22)
    Footnote  → Red       (#E74C3C)
    Chart     → Brown     (#8B4513)

Edge styling:
    Positive  → Solid green lines
    Negative  → Dashed red lines with risk-level labels

Author: Karen
"""

import os
from typing import Any, Dict, List, Optional, Set, Tuple

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for server environments
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx

try:
    from pyvis.network import Network as PyVisNetwork
    PYVIS_AVAILABLE = True
except ImportError:
    PYVIS_AVAILABLE = False

from graph.graph_engine import KnowledgeGraph


# ──────────────────────────────────────────────
# Color Configuration
# ──────────────────────────────────────────────

NODE_COLORS: Dict[str, str] = {
    "heading": "#4A90D9",
    "paragraph": "#9B59B6",
    "table": "#2ECC71",
    "image": "#F1C40F",
    "figure": "#F1C40F",
    "caption": "#E67E22",
    "footnote": "#E74C3C",
    "chart": "#8B4513",
}

NODE_SHAPES_PYVIS: Dict[str, str] = {
    "heading": "diamond",
    "paragraph": "dot",
    "table": "square",
    "image": "triangle",
    "figure": "triangle",
    "caption": "star",
    "footnote": "triangleDown",
    "chart": "hexagon",
}

POSITIVE_EDGE_COLOR = "#27AE60"   # Green
NEGATIVE_EDGE_COLOR = "#E74C3C"   # Red
CROSS_DOC_EDGE_COLOR = "#3498DB"  # Blue

RISK_LEVEL_COLORS = {
    "Low": "#F39C12",     # Amber
    "Medium": "#E67E22",  # Orange
    "High": "#C0392B",    # Dark red
}

DEFAULT_NODE_COLOR = "#95A5A6"  # Grey fallback


class GraphVisualizer:
    """
    Renders knowledge graph snapshots in multiple formats.

    - generate_snapshot()          → static PNG via Matplotlib
    - generate_interactive()       → interactive HTML via PyVis
    - generate_subgraph_snapshot() → focused retrieval subgraph
    """

    def __init__(
        self,
        figsize: Tuple[int, int] = (16, 12),
        dpi: int = 150,
        font_size: int = 8,
    ) -> None:
        self.figsize = figsize
        self.dpi = dpi
        self.font_size = font_size

    # ══════════════════════════════════════════
    # MATPLOTLIB STATIC SNAPSHOT
    # ══════════════════════════════════════════

    def generate_snapshot(
        self,
        graph: KnowledgeGraph,
        highlight_nodes: Optional[Set[str]] = None,
        output_path: Optional[str] = None,
        title: str = "DocuMind Knowledge Graph",
    ) -> str:
        """
        Render the full knowledge graph as a static PNG image.

        Parameters
        ----------
        graph           : KnowledgeGraph instance
        highlight_nodes : set of node IDs to visually emphasize
        output_path     : file path for the PNG (default: auto-generated)
        title           : title displayed on the figure

        Returns
        -------
        str : path to the saved PNG file
        """
        if output_path is None:
            output_path = "graph_snapshot.png"

        G = graph.graph
        fig, ax = plt.subplots(1, 1, figsize=self.figsize, dpi=self.dpi)
        fig.patch.set_facecolor("#1A1A2E")
        ax.set_facecolor("#1A1A2E")

        if G.number_of_nodes() == 0:
            ax.text(
                0.5, 0.5, "Empty Graph",
                transform=ax.transAxes, ha="center", va="center",
                fontsize=20, color="white",
            )
            fig.savefig(output_path, bbox_inches="tight", facecolor="#1A1A2E")
            plt.close(fig)
            return output_path

        # Layout
        pos = self._compute_layout(G)

        # Draw edges first (underneath nodes)
        self._draw_edges_matplotlib(G, pos, ax)

        # Draw nodes
        self._draw_nodes_matplotlib(G, pos, ax, highlight_nodes)

        # Draw labels
        self._draw_labels_matplotlib(G, pos, ax)

        # Title
        ax.set_title(title, fontsize=16, color="white", fontweight="bold", pad=20)

        # Legend
        self._draw_legend(ax)

        ax.axis("off")
        fig.tight_layout()
        fig.savefig(output_path, bbox_inches="tight", facecolor="#1A1A2E")
        plt.close(fig)

        return output_path

    def _draw_nodes_matplotlib(
        self,
        G: nx.DiGraph,
        pos: Dict,
        ax: plt.Axes,
        highlight_nodes: Optional[Set[str]] = None,
    ) -> None:
        """Draw nodes colored by type with optional highlight ring."""
        node_colors = []
        node_sizes = []
        node_edge_colors = []
        node_linewidths = []

        for node_id in G.nodes:
            node_type = G.nodes[node_id].get("type", "unknown")
            color = NODE_COLORS.get(node_type, DEFAULT_NODE_COLOR)
            node_colors.append(color)

            # Larger nodes for headings
            size = 600 if node_type == "heading" else 400
            node_sizes.append(size)

            # Highlight ring
            if highlight_nodes and node_id in highlight_nodes:
                node_edge_colors.append("#FFFFFF")
                node_linewidths.append(3.0)
            else:
                node_edge_colors.append(color)
                node_linewidths.append(1.0)

        nx.draw_networkx_nodes(
            G,
            pos,
            ax=ax,
            node_color=node_colors,
            node_size=node_sizes,
            edgecolors=node_edge_colors,
            linewidths=node_linewidths,
            alpha=0.9,
        )

    def _draw_edges_matplotlib(
        self, G: nx.DiGraph, pos: Dict, ax: plt.Axes
    ) -> None:
        """
        Draw edges: positive as solid green, negative as dashed red.
        """
        positive_edges = []
        negative_edges = []
        cross_doc_edges = []

        for src, tgt, data in G.edges(data=True):
            if data.get("cross_document"):
                cross_doc_edges.append((src, tgt))
            elif data.get("polarity") == "negative":
                negative_edges.append((src, tgt))
            else:
                positive_edges.append((src, tgt))

        # Positive edges — solid green
        if positive_edges:
            nx.draw_networkx_edges(
                G, pos, edgelist=positive_edges, ax=ax,
                edge_color=POSITIVE_EDGE_COLOR, style="solid",
                alpha=0.6, arrows=True, arrowsize=12,
                width=1.5, connectionstyle="arc3,rad=0.1",
            )

        # Negative edges — dashed red
        if negative_edges:
            nx.draw_networkx_edges(
                G, pos, edgelist=negative_edges, ax=ax,
                edge_color=NEGATIVE_EDGE_COLOR, style="dashed",
                alpha=0.8, arrows=True, arrowsize=15,
                width=2.0, connectionstyle="arc3,rad=0.15",
            )

        # Cross-document edges — dotted blue
        if cross_doc_edges:
            nx.draw_networkx_edges(
                G, pos, edgelist=cross_doc_edges, ax=ax,
                edge_color=CROSS_DOC_EDGE_COLOR, style="dotted",
                alpha=0.7, arrows=True, arrowsize=12,
                width=1.5, connectionstyle="arc3,rad=0.2",
            )

    def _draw_labels_matplotlib(
        self, G: nx.DiGraph, pos: Dict, ax: plt.Axes
    ) -> None:
        """Draw node labels truncated to fit."""
        labels = {}
        for nid in G.nodes:
            node_type = G.nodes[nid].get("type", "")
            # Show id and abbreviated type
            labels[nid] = f"{nid}\n({node_type[:4]})"

        nx.draw_networkx_labels(
            G, pos, labels=labels, ax=ax,
            font_size=self.font_size, font_color="white",
            font_weight="bold",
        )

    def _draw_legend(self, ax: plt.Axes) -> None:
        """Draw a legend showing node type colors and edge styles."""
        legend_handles = []

        # Node types
        for node_type, color in NODE_COLORS.items():
            if node_type == "figure":
                continue  # Same color as image
            legend_handles.append(
                mpatches.Patch(color=color, label=node_type.capitalize())
            )

        # Edge types
        legend_handles.append(
            mpatches.Patch(color=POSITIVE_EDGE_COLOR, label="Positive Edge (solid)")
        )
        legend_handles.append(
            mpatches.Patch(color=NEGATIVE_EDGE_COLOR, label="Negative Edge (dashed)")
        )
        legend_handles.append(
            mpatches.Patch(color=CROSS_DOC_EDGE_COLOR, label="Cross-Doc Edge (dotted)")
        )

        ax.legend(
            handles=legend_handles,
            loc="upper left",
            fontsize=7,
            facecolor="#16213E",
            edgecolor="#0F3460",
            labelcolor="white",
            framealpha=0.9,
        )

    @staticmethod
    def _compute_layout(G: nx.DiGraph) -> Dict:
        """
        Compute node positions using spring layout with type-based
        grouping for visual clarity.
        """
        try:
            pos = nx.spring_layout(
                G, k=2.5, iterations=50, seed=42, scale=2.0
            )
        except Exception:
            pos = nx.circular_layout(G)
        return pos

    # ══════════════════════════════════════════
    # PYVIS INTERACTIVE HTML
    # ══════════════════════════════════════════

    def generate_interactive(
        self,
        graph: KnowledgeGraph,
        output_path: str = "graph_interactive.html",
        height: str = "800px",
        width: str = "100%",
        notebook: bool = False,
    ) -> str:
        """
        Generate an interactive HTML visualization using PyVis.

        Parameters
        ----------
        graph       : KnowledgeGraph instance
        output_path : path for the HTML file
        height      : CSS height of the visualization
        width       : CSS width of the visualization
        notebook    : set True if rendering in Jupyter

        Returns
        -------
        str : path to the saved HTML file
        """
        if not PYVIS_AVAILABLE:
            raise ImportError(
                "PyVis is required for interactive visualization. "
                "Install it with: pip install pyvis"
            )

        net = PyVisNetwork(
            height=height,
            width=width,
            directed=True,
            notebook=notebook,
            bgcolor="#1A1A2E",
            font_color="white",
        )

        # Physics configuration for attractive layout
        net.set_options("""
        {
            "physics": {
                "forceAtlas2Based": {
                    "gravitationalConstant": -50,
                    "centralGravity": 0.01,
                    "springLength": 200,
                    "springConstant": 0.08
                },
                "solver": "forceAtlas2Based",
                "stabilization": {
                    "iterations": 150
                }
            },
            "edges": {
                "smooth": {
                    "type": "curvedCW",
                    "roundness": 0.2
                }
            }
        }
        """)

        G = graph.graph

        # Add nodes
        for node_id, attrs in G.nodes(data=True):
            node_type = attrs.get("type", "unknown")
            content = attrs.get("content", "")
            page = attrs.get("page", "?")
            doc_id = attrs.get("doc_id", "?")

            color = NODE_COLORS.get(node_type, DEFAULT_NODE_COLOR)
            shape = NODE_SHAPES_PYVIS.get(node_type, "dot")
            size = 30 if node_type == "heading" else 20

            # Tooltip with full details
            title = (
                f"<b>{node_id}</b><br>"
                f"Type: {node_type}<br>"
                f"Page: {page}<br>"
                f"Doc: {doc_id}<br>"
                f"Content: {content[:200]}..."
            )

            net.add_node(
                node_id,
                label=node_id,
                color=color,
                shape=shape,
                size=size,
                title=title,
            )

        # Add edges
        for src, tgt, data in G.edges(data=True):
            polarity = data.get("polarity", "positive")
            edge_type = data.get("edge_type", "")
            risk_level = data.get("risk_level", "")
            is_cross_doc = data.get("cross_document", False)

            if is_cross_doc:
                color = CROSS_DOC_EDGE_COLOR
                dashes = True
                width = 2
                label = f"{edge_type} (cross-doc)"
            elif polarity == "negative":
                color = RISK_LEVEL_COLORS.get(risk_level, NEGATIVE_EDGE_COLOR)
                dashes = True
                width = 3
                label = f"{edge_type} [{risk_level}]"
            else:
                color = POSITIVE_EDGE_COLOR
                dashes = False
                width = 1.5
                label = edge_type

            title = (
                f"<b>{edge_type}</b><br>"
                f"Polarity: {polarity}<br>"
                f"Risk: {risk_level or 'N/A'}"
            )

            net.add_edge(
                src, tgt,
                color=color,
                dashes=dashes,
                width=width,
                label=label,
                title=title,
                arrows="to",
            )

        net.save_graph(output_path)
        return output_path

    # ══════════════════════════════════════════
    # SUBGRAPH SNAPSHOT (FOR EXPLAINABILITY)
    # ══════════════════════════════════════════

    def generate_subgraph_snapshot(
        self,
        graph: KnowledgeGraph,
        seed_nodes: List[str],
        positive_nodes: List[str],
        negative_nodes: List[str],
        output_path: Optional[str] = None,
        title: str = "Retrieval Evidence Graph",
    ) -> str:
        """
        Render a focused subgraph showing only the retrieval evidence
        for the explainability panel.

        Seed nodes are highlighted with a white border, positive nodes
        with green, and negative nodes with red.

        Parameters
        ----------
        graph          : KnowledgeGraph instance
        seed_nodes     : node IDs from hybrid search
        positive_nodes : node IDs from positive expansion
        negative_nodes : node IDs from negative expansion
        output_path    : file path for PNG output
        title          : figure title

        Returns
        -------
        str : path to the saved PNG
        """
        if output_path is None:
            output_path = "evidence_subgraph.png"

        all_nodes = set(seed_nodes) | set(positive_nodes) | set(negative_nodes)
        subgraph = graph.get_subgraph(list(all_nodes))

        # Use the standard snapshot with seed nodes highlighted
        return self.generate_snapshot(
            subgraph,
            highlight_nodes=set(seed_nodes),
            output_path=output_path,
            title=title,
        )

    def __repr__(self) -> str:
        return f"GraphVisualizer(figsize={self.figsize}, dpi={self.dpi})"
