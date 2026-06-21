from __future__ import annotations

from typing import Any, Dict, List, Optional


SYSTEM_PROMPT = """You are DocuMind, a risk-aware document intelligence assistant.

Your answers must:
1. Directly address the user's question using the supporting evidence provided.
2. Explicitly surface any exceptions, contradictions, or risks found in the evidence.
3. Qualify your answer when risk evidence is present — never ignore it.
4. Cite the source node type and page number for key claims.
5. End with a one-line confidence statement when risk level is Medium or High.

When answering questions about figures, tables, or charts:
- Reference the figure/table number and caption
- Use the vision summary to describe what the image shows
- Explain trends, relationships, and key observations
- Connect the visual data to surrounding text context

Format: plain prose. No bullet dumps. Be concise and precise."""


def _format_node(node: Dict[str, Any], prefix: str = "") -> str:
    ntype = node.get("type", "node")
    page  = node.get("page", "?")
    content = str(node.get("content", "")).strip()
    parts = [f"{prefix}[{ntype.upper()} · Page {page}]"]

    # Figure/Table metadata
    fig_num = node.get("figure_number", "") or ""
    tbl_num = node.get("table_number", "") or ""
    caption = node.get("caption", "") or ""

    if fig_num:
        parts.append(f"Figure {fig_num}")

    if tbl_num:
        parts.append(f"Table {tbl_num}")

    if caption:
        parts.append(f"Caption: {caption[:200]}")

    # Vision summary for images/figures/charts
    vision = node.get("vision_summary", "") or ""
    if vision:
        parts.append(f"Vision: {vision[:300]}")

    # Image inline data marker (not text, will be rendered by frontend)
    has_image = node.get("image_data") or node.get("image_base64") or ""
    if has_image:
        parts.append("[IMAGE_ATTACHED]")

    # Table structured data (never flatten to markdown)
    tbl_headers = node.get("headers", []) or []
    tbl_rows = node.get("rows", []) or []
    if tbl_headers and tbl_rows:
        def _c(v):
            return getattr(v, 'text', str(v)) if hasattr(v, 'text') else str(v)
        h_str = " | ".join(_c(h) for h in tbl_headers[:8])
        lines = [f"[TABLE {node.get('table_number','')}]"]
        lines.append("  Headers: " + h_str)
        for r in tbl_rows[:8]:
            lines.append("    " + " | ".join(_c(c) for c in r[:8]))
        parts.append("\n".join(lines))
    elif node.get("table_markdown", ""):
        tbl = node["table_markdown"][:400]
        parts.append(f"[TABLE {node.get('table_number','')}]\n  {tbl}")

    if content:
        parts.append(content[:400])

    return "\n".join(parts)


def build_prompt(
    query: str,
    supporting: List[Dict[str, Any]],
    exceptions: List[Dict[str, Any]],
    contradictions: List[Dict[str, Any]],
    risks: List[Dict[str, Any]],
    overall_risk_level: str = "None",
    confidence: Optional[float] = None,
    cross_doc: bool = False,
) -> Dict[str, str]:
    lines: List[str] = []

    if supporting:
        lines.append("=== SUPPORTING EVIDENCE ===")
        for node in supporting[:8]:
            line = _format_node(node)
            if line.strip():
                lines.append(line)

    risk_nodes = exceptions + contradictions + risks
    if risk_nodes:
        lines.append("\n=== RISK / EXCEPTION EVIDENCE ===")
        for node in risk_nodes[:5]:
            line = _format_node(node, prefix="⚠ ")
            if line.strip():
                lines.append(line)

    if overall_risk_level and overall_risk_level != "None":
        lines.append(f"\n⚑ RISK LEVEL: {overall_risk_level.upper()}")
        if overall_risk_level == "High":
            lines.append("  → High risk detected. You MUST surface contradictions or exceptions in your answer.")
        elif overall_risk_level == "Medium":
            lines.append("  → Medium risk detected. Qualify your answer with the exceptions found.")
        else:
            lines.append("  → Low risk. Note any qualifications found.")

    if cross_doc:
        lines.append("\n[Cross-document mode: evidence spans multiple documents. Cite doc context where relevant.]")

    evidence_block = "\n\n".join(lines) if lines else "No evidence retrieved."

    user_prompt = f"""{evidence_block}

---
QUESTION: {query}

Answer based strictly on the evidence above. Surface exceptions and risks explicitly."""

    return {"system": SYSTEM_PROMPT, "user": user_prompt}


def build_prompt_from_fusion(
    query: str,
    fusion_result: Dict[str, Any],
    risk_result: Dict[str, Any],
    cross_doc: bool = False,
) -> Dict[str, str]:
    evidence = fusion_result.get("evidence", {})
    overall_risk = risk_result.get("overall_risk_level", "None")
    confidence = 1.0 - ({"None": 0.0, "Low": 0.08, "Medium": 0.25, "High": 0.45}.get(overall_risk, 0.25))

    return build_prompt(
        query=query,
        supporting=evidence.get("supporting", []),
        exceptions=evidence.get("exceptions", []),
        contradictions=evidence.get("contradictions", []),
        risks=evidence.get("risks", []),
        overall_risk_level=overall_risk,
        confidence=confidence,
        cross_doc=cross_doc,
    )
