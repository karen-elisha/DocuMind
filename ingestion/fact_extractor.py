"""Extract atomic fact sentences from document text for precise retrieval."""

from __future__ import annotations

import re
from typing import Any, Dict, List

# Sentence boundary — avoid splitting on decimals like $1.763
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'])")

# Patterns that indicate a self-contained factual statement worth indexing alone
FACT_PATTERNS: List[tuple[str, re.Pattern[str]]] = [
    ("headcount", re.compile(
        r"\b(?:employed|employment of)\s+[\d,]+\s+(?:people|employees|full[- ]time)",
        re.IGNORECASE,
    )),
    ("headcount_breakdown", re.compile(
        r"\b[\d,]+\s+employed in the united states\b.*\b[\d,]+\s+employed internationally\b",
        re.IGNORECASE,
    )),
    ("rd_spend", re.compile(
        r"research,?\s*development and related expenses totaled\s+\$[\d,\.]+\s*(?:billion|million)",
        re.IGNORECASE,
    )),
    ("financial_annual", re.compile(
        r"(?:years ended december 31|net sales|net income attributable).*\$?\s*[\d,]{3,}",
        re.IGNORECASE,
    )),
    ("environmental_spend", re.compile(
        r"environmental(?:ly)?\s+(?:capital|compliance|projects?).*\$[\d,\.]+\s*(?:million|billion)",
        re.IGNORECASE,
    )),
    ("declarative_amount", re.compile(
        r"\b(?:totaled|amounted to|was|were|spent)\s+\$?[\d,\.]+\s*(?:billion|million|m|b)\b",
        re.IGNORECASE,
    )),
    ("as_of_date", re.compile(
        r"\bas of december 31,?\s*20\d{2}\b.*[\d,]{3,}",
        re.IGNORECASE,
    )),
]

# Inline SEC Item section detection
_ITEM_INLINE = re.compile(
    r"(Item\s+\d+[A-Z]?\.?\s+(?:Business|Risk Factors|Unresolved Staff Comments|"
    r"Properties|Legal Proceedings|Mine Safety|Market for|Selected Financial|"
    r"Management.s Discussion|Quantitative and Qualitative|Financial Statements|"
    r"Changes in and Disagreements|Controls and Procedures|Other Information|"
    r"Directors|Executive Compensation|Security Ownership|Certain Relationships|"
    r"Principal Accountant|Exhibits|Available Information)[^\n.]{0,60})",
    re.IGNORECASE,
)

_TOC_NOISE = re.compile(
    r"\btable of contents\b|\bindex to financial\b|\bavailable information\b.*\bsec maintains\b",
    re.IGNORECASE,
)

_FINANCIAL_BLOCK = re.compile(
    r"Years ended December 31:.*?Net sales\s+\$\s*([\d,]+)\s+\$\s*([\d,]+).*?"
    r"Net income attributable to 3M\s+([\d,]+)\s+([\d,]+)",
    re.IGNORECASE | re.DOTALL,
)


def detect_section_from_text(text: str) -> str:
    """Extract the best SEC Item section label from inline text."""
    m = _ITEM_INLINE.search(text)
    if m:
        label = m.group(1).strip()
        if not _TOC_NOISE.search(label):
            return label[:120]
    return ""


def is_toc_noise(text: str) -> bool:
    return bool(_TOC_NOISE.search(text))


def is_quarterly_content(text: str) -> bool:
    tl = text.lower()
    if re.search(r"fourth quarter|third quarter|second quarter|first quarter|Q[1-4]|quarter ended|fourth-quarter", tl):
        if re.search(r"years ended december 31", tl) and not re.search(
            r"fourth quarter|third quarter|second quarter|first quarter|Q[1-4]|fourth-quarter",
            tl,
        ):
            return False
        return True
    return False


def split_sentences(text: str) -> List[str]:
    """Split text into sentences without breaking decimal numbers."""
    text = text.strip()
    if not text:
        return []
    parts = _SENTENCE_SPLIT.split(text)
    return [p.strip() for p in parts if p.strip()]


def classify_fact(sentence: str) -> str:
    if is_quarterly_content(sentence):
        return ""
    for fact_type, pattern in FACT_PATTERNS:
        if pattern.search(sentence):
            return fact_type
    return ""


def extract_fact_sentences(
    text: str,
    *,
    page: int,
    section: str,
    doc_id: str,
    source_node_id: str,
) -> List[Dict[str, Any]]:
    """Return atomic fact chunks extracted from a text block."""
    facts: List[Dict[str, Any]] = []
    seen: set[str] = set()

    # Extract consolidated annual financial data block (Item 6 Selected Financial Data)
    fin_m = _FINANCIAL_BLOCK.search(text)
    if fin_m:
        sales_2015, sales_2014, income_2015, income_2014 = fin_m.groups()
        fin_sentence = (
            f"Years ended December 31 — Selected Financial Data: "
            f"2015 net sales ${sales_2015} billion, net income attributable to 3M ${income_2015} billion; "
            f"2014 net sales ${sales_2014} billion, net income attributable to 3M ${income_2014} billion."
        )
        fin_section = "Item 6. Selected Financial Data" if "selected financial" not in section.lower() else section
        facts.append({
            "type": "fact",
            "page": page,
            "content": fin_sentence,
            "metadata": {
                "fact_type": "financial_annual",
                "section": fin_section,
                "parent_heading": fin_section,
                "source_node_id": source_node_id,
                "doc_id": doc_id,
            },
        })
        seen.add(fin_sentence.lower())

    for sentence in split_sentences(text):
        fact_type = classify_fact(sentence)
        if not fact_type:
            continue
        normalized = re.sub(r"\s+", " ", sentence.strip().lower())
        if normalized in seen or len(sentence.strip()) < 30:
            continue
        seen.add(normalized)

        inline_section = detect_section_from_text(sentence) or section
        facts.append({
            "type": "fact",
            "page": page,
            "content": sentence.strip(),
            "metadata": {
                "fact_type": fact_type,
                "section": inline_section,
                "parent_heading": inline_section,
                "source_node_id": source_node_id,
                "doc_id": doc_id,
            },
        })

    return facts


def format_table_row_fact(
    headers: List[str],
    row_values: List[str],
    *,
    page: int,
    section: str,
    table_label: str = "",
) -> str:
    """Convert a table row into a searchable declarative sentence."""
    pairs = []
    for h, v in zip(headers, row_values):
        h_clean = str(h).strip()
        v_clean = str(v).strip()
        if h_clean and v_clean and v_clean not in ("—", "-", "nan", "None"):
            pairs.append(f"{h_clean}: {v_clean}")
    if not pairs:
        return ""
    prefix = f"{table_label}. " if table_label else ""
    return prefix + "; ".join(pairs)
