"""Fact Lock — verify LLM answer claims against retrieved evidence."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# Numeric / percentage patterns in LLM answers
_PERCENT_RE = re.compile(
    r"(?:~|approximately\s+|about\s+)?(\d{1,3}(?:\.\d+)?)\s*(?:%|percent|percentage)",
    re.IGNORECASE,
)
_DOLLAR_RE = re.compile(
    r"\$\s*([\d,]+(?:\.\d+)?)\s*(billion|million|m|b)?",
    re.IGNORECASE,
)
_COMMA_NUM_RE = re.compile(r"\b(\d{1,3}(?:,\d{3})+)\b")
_PLAIN_NUM_RE = re.compile(r"\b(\d{4,})\b")


def _normalize_num(s: str) -> str:
    return re.sub(r"[^\d.]", "", s)


def _extract_claims(answer: str) -> List[Dict[str, str]]:
    """Pull verifiable numeric claims from the answer text."""
    claims: List[Dict[str, str]] = []
    seen: set[str] = set()

    for m in _PERCENT_RE.finditer(answer):
        val = m.group(1)
        key = f"pct:{val}"
        if key not in seen:
            seen.add(key)
            claims.append({
                "value": val,
                "display": f"{val}%",
                "type": "percentage",
            })

    for m in _DOLLAR_RE.finditer(answer):
        raw = m.group(1)
        unit = (m.group(2) or "").lower()
        display = f"${raw}" + (f" {unit}" if unit else "")
        key = f"$:{_normalize_num(raw)}:{unit}"
        if key not in seen:
            seen.add(key)
            claims.append({
                "value": _normalize_num(raw),
                "display": display.strip(),
                "type": "currency",
                "unit": unit,
            })

    for m in _COMMA_NUM_RE.finditer(answer):
        raw = m.group(1)
        if raw in seen:
            continue
        # Skip years
        if re.match(r"^20\d{2}$", raw.replace(",", "")):
            continue
        key = f"n:{raw}"
        if key not in seen:
            seen.add(key)
            claims.append({
                "value": _normalize_num(raw),
                "display": raw,
                "type": "number",
            })

    return claims


def _evidence_corpus(evidence_nodes: List[Dict[str, Any]]) -> List[Tuple[str, Dict[str, Any]]]:
    """Flatten evidence nodes into searchable (text, node) pairs."""
    corpus: List[Tuple[str, Dict[str, Any]]] = []
    for node in evidence_nodes:
        if not node:
            continue
        # Handle negative-expansion entries with nested "node"
        inner = node.get("node") if isinstance(node.get("node"), dict) else node
        content = str(inner.get("content") or node.get("content") or "")
        if content.strip():
            corpus.append((content, inner if inner.get("content") else node))
    return corpus


def _find_in_evidence(
    claim: Dict[str, str],
    corpus: List[Tuple[str, Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    val = claim["value"]
    ctype = claim["type"]

    for text, node in corpus:
        text_norm = _normalize_num(text)
        text_lower = text.lower()

        if ctype == "percentage":
            patterns = [
                f"{val}%",
                f"{val} percent",
                f"{val} percentage",
                f"approximately {val}",
            ]
            if any(p in text_lower for p in patterns):
                return _match_result(claim, text, node)

        elif ctype == "currency":
            unit = claim.get("unit", "")
            raw_variants = [val, val.replace(".", ",") if "." in val else val]
            for rv in raw_variants:
                if rv in text_norm or rv in text.replace(",", ""):
                    if not unit or unit[:1] in text_lower or unit in text_lower:
                        return _match_result(claim, text, node)
            # e.g. "1.763 billion" without $
            if val in text_norm and ("billion" in text_lower or "million" in text_lower):
                return _match_result(claim, text, node)

        elif ctype == "number":
            if val in text_norm or claim["display"] in text:
                return _match_result(claim, text, node)

    return None


def _match_result(claim: Dict[str, str], text: str, node: Dict[str, Any]) -> Dict[str, Any]:
    # Extract a short snippet around the match
    display = claim["display"]
    idx = text.lower().find(display.lower().replace("$", "").strip()[:6])
    if idx < 0:
        idx = text.find(claim["value"][:4]) if len(claim["value"]) >= 4 else 0
    snippet = text[max(0, idx - 40): idx + 80].strip()
    if len(snippet) > 120:
        snippet = snippet[:120] + "..."

    page = node.get("page") or node.get("page_number") or "?"
    return {
        "verified": True,
        "page": page,
        "snippet": snippet,
        "node_type": node.get("type", "evidence"),
    }


def verify_answer(
    answer: str,
    evidence_nodes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Verify numeric claims in the answer against evidence chunks.

    Returns Fact Lock payload for API / UI.
    """
    claims = _extract_claims(answer)
    corpus = _evidence_corpus(evidence_nodes)

    verified_facts: List[Dict[str, Any]] = []
    unverified_facts: List[Dict[str, Any]] = []

    for claim in claims:
        match = _find_in_evidence(claim, corpus)
        entry = {
            "value": claim["display"],
            "type": claim["type"],
            "verified": bool(match),
            "page": match["page"] if match else None,
            "snippet": match["snippet"] if match else None,
            "node_type": match["node_type"] if match else None,
        }
        if match:
            verified_facts.append(entry)
        else:
            unverified_facts.append(entry)

    total = len(claims)
    verified_count = len(verified_facts)
    score = (verified_count / total) if total > 0 else 1.0

    # Qualitative claims (no numbers) — mark as narrative if no numeric claims
    status = "verified" if total > 0 and verified_count == total else (
        "partial" if verified_count > 0 else (
            "narrative" if total == 0 else "unverified"
        )
    )

    return {
        "status": status,
        "score": round(score, 3),
        "total_claims": total,
        "verified_count": verified_count,
        "verified": verified_facts,
        "unverified": unverified_facts,
    }
