"""Heuristics that boost authoritative declarative facts over trend commentary."""

from __future__ import annotations

import re
from typing import Dict

from ingestion.fact_extractor import is_quarterly_content

# Sections that typically hold source-of-truth totals in 10-K filings
AUTHORITY_SECTION_PATTERNS = (
    r"\bbusiness\b",
    r"\bgeneral\b",
    r"\boverview\b",
    r"\bselected financial\b",
    r"\bconsolidated\b",
    r"\bsummary\b",
    r"\bfinancial data\b",
    r"\bitem 1\b",
    r"\bitem 6\b",
    r"\bpart i\b",
    r"\bresearch and development\b",
    r"\bresearch and patents\b",
    r"\br&d\b",
    r"\bemployees\b",
    r"\byears ended december 31\b",
)

COMMENTARY_PATTERNS = (
    r"\bdecreased by\b",
    r"\bincreased by\b",
    r"\bdown \d",
    r"\bup \d",
    r"\bdeclined by\b",
    r"\brose by\b",
    r"\breduction of\b",
    r"\bgrowth in\b",
    r"\bfactors? that\b",
    r"\bprimary factor\b",
    r"\bcompared to\b",
    r"\byear.over.year\b",
    r"\bemployment decreased\b",
    r"\bemployment increased\b",
    r"\bsubstantially impacted\b",
)

DECLARATIVE_PATTERNS = (
    r"\bemployed [\d,]+",
    r"\bemployment of [\d,]+",
    r"\btotal of \$?[\d,\.]+\s*(million|billion|m|b)?",
    r"\bspent \$?[\d,\.]+\s*(million|billion|m|b)?",
    r"\bwas \$?[\d,\.]+\s*(million|billion|m|b)?",
    r"\bwere \$?[\d,\.]+\s*(million|billion|m|b)?",
    r"\bamounted to\b",
    r"\bat december 31\b",
    r"\bas of december 31\b",
    r"\bconsisted of\b",
    r"\btotaling \$?[\d,\.]",
    r"\$[\d,\.]+\s*billion\b",
    r"\$[\d,\.]+\s*million\b",
    r"\bresearch and development.{0,40}\$[\d,\.]",
    r"\br&d.{0,40}\$[\d,\.]",
    r"\btotaled \$[\d,\.]+\s*billion in 20\d{2}\b",
    r"\bexpenses totaled \$[\d,\.]+\s*billion\b",
    r"\bnet sales.{0,30}\$[\d,]+",
    r"\bnet income attributable.{0,30}[\d,]+",
    r"\byears ended december 31\b",
)

FALSE_POSITIVE_PATTERNS = (
    r"\bintrinsic value\b",
    r"\bstock options\b",
    r"\bweighted-average\b",
    r"\bshares outstanding\b",
    r"\bearnings per share\b",
)


def is_annual_query(query: str) -> bool:
    ql = query.lower()
    if re.search(r"\b(annual|full[- ]?year|year ended|years ended|fiscal year)\b", ql):
        return True
    if re.search(r"\b20\d{2}\b", ql) and not re.search(r"\bquarter|Q[1-4]\b", ql):
        return True
    return False


def _candidate_section_text(candidate: Dict) -> str:
    meta = candidate.get("metadata") or {}
    parts = [
        candidate.get("section", ""),
        candidate.get("parent_heading", ""),
        meta.get("parent_heading", ""),
        meta.get("section", ""),
        (candidate.get("content") or "")[:250],
    ]
    return " ".join(str(p) for p in parts if p).lower()


def section_authority_boost(candidate: Dict) -> float:
    hay = _candidate_section_text(candidate)
    hits = sum(1 for pat in AUTHORITY_SECTION_PATTERNS if re.search(pat, hay))
    return min(0.22, hits * 0.07)


def is_commentary_heavy(content: str) -> bool:
    cl = content.lower()
    if is_quarterly_content(content):
        return True
    commentary_hits = sum(1 for pat in COMMENTARY_PATTERNS if re.search(pat, cl))
    declarative_hits = sum(1 for pat in DECLARATIVE_PATTERNS if re.search(pat, cl))
    return commentary_hits >= 2 and declarative_hits == 0


def quarterly_penalty(content: str, query: str) -> float:
    if not is_annual_query(query):
        return 0.0
    if is_quarterly_content(content):
        return 0.45
    return 0.0


def annual_boost(content: str, query: str) -> float:
    if not is_annual_query(query):
        return 0.0
    cl = content.lower()
    boost = 0.0
    if re.search(r"years ended december 31", cl):
        boost += 0.15
    if re.search(r"selected financial data", cl):
        boost += 0.12
    year_m = re.search(r"\b(20\d{2})\b", query)
    if year_m and year_m.group(1) in cl:
        if re.search(r"[\d,\.]{4,}", cl):
            boost += 0.10
    return boost


def fact_type_boost(candidate: Dict) -> float:
    ntype = str(candidate.get("type") or "").lower()
    meta = candidate.get("metadata") or {}
    if ntype == "fact" or meta.get("fact_type"):
        return 0.18
    if ntype == "table_row" or meta.get("is_financial"):
        return 0.14
    return 0.0


def commentary_penalty(content: str) -> float:
    cl = content.lower()
    commentary_hits = sum(1 for pat in COMMENTARY_PATTERNS if re.search(pat, cl))
    declarative_hits = sum(1 for pat in DECLARATIVE_PATTERNS if re.search(pat, cl))
    if declarative_hits >= 1:
        return 0.0
    return min(0.25, commentary_hits * 0.09)


def declarative_boost(content: str, query: str) -> float:
    cl = content.lower()
    ql = query.lower()
    boost = 0.0

    for pat in DECLARATIVE_PATTERNS:
        if re.search(pat, cl):
            boost += 0.08

    for pat in FALSE_POSITIVE_PATTERNS:
        if re.search(pat, cl):
            boost -= 0.15

    if re.search(r"\b20\d{2}\b", ql):
        year = re.search(r"\b(20\d{2})\b", ql)
        if year and year.group(1) in cl and re.search(r"[\d,\.]{3,}", cl):
            boost += 0.12

    if any(w in ql for w in ("how many", "how much", "total", "number of", "spent", "employed")):
        if re.search(r"[\d,\.]{3,}", cl):
            boost += 0.10

    if "research" in ql and "development" in ql:
        if re.search(r"research.{0,40}development.{0,80}totaled.{0,30}\$?[\d,\.]+", cl):
            boost += 0.22

    if "employee" in ql:
        if re.search(r"\bemployed [\d,]+ people\b", cl):
            boost += 0.25
        if re.search(r"\bemployed in the united states\b", cl) and re.search(r"\binternationally\b", cl):
            boost += 0.15

    if "net sales" in ql and re.search(r"net sales.{0,20}\$?\s*[\d,]+", cl):
        boost += 0.20

    if "net income" in ql and re.search(r"net income.{0,40}[\d,]+", cl):
        boost += 0.20

    if "net sales" in ql and "net income" in ql:
        if re.search(r"years ended december 31", cl) and re.search(r"net sales", cl) and re.search(r"net income attributable", cl):
            boost += 0.30

    boost += annual_boost(content, query)
    boost -= quarterly_penalty(content, query)

    return min(0.40, max(-0.20, boost))


def keyword_source_boost(source: str) -> float:
    if source == "both":
        return 0.16
    if source == "keyword":
        return 0.12
    return 0.0


def apply_retrieval_adjustments(query: str, candidate: Dict) -> float:
    """Return an adjusted retrieval score in [0, 1]."""
    base = float(candidate.get("score") or 0.5)
    content = str(candidate.get("content") or "")

    adjusted = base
    adjusted += keyword_source_boost(str(candidate.get("_retrieval_source") or ""))
    adjusted += section_authority_boost(candidate)
    adjusted += fact_type_boost(candidate)
    adjusted += declarative_boost(content, query)
    adjusted -= commentary_penalty(content)

    return max(0.01, min(0.99, adjusted))


def apply_rerank_adjustments(query: str, candidate: Dict, rerank_prob: float) -> float:
    """Blend cross-encoder score with factual heuristics."""
    content = str(candidate.get("content") or "")
    prev = float(candidate.get("score") or 0.5)

    factual = (
        section_authority_boost(candidate)
        + fact_type_boost(candidate)
        + declarative_boost(content, query)
        - commentary_penalty(content)
        + keyword_source_boost(str(candidate.get("_retrieval_source") or ""))
    )
    factual_norm = max(0.0, min(1.0, 0.5 + factual))

    # Factual queries: weight heuristics more heavily
    if is_annual_query(query) or re.search(r"\b(how many|how much|total|employed|spent)\b", query, re.I):
        blended = 0.40 * rerank_prob + 0.20 * prev + 0.40 * factual_norm
    else:
        blended = 0.50 * rerank_prob + 0.25 * prev + 0.25 * factual_norm
    return max(0.01, min(0.99, blended))
