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
from ingestion.fact_extractor import detect_section_from_text, format_table_row_fact, is_toc_noise

_ITEM_HEADING = re.compile(r"^Item\s+\d+[A-Z]?\.?\s", re.IGNORECASE)
_ITEM_SPLIT = re.compile(r"(?=Item\s+\d+[A-Z]?\.?\s)", re.IGNORECASE)
_PART_MARKER = re.compile(r"\bPART\s+[IVX]+\b", re.IGNORECASE)


def _item_section_label(text: str) -> str:
    detected = detect_section_from_text(text)
    if detected:
        return detected
    m = re.match(r"^(Item\s+\d+[A-Z]?\.?\s[^\n.]{0,80})", text.strip(), re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _split_item_sections(text: str) -> List[str]:
    """Split long Item 1 / Item 7 blocks into section-scoped paragraphs."""
    if len(text) < 600 or not _ITEM_SPLIT.search(text):
        return [text]
    parts = [p.strip() for p in _ITEM_SPLIT.split(text) if p.strip()]
    return parts if len(parts) > 1 else [text]


def _node_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _safe_filename(name: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9._-]+", "_", name.strip())
    return name or "document"


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _is_valid_section_heading(text: str, page_num: int) -> bool:
    """Reject TOC/index headings that pollute section metadata."""
    if is_toc_noise(text):
        return False
    if page_num <= 2 and _ITEM_HEADING.match(text.strip()):
        return False
    if len(text) > 250:
        return False
    return True


def _classify_block(text: str, font_size: float, page_median_size: float,
                    block_y: float, page_height: float) -> str:
    """Classify a text block using font size and page-position heuristics."""
    text_lower = text.lower().strip()

    if font_size >= page_median_size * 1.25 and len(text) < 200:
        return "heading"

    if _ITEM_HEADING.match(text.strip()) and len(text) < 250:
        return "heading"

    if _PART_MARKER.match(text.strip()) and len(text) < 80:
        return "heading"

    if font_size <= page_median_size * 0.85 and block_y > page_height * 0.85:
        return "footnote"

    if re.match(r"^[\*†‡§¹²³⁴⁵⁶⁷⁸⁹\(\d\)]+\s", text):
        return "footnote"

    if re.match(r"^(figure|fig\.|table|exhibit|chart|note)\s*\d*[:\.]", text_lower) and len(text) < 250:
        return "caption"

    return "paragraph"


def _extract_table_rows(df, page_num: int, section: str) -> List[Dict[str, Any]]:
    """Convert a pandas DataFrame into row-wise searchable table elements."""
    elements: List[Dict[str, Any]] = []
    if df.empty:
        return elements

    headers = [str(c).strip() for c in df.columns]
    header_line = " | ".join(headers)

    # Full table as markdown (for context)
    rows_md: List[str] = [header_line, "-" * min(len(header_line), 80)]
    for _, row in df.iterrows():
        rows_md.append(" | ".join(str(v).strip() for v in row.values))
    tbl_text = "\n".join(rows_md)

    elements.append({
        "element_id": _node_id("table"),
        "type": "table",
        "page": page_num,
        "content": tbl_text,
        "metadata": {
            "source": "pymupdf_table",
            "section": section,
            "table_headers": headers,
        },
    })

    # Row-wise fact sentences for financial tables
    is_financial = any(
        re.search(r"net sales|net income|december 31|years ended", h, re.I)
        for h in headers
    )
    table_label = section or "Financial table"
    if "selected financial" in section.lower():
        table_label = "Selected Financial Data — Years ended December 31"

    for _, row in df.iterrows():
        row_vals = [str(v).strip() for v in row.values]
        row_fact = format_table_row_fact(
            headers, row_vals, page=page_num, section=section, table_label=table_label,
        )
        if row_fact and (is_financial or re.search(r"[\d,]{3,}", row_fact)):
            elements.append({
                "element_id": _node_id("table_row"),
                "type": "table_row",
                "page": page_num,
                "content": row_fact,
                "metadata": {
                    "source": "pymupdf_table_row",
                    "section": section,
                    "table_headers": headers,
                    "is_financial": is_financial,
                },
            })

    return elements


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
    past_toc = False

    for page_num, page in enumerate(doc, start=1):
        page_height = page.rect.height

        if page_num >= 3:
            past_toc = True

        blocks = page.get_text("dict", flags=_fitz_mod.TEXT_PRESERVE_WHITESPACE)["blocks"]

        all_sizes: List[float] = []
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span.get("size", 0) > 5:
                        all_sizes.append(span["size"])

        if not all_sizes:
            continue

        all_sizes.sort()
        median_size = all_sizes[int(len(all_sizes) * 0.60)]

        for block in blocks:
            if block.get("type") != 0:
                continue

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
            block_y = block["bbox"][1]

            sub_blocks = _split_item_sections(block_text)
            for sub_text in sub_blocks:
                elem_type = _classify_block(sub_text, dominant_size, median_size, block_y, page_height)

                inline_section = detect_section_from_text(sub_text)
                if inline_section:
                    current_section = inline_section
                elif elem_type == "heading" and _is_valid_section_heading(sub_text, page_num):
                    current_section = sub_text[:120]
                elif _item_section_label(sub_text) and past_toc:
                    label = _item_section_label(sub_text)
                    if not is_toc_noise(label):
                        current_section = label

                section_for_elem = inline_section or current_section

                elements.append({
                    "element_id": _node_id(elem_type),
                    "type": elem_type,
                    "page": page_num,
                    "content": sub_text,
                    "metadata": {
                        "source": "pymupdf",
                        "font_size": round(dominant_size, 1),
                        "section": section_for_elem,
                    },
                })
                text_count += 1

        try:
            tab_finder = page.find_tables()
            for tbl in tab_finder.tables:
                df = tbl.to_pandas()
                if df.empty:
                    continue
                row_elements = _extract_table_rows(df, page_num, current_section)
                elements.extend(row_elements)
                table_count += len([e for e in row_elements if e["type"] == "table"])
        except Exception:
            pass

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
