"""Generate tailored demo questions from ingested document insights."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, List

from generation.groq_client import chat

_RISK_HEADING_RE = re.compile(
    r"\b(risk|caution|warning|uncertainty|factor|legal proceeding|litigation)\b",
    re.IGNORECASE,
)
_FINANCIAL_RE = re.compile(
    r"\b(revenue|sales|income|financial|expense|billion|million|employee|headcount|profit|earnings)\b",
    re.IGNORECASE,
)


def _build_document_context(insight: Dict[str, Any]) -> str:
    doc_name = insight.get("document_name", "document")
    stats = insight.get("stats", {})
    lines = [
        f"Document: {doc_name}",
        f"Pages: {stats.get('pages', '?')}",
        f"Tables: {stats.get('tables', 0)}, Images: {stats.get('images', 0)}",
    ]

    headings = insight.get("headings", [])[:20]
    if headings:
        lines.append("\nKey headings:")
        for h in headings[:15]:
            lines.append(f"  - (p.{h.get('page', '?')}) {str(h.get('content', ''))[:120]}")

    tables = insight.get("tables", [])[:5]
    if tables:
        lines.append("\nTable previews:")
        for t in tables[:3]:
            preview = (t.get("summary") or t.get("markdown", ""))[:200]
            lines.append(f"  - (p.{t.get('page', '?')}) {preview}")

    extracted = insight.get("extracted_text", {})
    if extracted:
        pages = sorted(extracted.keys(), key=lambda x: int(x) if str(x).isdigit() else 0)
        sample_paras: List[str] = []
        for p in pages[:3]:
            paras = extracted.get(p, {}).get("paragraphs", [])
            sample_paras.extend(paras[:2])
        if sample_paras:
            lines.append("\nOpening content samples:")
            for para in sample_paras[:4]:
                lines.append(f"  - {para[:250]}")

    return "\n".join(lines)


def _parse_llm_json(raw: str) -> List[Dict[str, Any]]:
    raw = raw.strip()
    # Strip markdown code fences if present
    if "```" in raw:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        if m:
            raw = m.group(1).strip()
    start = raw.find("[")
    end = raw.rfind("]")
    if start >= 0 and end > start:
        raw = raw[start : end + 1]
    data = json.loads(raw)
    if not isinstance(data, list):
        return []
    return data


def _normalize_questions(
    items: List[Dict[str, Any]],
    doc_id: str,
) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for i, item in enumerate(items[:6]):
        if not isinstance(item, dict):
            continue
        query = str(item.get("query") or "").strip()
        if len(query) < 15:
            continue
        category = str(item.get("category") or "factual").lower()
        if category not in ("factual", "risk"):
            category = "risk" if item.get("expects_risk_radar") else "factual"
        normalized.append({
            "id": str(item.get("id") or f"demo_{i + 1}"),
            "label": str(item.get("label") or query[:50])[:60],
            "description": str(item.get("description") or query[:80])[:100],
            "query": query,
            "doc_id": doc_id,
            "category": category,
            "expects_risk_radar": bool(
                item.get("expects_risk_radar") or category == "risk"
            ),
        })
    return normalized[:5]


def _heuristic_questions(insight: Dict[str, Any], doc_id: str) -> List[Dict[str, Any]]:
    """Fast fallback when LLM generation fails."""
    doc_name = insight.get("document_name", doc_id)
    questions: List[Dict[str, Any]] = []
    headings = insight.get("headings", [])
    tables = insight.get("tables", [])

    questions.append({
        "id": "summary",
        "label": "Document Overview",
        "description": "High-level summary of this document",
        "query": f"Summarize the main topics and purpose of {doc_name}. What are the key sections?",
        "doc_id": doc_id,
        "category": "factual",
        "expects_risk_radar": False,
    })

    for h in headings:
        text = str(h.get("content", ""))
        if _FINANCIAL_RE.search(text) and len(questions) < 4:
            questions.append({
                "id": f"fin_{uuid.uuid4().hex[:6]}",
                "label": text[:45] + ("..." if len(text) > 45 else ""),
                "description": "Financial or metric-focused question",
                "query": f"Based on the section '{text[:80]}', what are the key figures and facts reported?",
                "doc_id": doc_id,
                "category": "factual",
                "expects_risk_radar": False,
            })
            break

    for h in headings:
        text = str(h.get("content", ""))
        if _RISK_HEADING_RE.search(text) and len(questions) < 5:
            questions.append({
                "id": f"risk_{uuid.uuid4().hex[:6]}",
                "label": "Risk & Qualifications",
                "description": "Risks, exceptions, or caveats in the document",
                "query": f"What risks, uncertainties, or important qualifications are discussed in '{text[:80]}'?",
                "doc_id": doc_id,
                "category": "risk",
                "expects_risk_radar": True,
            })
            break

    if tables:
        t = tables[0]
        questions.append({
            "id": "table_1",
            "label": f"Table on Page {t.get('page', '?')}",
            "description": "Key data from the first major table",
            "query": f"What are the most important values and trends in the table on page {t.get('page', 1)}?",
            "doc_id": doc_id,
            "category": "factual",
            "expects_risk_radar": False,
        })

    images = insight.get("images", [])
    if images and len(questions) < 5:
        fig = images[0]
        fn = fig.get("figure_number") or "1"
        questions.append({
            "id": "figure_1",
            "label": f"Figure {fn}",
            "description": "Explain the first figure or chart",
            "query": f"Explain Figure {fn} and what it shows in the context of this document.",
            "doc_id": doc_id,
            "category": "factual",
            "expects_risk_radar": False,
        })

    while len(questions) < 3:
        questions.append({
            "id": f"general_{len(questions)}",
            "label": "Key Takeaways",
            "description": "Main conclusions from the document",
            "query": f"What are the three most important takeaways from {doc_name}?",
            "doc_id": doc_id,
            "category": "factual",
            "expects_risk_radar": False,
        })

    return questions[:5]


def generate_demo_questions(
    doc_id: str,
    insight: Dict[str, Any],
    *,
    use_llm: bool = True,
) -> List[Dict[str, Any]]:
    """
    Generate 3–5 tailored demo questions for an ingested document.
    Uses LLM when available; falls back to heuristics from headings/tables.
    """
    context = _build_document_context(insight)

    if use_llm:
        try:
            system = (
                "You generate analyst-style questions for document Q&A demos. "
                "Return ONLY a valid JSON array, no other text."
            )
            user = f"""Based on this document, generate exactly 5 high-quality questions an analyst would ask.

Requirements:
- Mix factual questions (numbers, definitions, summaries) and 1-2 risk/qualification questions
- Questions must be answerable FROM this document only
- Use specific section names, metrics, or topics mentioned in the context
- For SEC/financial filings: prefer headcount, revenue, R&D, risk factors when present
- Each item: id, label (short 3-6 words), description (one line), query (full question), category ("factual" or "risk"), expects_risk_radar (boolean)

{context}

JSON array:"""

            raw = chat(user, system=system, factual=False)
            parsed = _parse_llm_json(raw)
            normalized = _normalize_questions(parsed, doc_id)
            if len(normalized) >= 3:
                print(f"[DemoQuestions] Generated {len(normalized)} LLM questions for {doc_id}")
                return normalized
        except Exception as exc:
            print(f"[DemoQuestions] LLM generation failed for {doc_id}: {exc}")

    fallback = _heuristic_questions(insight, doc_id)
    print(f"[DemoQuestions] Using {len(fallback)} heuristic questions for {doc_id}")
    return fallback
