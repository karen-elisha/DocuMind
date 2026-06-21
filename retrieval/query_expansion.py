from __future__ import annotations
import re
from typing import List


# Common section-level terms — used only to generate useful search variants,
# never for hardcoded routing or type boosting.
_SECTION_TERMS = re.compile(
    r'\b(abstract|introduction|background|methodology|method|approach|'
    r'experiment|result|discussion|conclusion|reference|appendix|'
    r'training|dataset|evaluation|implementation|related work)\b',
    re.IGNORECASE
)


def expand_query(query: str) -> List[str]:
    """Generate query variants for multi-query retrieval.

    The goal is to produce semantically diverse reformulations
    that increase recall without introducing noise.

    Never adds keyword prefixes like 'definition' or 'meaning'
    which degrade retrieval for section-level queries.
    """
    q = query.strip()
    if not q:
        return [q]

    variants = [q]
    q_lower = q.lower()

    # If the query references a document section, generate a variant
    # that uses the section name directly as a search target.
    m = _SECTION_TERMS.search(q_lower)
    if m:
        section_word = m.group(1)
        variants.append(f"{q} section")
        variants.append(f"{section_word} about")

    # For "what is X" / "explain X" queries, create an additional
    # information-seeking variant without intro words.
    if q_lower.startswith("explain ") or q_lower.startswith("what is ") or q_lower.startswith("what are "):
        topic = re.sub(r'^(explain|what is|what are|what does)\s+', '', q_lower, flags=re.IGNORECASE).strip()
        if topic and len(topic) > 3:
            # Keep the original query and add a focused variant
            if not any(v == topic for v in variants):
                variants.append(topic)

    # Return unique non-empty variants (max 4)
    seen = set()
    deduped = []
    for v in variants:
        vn = v.strip()
        if vn and vn not in seen:
            seen.add(vn)
            deduped.append(vn)
    return deduped[:4]
