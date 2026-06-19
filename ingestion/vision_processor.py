from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from groq import Groq

from config import Config


@dataclass(frozen=True)
class VisionSummary:
    image_path: str
    page: int
    summary: str


def _build_groq_client() -> Groq:
    api_key = getattr(Config, "GROQ_API_KEY", "") or ""
    # If missing, raise early so ingestion runner can report properly.
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set. Cannot run vision processing.")
    return Groq(api_key=api_key)


def _is_probably_diagram_prompt(s: str) -> str:
    # Kept for future heuristics; currently unused.
    return s


def summarize_images(
    images: List[Dict[str, Any]],
    *,
    model: Optional[str] = None,
    max_images: Optional[int] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Task 2 Vision Processing

    Requirements:
    - Read extracted images (from parser output)
    - Use Groq Vision model
    - Generate concise semantic descriptions suitable for retrieval

    Returns:
      {
        "<image_element_id or synthetic_id>": {
            "page": int,
            "image_path": str,
            "vision_summary": str
        },
        ...
      }
    """
    client = _build_groq_client()
    if model is None:
        model = getattr(Config, "GROQ_VISION_MODEL", "llama-3.2-11b-vision-preview")

    results: Dict[str, Dict[str, Any]] = {}

    iterable = images or []
    if max_images is not None:
        iterable = iterable[: max_images]

    for idx, img in enumerate(iterable):
        image_path = img.get("image_path")
        page = int(img.get("page") or 1)

        if not image_path or not os.path.exists(image_path):
            continue

        # We may not have a stable image_element_id from parser; use a synthetic key if needed.
        image_key = img.get("image_element_id") or f"image_{idx}_p{page}"

        with open(image_path, "rb") as f:
            image_bytes = f.read()

        # Groq vision expects base64 in many SDK examples; the Groq python client
        # accepts file-like payloads depending on model. To stay robust, we pass
        # base64 via the required structure.
        import base64

        b64 = base64.b64encode(image_bytes).decode("utf-8")

        prompt = (
            "You are a document vision analyst for building retrieval nodes.\n"
            "Provide a concise semantic description (1-3 sentences) of what the image shows.\n\n"
            "Focus on:\n"
            "- architecture diagrams, workflow diagrams (entities + arrows)\n"
            "- charts/graphs (metrics + trends)\n"
            "- graphs/figures (key components + relationships)\n"
            "\n"
            "Output format: a single sentence description suitable for semantic retrieval.\n"
        )

        # Use Groq chat completion with vision content.
        # Model name is based on the repo plan; can be overridden via `model`.
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                }
            ],
            temperature=0.2,
            max_tokens=180,
        )

        summary_text = ""
        try:
            summary_text = completion.choices[0].message.content.strip()
        except Exception:
            summary_text = ""

        if not summary_text:
            summary_text = "Figure/diagram detected, but no description could be generated."

        results[image_key] = {
            "page": page,
            "image_path": image_path,
            "vision_summary": summary_text,
        }

    return results
