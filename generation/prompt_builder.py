from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


OUTPUT_FORMAT_RULES = """
OUTPUT FORMAT — Markdown required (never a single dense paragraph):

Structure:
- Use ## headings to separate logical sections (e.g. "## Direct Answer", "## Comparison", "## Risk Implications")
- Use bullet points (- ) for each distinct fact, figure, or sub-answer
- **Bold** all key numbers, percentages, dollar amounts, dates, and critical terms
- Use *italics* for page citations, qualifying context, and source references
- When the question has multiple parts, give each part its own bullet or subsection
- End with a *Source: Page X, ...* line when page numbers are available

Example:
## Direct Answer
- **~60%** of revenues came from outside the United States *(Page 10)*

## Risk Implications
- Foreign currency fluctuations may affect projected **sales and earnings** growth
- A stronger U.S. dollar could *adversely affect* results of operations *(Page 10)*

Do NOT write wall-of-text paragraphs. Be scannable and professional."""


FACTUAL_SYSTEM_PROMPT = f"""You are DocuMind, a precision document intelligence assistant for SEC filings and financial reports.

CRITICAL RULES:
1. Answer ONLY using numbers and facts explicitly stated in the evidence below.
2. NEVER invent, estimate, or infer numbers not present in the evidence.
3. If the evidence contains the exact answer, state it directly with the precise figures.
4. For headcount questions: report total, US, and international if all are in evidence.
5. For financial questions: use ANNUAL figures from "Years ended December 31" or "Selected Financial Data" — NOT quarterly figures.
6. When comparing years, cite both years' values and the difference if stated in evidence.
7. If evidence is insufficient, say "The evidence does not contain this information" — do not guess.
8. Cite page numbers for each key figure.

DOMAIN LOGIC — Comparing figures across sections:
- When figures from different sections (e.g. Item 7 vs. Note 1) appear to differ, first check whether the metrics are structurally different (e.g. segment-level operating income vs. company-wide net cash flows) before assuming a numerical error or reclassification.
- A difference in numbers across sections is NOT a discrepancy unless both sections are measuring the exact same metric at the same scope and time period.
- Always identify the definition and scope of each metric before comparing.

{OUTPUT_FORMAT_RULES}"""


GENERAL_SYSTEM_PROMPT = f"""You are DocuMind, a risk-aware document intelligence assistant.

Your answers must:
1. Directly address the user's question using the supporting evidence provided.
2. Explicitly surface any exceptions, contradictions, or risks found in the evidence.
3. Qualify your answer when risk evidence is present — never ignore it.
4. Cite the source node type and page number for key claims.

DOMAIN LOGIC — Comparing figures across sections:
- When figures from different sections (e.g. Item 7 vs. Note 1) appear to differ, first check whether the metrics are structurally different (e.g. segment-level operating income vs. company-wide net cash flows) before assuming a numerical error or reclassification.
- A difference in numbers across sections is NOT a discrepancy unless both sections are measuring the exact same metric at the same scope and time period.
- Always identify the definition and scope of each metric before comparing.

{OUTPUT_FORMAT_RULES}"""


def is_factual_query(query: str) -> bool:
    ql = query.lower()
    factual_signals = (
        r"\bhow many\b", r"\bhow much\b", r"\btotal\b", r"\bnumber of\b",
        r"\bemployed\b", r"\bemployees\b", r"\bspent\b", r"\bspend\b",
        r"\bnet sales\b", r"\bnet income\b", r"\brevenue\b", r"\bamount\b",
        r"\bcompare\b", r"\bcompared to\b", r"\b20\d{2}\b",
        r"\bresearch and development\b", r"\br&d\b",
    )
    return any(re.search(pat, ql) for pat in factual_signals)


def _extract_relevant_excerpt(content: str, query: str, max_len: int = 900) -> str:
    """Return the most query-relevant portion of a chunk instead of blind truncation."""
    if len(content) <= max_len:
        return content

    ql = query.lower()
    keywords = [w for w in re.findall(r"\b\w{4,}\b", ql) if w not in (
        "what", "were", "does", "have", "many", "much", "about", "both", "compare",
    )]

    best_start = 0
    best_score = -1
    step = max(50, max_len // 4)
    for start in range(0, len(content) - 200, step):
        window = content[start: start + max_len]
        score = sum(1 for kw in keywords if kw in window.lower())
        if re.search(r"[\d,\.]{4,}", window):
            score += 3
        if "years ended december 31" in window.lower():
            score += 4
        if "employed" in ql and "employed" in window.lower():
            score += 5
        if score > best_score:
            best_score = score
            best_start = start

    excerpt = content[best_start: best_start + max_len]
    if best_start > 0:
        excerpt = "..." + excerpt
    if best_start + max_len < len(content):
        excerpt = excerpt + "..."
    return excerpt


def _format_node(node: Dict[str, Any], prefix: str = "", query: str = "") -> str:
    ntype = node.get("type", "node")
    page = node.get("page", "?")
    score = node.get("score", 0)
    content = str(node.get("content", "")).strip()
    parts = [f"{prefix}[{ntype.upper()} · Page {page} · relevance={score:.2f}]"]

    section = node.get("section", "") or node.get("metadata", {}).get("section", "")
    if section:
        parts.append(f"Section: {section[:100]}")

    fig_num = node.get("figure_number", "") or ""
    tbl_num = node.get("table_number", "") or ""
    caption = node.get("caption", "") or ""

    if fig_num:
        parts.append(f"Figure {fig_num}")
    if tbl_num:
        parts.append(f"Table {tbl_num}")
    if caption:
        parts.append(f"Caption: {caption[:200]}")

    vision = node.get("vision_summary", "") or ""
    if vision:
        parts.append(f"Vision: {vision[:300]}")

    tbl_headers = node.get("headers", []) or []
    tbl_rows = node.get("rows", []) or []
    if tbl_headers and tbl_rows:
        def _c(v):
            return getattr(v, "text", str(v)) if hasattr(v, "text") else str(v)
        h_str = " | ".join(_c(h) for h in tbl_headers[:8])
        lines = [f"[TABLE {node.get('table_number', '')}]"]
        lines.append("  Headers: " + h_str)
        for r in tbl_rows[:8]:
            lines.append("    " + " | ".join(_c(c) for c in r[:8]))
        parts.append("\n".join(lines))
    elif node.get("table_markdown", ""):
        tbl = node["table_markdown"][:500]
        parts.append(f"[TABLE {node.get('table_number', '')}]\n  {tbl}")

    if content:
        excerpt = _extract_relevant_excerpt(content, query) if query else content[:900]
        parts.append(excerpt)

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
    factual = is_factual_query(query)
    system = FACTUAL_SYSTEM_PROMPT if factual else GENERAL_SYSTEM_PROMPT

    # Sort supporting by score descending so best evidence comes first
    sorted_supporting = sorted(
        supporting,
        key=lambda n: float(n.get("score") or n.get("_rerank_score") or 0),
        reverse=True,
    )

    lines: List[str] = []

    if sorted_supporting:
        lines.append("=== SUPPORTING EVIDENCE (use ONLY these facts) ===")
        for node in sorted_supporting[:10]:
            line = _format_node(node, query=query)
            if line.strip():
                lines.append(line)

    risk_nodes = exceptions + contradictions + risks
    if risk_nodes and not factual:
        lines.append("\n=== RISK / EXCEPTION EVIDENCE ===")
        for node in risk_nodes[:5]:
            line = _format_node(node, prefix="⚠ ", query=query)
            if line.strip():
                lines.append(line)

    if overall_risk_level and overall_risk_level != "None" and not factual:
        lines.append(f"\n⚑ RISK LEVEL: {overall_risk_level.upper()}")

    if cross_doc:
        lines.append("\n[Cross-document mode: evidence spans multiple documents.]")

    evidence_block = "\n\n".join(lines) if lines else "No evidence retrieved."

    if factual:
        user_prompt = f"""{evidence_block}

---
QUESTION: {query}

Answer using ONLY the exact numbers and facts from the evidence above.
Use structured Markdown with ## headings, bullet points, **bold** key figures, and *italic* citations.
Do not use quarterly data when annual totals are requested."""
    else:
        user_prompt = f"""{evidence_block}

---
QUESTION: {query}

Answer based strictly on the evidence above.
Use structured Markdown with ## headings, bullet points, **bold** key terms, and *italic* page citations."""

    return {"system": system, "user": user_prompt, "factual": factual}


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
