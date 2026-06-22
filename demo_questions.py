"""Per-document demo questions — generated at ingest time."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Populated via main._DOCUMENT_INSIGHTS[doc_id]["demo_questions"]
# This module provides accessors only.


def get_demo_questions(
    doc_id: Optional[str] = None,
    insights_store: Optional[Dict[str, dict]] = None,
) -> List[Dict[str, Any]]:
    """Return demo questions for a document (empty if not yet generated)."""
    if not doc_id or not insights_store:
        return []
    insight = insights_store.get(doc_id, {})
    return list(insight.get("demo_questions") or [])


def set_demo_questions(
    doc_id: str,
    questions: List[Dict[str, Any]],
    insights_store: Dict[str, dict],
) -> None:
    if doc_id not in insights_store:
        insights_store[doc_id] = {}
    insights_store[doc_id]["demo_questions"] = questions
