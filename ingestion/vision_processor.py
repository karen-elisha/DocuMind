from __future__ import annotations

import json
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
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set. Cannot run vision processing.")
    return Groq(api_key=api_key)


_VISION_SYSTEM_PROMPT = """You are an expert scientific document analyst.

Analyze the image in detail and produce a thorough 150-300 word explanation.

For every image:
1. Identify figure number if visible.
2. Read and interpret any caption.
3. Analyze chart/diagram/figure type.
4. Explain relationships between elements.
5. Identify axes labels, units, scales.
6. Identify trends, increases, decreases, peaks, anomalies.
7. Identify key conclusions and scientific significance.

If scientific graph/chart:
- Explain the trend (rising, falling, cyclic, etc.)
- Identify variables (x-axis, y-axis, units)
- Note specific data points, peaks, valleys
- Explain what the trend means scientifically

If architecture/workflow diagram:
- Explain components and their roles
- Explain the flow / sequence
- Explain data or control flow between components

If table screenshot:
- Extract key values and relationships
- Summarize findings across rows/columns

Return valid JSON only with this exact structure:
{
  "figure_number": "",
  "chart_type": "",
  "title": "",
  "axes": "",
  "summary": "150-300 word detailed analysis",
  "observations": ["observation 1", "observation 2", "observation 3"],
  "conclusion": "key conclusion"
}
Do not return generic descriptions like 'the image shows a graph'. Be specific and detailed."""


def _parse_vision_response(text: str) -> dict:
    """Try to parse JSON from the vision model response."""
    text = text.strip()
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try to extract JSON from markdown code block
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    return {}


def summarize_images(
    images: List[Dict[str, Any]],
    *,
    model: Optional[str] = None,
    max_images: Optional[int] = None,
) -> Dict[str, Dict[str, Any]]:
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

        image_key = img.get("image_element_id") or f"image_{idx}_p{page}"

        with open(image_path, "rb") as f:
            image_bytes = f.read()

        import base64

        b64 = base64.b64encode(image_bytes).decode("utf-8")

        try:
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": _VISION_SYSTEM_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{b64}"},
                            },
                        ],
                    }
                ],
                temperature=0.2,
                max_tokens=500,
                response_format={"type": "json_object"},
            )

            raw = ""
            try:
                raw = completion.choices[0].message.content.strip()
            except Exception:
                raw = ""

            parsed = _parse_vision_response(raw)

            summary_text = parsed.get("summary", "")
            if not summary_text:
                parsed = _parse_vision_response(raw)
                summary_text = parsed.get("summary", "")
            if not summary_text:
                summary_text = f"[Figure {parsed.get('figure_number', '')}] {parsed.get('title', '') or parsed.get('chart_type', '') or 'diagram'}. {parsed.get('conclusion', '') or ''}"

            results[image_key] = {
                "page": page,
                "image_path": image_path,
                "vision_summary": summary_text,
                "vision_detail": parsed,
            }
        except Exception:
            results[image_key] = {
                "page": page,
                "image_path": image_path,
                "vision_summary": f"[Image page {page}] {img.get('caption', 'image')}",
                "vision_detail": {},
            }

    return results
