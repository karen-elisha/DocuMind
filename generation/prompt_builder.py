from __future__ import annotations

from typing import Any, Dict, List, Optional


# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are DocuMind, a risk-aware document intelligence assistant.

Your answers must:
1. Directly address the user's question using the supporting evidence provided.
2. Explicitly surface any exceptions, contradictions, or risks found in the evidence.
3. Qualify your answer when risk evidence is present — never ignore it.
4. Cite the source node type and page number for key claims.
5. End with a one-line confidence statement when risk level is Medium or High.

Format: plain prose. No bullet dumps. Be concise and precise."""


def _format_node(node: Dict[str, Any], prefix: str = "") -> str:
    ntype = node.get("type", "node")
    page  = node.get("page", "?")
    content = str(node.get("content", "")).strip()
    if not content:
        return ""
    return f"{prefix}[{ntype.upper()} · Page {page}]: {content[:400]}"


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
    """
    Build the system + user prompt for Groq generation.

    Returns:
        {"system": str, "user": str}
    """
    lines: List[str] = []

    # ── Supporting evidence ───────────────────────────────────────────────────
    if supporting:
        lines.append("=== SUPPORTING EVIDENCE ===")
        for node in supporting[:8]:
            line = _format_node(node)
            if line:
                lines.append(line)

    # ── Risk evidence ─────────────────────────────────────────────────────────
    risk_nodes = exceptions + contradictions + risks
    if risk_nodes:
        lines.append("\n=== RISK / EXCEPTION EVIDENCE ===")
        for node in risk_nodes[:5]:
            line = _format_node(node, prefix="⚠ ")
            if line:
                lines.append(line)

    # ── Risk flag ─────────────────────────────────────────────────────────────
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

    evidence_block = "\n".join(lines) if lines else "No evidence retrieved."

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
    """
    Convenience wrapper — takes the output dicts from evidence_fusion and risk_detector
    and builds the full prompt.
    """
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
