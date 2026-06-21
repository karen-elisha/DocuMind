"""
pymupdf_parser.py — Fast, memory-safe PDF parser using PyMuPDF (fitz).

Used as the primary parser for large/complex PDFs that cause Docling's ML
layout model to crash with std::bad_alloc.  Zero ML models — pure C++ PDF
rendering with font-size heuristics for element classification.
"""
from __future__ import annotations

import os
import re
import time
import uuid
from typing import Any, Dict, List, Optional

from config import Config


# ── helpers ────────────────────────────────────────────────────────────────────

def _node_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _safe_filename(name: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9._-]+", "_", name.strip())
    return name or "document"


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _classify_block(text: str, font_size: float, page_median_size: float,
                    block_y: float, page_height: float) -> str:
    """Classify a text block using font size and page-position heuristics."""
    text_lower = text.lower().strip()

    # Headings: significantly larger font than median body text
    if font_size >= page_median_size * 1.25 and len(text) < 200:
        return "heading"

    # Footnotes: small font near the bottom of the page (bottom 15%)
    if font_size <= page_median_size * 0.85 and block_y > page_height * 0.85:
        return "footnote"

    # Footnotes by marker pattern: starts with ¹²³⁴⁵ or (1) or *
    if re.match(r"^[\*†‡§¹²³⁴⁵⁶⁷⁸⁹\(\d\)]+\s", text):
        return "footnote"

    # Captions: short text following a common caption pattern
    if re.match(r"^(figure|fig\.|table|exhibit|chart|note)\s*\d*[:\.]", text_lower) and len(text) < 250:
        return "caption"

    return "paragraph"


# ── main parser ────────────────────────────────────────────────────────────────

def parse_document_pymupdf(
    file_path: str,
    doc_id: str,
    images_out_dir: Optional[str] = None,
    _timing: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Parse a PDF using PyMuPDF. No ML models — pure font + position heuristics.

    Returns the same schema as the Docling parser so it is a drop-in replacement.
    """
    try:
        import fitz as _fitz_mod  # PyMuPDF
    except ImportError:
        import pymupdf as _fitz_mod  # fallback

    timings: Dict[str, float] = {} if _timing is None else _timing

    if images_out_dir is None:
        images_out_dir = os.path.join(Config.PROCESSED_DIR, "images", _safe_filename(doc_id))
    _ensure_dir(images_out_dir)

    print(f"[PyMuPDFParser] Opening file: {file_path}")
    t0 = time.perf_counter()

    doc = _fitz_mod.open(file_path)
    num_pages = len(doc)
    print(f"[PyMuPDFParser] Pages: {num_pages}")

    elements: List[Dict[str, Any]] = []
    images: List[Dict[str, Any]] = []

    text_count = 0
    table_count = 0
    image_count = 0

    current_section = ""

    for page_num, page in enumerate(doc, start=1):
        page_height = page.rect.height

        # ── Text blocks ───────────────────────────────────────────────────────
        # Get all text blocks with font information
        blocks = page.get_text("dict", flags=_fitz_mod.TEXT_PRESERVE_WHITESPACE)["blocks"]

        # Collect all font sizes on this page to compute median body size
        all_sizes: List[float] = []
        for block in blocks:
            if block.get("type") != 0:  # 0 = text block
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span.get("size", 0) > 5:
                        all_sizes.append(span["size"])

        if not all_sizes:
            continue

        all_sizes.sort()
        # Use the 60th percentile as "body text" size
        median_size = all_sizes[int(len(all_sizes) * 0.60)]

        for block in blocks:
            if block.get("type") != 0:
                continue

            # Gather all text and dominant font size in this block
            block_text_parts: List[str] = []
            span_sizes: List[float] = []

            for line in block.get("lines", []):
                line_parts: List[str] = []
                for span in line.get("spans", []):
                    t = span.get("text", "").strip()
                    if t:
                        line_parts.append(t)
                        if span.get("size", 0) > 5:
                            span_sizes.append(span["size"])
                if line_parts:
                    block_text_parts.append(" ".join(line_parts))

            block_text = " ".join(block_text_parts).strip()
            if not block_text or len(block_text) < 3:
                continue

            dominant_size = sum(span_sizes) / len(span_sizes) if span_sizes else median_size
            block_y = block["bbox"][1]  # top-y of block

            elem_type = _classify_block(block_text, dominant_size, median_size, block_y, page_height)

            # Track current section from headings
            if elem_type == "heading":
                current_section = block_text[:120]

            elements.append({
                "element_id": _node_id(elem_type),
                "type": elem_type,
                "page": page_num,
                "content": block_text,
                "metadata": {
                    "source": "pymupdf",
                    "font_size": round(dominant_size, 1),
                    "section": current_section,
                },
            })
            text_count += 1

        # ── Tables ────────────────────────────────────────────────────────────
        try:
            tab_finder = page.find_tables()
            for tbl in tab_finder.tables:
                df = tbl.to_pandas()
                if df.empty:
                    continue
                # Convert to simple markdown-like text
                rows = []
                headers = " | ".join(str(c) for c in df.columns)
                rows.append(headers)
                rows.append("-" * len(headers))
                for _, row in df.iterrows():
                    rows.append(" | ".join(str(v) for v in row.values))
                tbl_text = "\n".join(rows)

                if tbl_text.strip():
                    elements.append({
                        "element_id": _node_id("table"),
                        "type": "table",
                        "page": page_num,
                        "content": tbl_text,
                        "metadata": {
                            "source": "pymupdf_table",
                            "section": current_section,
                        },
                    })
                    table_count += 1
        except Exception:
            pass  # table extraction is best-effort

    doc.close()

    timings["conversion"] = time.perf_counter() - t0
    timings["text_extraction"] = 0.0
    timings["image_extraction"] = 0.0
    timings["table_extraction"] = 0.0
    timings["total_parser"] = timings["conversion"]

    print(
        f"[PyMuPDFParser] Done in {timings['conversion']:.2f}s  "
        f"pages={num_pages}  texts={text_count}  tables={table_count}  images={image_count}  "
        f"elements={len(elements)}"
    )

    return {
        "doc_id": doc_id,
        "document_name": os.path.basename(file_path),
        "pages_processed": num_pages,
        "text_count": text_count,
        "table_count": table_count,
        "image_count": image_count,
        "elements": elements,
        "images": images,
    }
