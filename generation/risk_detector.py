from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

# ── Keyword rules: (pattern, risk_level, signal_label) ───────────────────────
_RULES: List[Tuple[re.Pattern, str, str]] = [
    # High
    (re.compile(r"\bcritical\s+risk\b|\bdoes\s+not\s+apply\b|\bnot\s+applicable\b|\binvalidates\b|\bnullifies\b|\bsupersedes\b|\bmaterial\s+weakness\b|\bsignificant\s+doubt\b", re.I), "High", "critical_risk"),
    (re.compile(r"\bcontradicts\b|\bcontrary\b|\binconsistent\s+with\b|\bat\s+odds\s+with\b|\bconflicts\s+with\b", re.I), "High", "contradiction"),
    # Medium
    (re.compile(r"\bwarning\b|\blimitation\b|\bcaution\b|\bcaveat\b|\brestricted\b|\bsubject\s+to\b|\bonly\s+applicable\b", re.I), "Medium", "warning"),
    (re.compile(r"\bexcept\b|\bunless\b|\bexcluding\b|\bapart\s+from\b|\bbarring\b|\bwith\s+the\s+exception\s+of\b", re.I), "Medium", "exception"),
    (re.compile(r"\bmay\s+not\b|\bdoes\s+not\s+guarantee\b|\bno\s+assurance\b|\bcannot\s+ensure\b|\bnot\s+always\b", re.I), "Medium", "limitation"),
    # Low
    (re.compile(r"\bhowever\b|\bnote\s+that\b|\balthough\b|\bnevertheless\b|\bthat\s+said\b|\bon\s+the\s+other\s+hand\b", re.I), "Low", "qualification"),
    (re.compile(r"\bdespite\b|\bnotwithstanding\b|\beven\s+though\b|\bwhile\b", re.I), "Low", "contrast"),
]

_LEVEL_ORDER = {"None": 0, "Low": 1, "Medium": 2, "High": 3}


def score_text(text: str) -> Dict[str, Any]:
    """
    Scan a single text string for risk signals.

    Returns:
        {
            "risk_level": "None" | "Low" | "Medium" | "High",
            "signals": [{"label": str, "match": str, "risk_level": str}]
        }
    """
    signals = []
    for pattern, level, label in _RULES:
        for m in pattern.finditer(text):
            signals.append({"label": label, "match": m.group(0), "risk_level": level})

    if not signals:
        return {"risk_level": "None", "signals": []}

    top = max(signals, key=lambda s: _LEVEL_ORDER[s["risk_level"]])
    return {"risk_level": top["risk_level"], "signals": signals}


def score_nodes(nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Score a list of evidence nodes and aggregate into one risk level.

    Returns:
        {
            "overall_risk_level": str,
            "node_scores": [{"node_id": str, "risk_level": str, "signals": [...]}],
            "risk_counts": {"High": int, "Medium": int, "Low": int}
        }
    """
    node_scores = []
    counts: Dict[str, int] = {"High": 0, "Medium": 0, "Low": 0}

    for node in nodes:
        content = node.get("content", "") or ""
        result = score_text(content)
        level = result["risk_level"]
        if level in counts:
            counts[level] += 1
        node_scores.append({
            "node_id": node.get("node_id") or node.get("id", ""),
            "risk_level": level,
            "signals": result["signals"],
        })

    # Aggregate — density escalation: 3+ Medium → High
    if counts["High"] > 0:
        overall = "High"
    elif counts["Medium"] >= 3:
        overall = "High"
    elif counts["Medium"] > 0:
        overall = "Medium"
    elif counts["Low"] > 0:
        overall = "Low"
    else:
        overall = "None"

    return {
        "overall_risk_level": overall,
        "node_scores": node_scores,
        "risk_counts": counts,
    }


def confidence_from_risk(risk_level: str) -> float:
    """Map risk level to a confidence adjustment factor (0–1)."""
    return {"None": 1.0, "Low": 0.92, "Medium": 0.75, "High": 0.55}.get(risk_level, 0.75)
