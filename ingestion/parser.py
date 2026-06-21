from __future__ import annotations

import os
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from config import Config


@dataclass(frozen=True)
class ParsedElement:
    element_id: str
    type: str  # heading|paragraph|table|image|caption|footnote|list_item|formula
    page: int
    content: str
    metadata: Dict[str, Any]
    embedding: Sequence[float] = ()
    section: str = ""


_PARSER_USED: Optional[str] = None  # "docling" or "pymupdf" — set during parse_document


def get_parser_used() -> Optional[str]:
    """Return which parser was used for the last document."""
    global _PARSER_USED
    return _PARSER_USED


# ---- Singleton DocumentConverter ----

_converter_instance = None


def _get_converter():
    global _converter_instance
    if _converter_instance is None:
        try:
            from docling.document_converter import DocumentConverter, PdfFormatOption
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
        except ImportError as exc:
            print(f"[DoclingParser] Docling not available: {exc}")
            print("[DoclingParser] Use PyMuPDF fallback for all PDFs.")
            return None

        print("[DoclingParser] Creating singleton converter (OCR={}, table_structure={})".format(
            Config.ENABLE_OCR, Config.ENABLE_TABLE_STRUCTURE
        ))
        t0 = time.perf_counter()
        pipeline_options = PdfPipelineOptions()
        # Only generate picture images when vision processing is enabled.
        # generate_page_images=True at 2x scale was the cause of std::bad_alloc
        # on large PDFs — it renders every page as a high-res image in memory.
        pipeline_options.generate_picture_images = Config.ENABLE_VISION
        pipeline_options.generate_page_images = False
        pipeline_options.images_scale = 1.0  # 2.0 doubles RAM usage per page
        pipeline_options.do_ocr = Config.ENABLE_OCR
        pipeline_options.do_table_structure = Config.ENABLE_TABLE_STRUCTURE
        pdf_format_option = PdfFormatOption(pipeline_options=pipeline_options)
        format_options = {InputFormat.PDF: pdf_format_option}
        _converter_instance = DocumentConverter(format_options=format_options)
        print(f"[DoclingParser] Converter created in {time.perf_counter()-t0:.2f}s")
    return _converter_instance


# ---- Figure/table number extraction from captions ----

_FIGURE_NUM_RE = re.compile(r'(?:figure|fig)[.\s]*(\d+)', re.IGNORECASE)
_TABLE_NUM_RE = re.compile(r'table[.\s]*(\d+)', re.IGNORECASE)


def _extract_figure_number(text: str | None) -> str:
    if not text:
        return ""
    m = _FIGURE_NUM_RE.search(text)
    return m.group(1) if m else ""


def _extract_table_number(text: str | None) -> str:
    if not text:
        return ""
    m = _TABLE_NUM_RE.search(text)
    return m.group(1) if m else ""


# ---- Helpers ----

def _safe_filename(name: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9._-]+", "_", name.strip())
    return name or "document"


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _node_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _get_page(item: Any, default: int = 1) -> int:
    prov = getattr(item, "prov", None) or []
    if prov:
        pn = getattr(prov[0], "page_no", None)
        if pn is not None:
            try:
                return int(pn)
            except (ValueError, TypeError):
                pass
    return default


# ---- Main parser ----

def _count_pdf_pages(file_path: str) -> int:
    """Quick page count without loading the full PDF."""
    try:
        try:
            import fitz as _fitz_mod
        except ImportError:
            import pymupdf as _fitz_mod
        doc = _fitz_mod.open(file_path)
        n = len(doc)
        doc.close()
        return n
    except Exception as exc:
        print(f"[Parser] Failed to count pages with fitz: {exc}")
        return -1  # signal: check file existence at least


def _run_docling_with_timeout(
    converter: Any,
    file_path: str,
    timeout: int,
) -> Any:
    """Run Docling conversion with a wall-clock timeout via a subprocess signal.

    Falls back to PyMuPDF if the conversion takes longer than *timeout* seconds.
    """
    import threading

    result_container: list = []
    error_container: list = []

    def target():
        try:
            r = converter.convert(file_path)
            result_container.append(r)
        except Exception as e:
            error_container.append(e)

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout)

    if t.is_alive():
        print(f"[Parser] Docling conversion timed out after {timeout}s — falling back to PyMuPDF.")
        # We cannot easily kill the thread, but we detach and move on.
        return None

    if error_container:
        raise error_container[0]

    return result_container[0] if result_container else None


def parse_document(
    file_path: str,
    doc_id: str,
    images_out_dir: Optional[str] = None,
    _timing: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    PARSER STRATEGY (req. 6):

    1. Default parser = Docling for all PDFs (text, headings, tables, images,
       captions, page metadata, layout, figure/table relationships).
    2. Fallback parser = PyMuPDF if:
       A. Document page count > MAX_DOCLING_PAGES (Config, default 30)
       B. Docling conversion fails (exception)
       C. Docling timeout exceeds DOCLING_TIMEOUT (Config, default 120s)
    3. Metadata ``parser`` field stored in the return dict.
    5. If fallback is used, a warning key is set.
    """
    global _PARSER_USED
    timings: Dict[str, float] = {} if _timing is None else _timing

    document_name = os.path.basename(file_path)
    _, ext = os.path.splitext(document_name.lower())
    if ext not in {".pdf", ".docx"}:
        raise ValueError(f"Unsupported file type: {ext}")

    use_pymupdf = False
    fallback_reason = None

    # For PDFs: decide parser based on page count
    if ext == ".pdf":
        num_pages = _count_pdf_pages(file_path)
        if num_pages < 0:
            use_pymupdf = True
            fallback_reason = "page_count_failed"
            print("[Parser] Page count failed — trying PyMuPDF fallback.")
        elif num_pages > Config.MAX_DOCLING_PAGES:
            use_pymupdf = True
            fallback_reason = "too_many_pages"
            print(
                f"[Parser] PDF has {num_pages} pages (> {Config.MAX_DOCLING_PAGES}). "
                f"Using PyMuPDF (fast, no ML models)."
            )
        else:
            print(
                f"[Parser] PDF has {num_pages} pages (<= {Config.MAX_DOCLING_PAGES}). "
                f"Using Docling (rich metadata)."
            )

    # Try Docling unless we already decided on PyMuPDF
    if not use_pymupdf:
        converter = _get_converter()
        if converter is None:
            use_pymupdf = True
            fallback_reason = "docling_unavailable"
            print("[Parser] Docling converter unavailable — falling back to PyMuPDF.")
        else:
            if images_out_dir is None:
                images_out_dir = os.path.join(Config.PROCESSED_DIR, "images", _safe_filename(doc_id))
            _ensure_dir(images_out_dir)

            # ---- Conversion (Docling path) ----
            t0 = time.perf_counter()
            print(f"[DoclingParser] Converting file: {file_path}")

            try:
                if Config.DOCLING_TIMEOUT > 0:
                    result = _run_docling_with_timeout(converter, file_path, Config.DOCLING_TIMEOUT)
                else:
                    result = converter.convert(file_path)

                if result is None:
                    use_pymupdf = True
                    fallback_reason = "docling_timeout"
                else:
                    timings["conversion"] = time.perf_counter() - t0
                    print(f"[DoclingParser] Conversion complete in {timings['conversion']:.2f}s")
            except Exception as exc:
                use_pymupdf = True
                fallback_reason = "docling_error"
                timings["conversion"] = time.perf_counter() - t0
                print(f"[DoclingParser] Conversion FAILED after {timings['conversion']:.2f}s: {exc}")
                import traceback
                traceback.print_exc()

    # ---- PyMuPDF fallback path ----
    if use_pymupdf:
        _PARSER_USED = "pymupdf"
        from ingestion.pymupdf_parser import parse_document_pymupdf
        result = parse_document_pymupdf(
            file_path=file_path,
            doc_id=doc_id,
            images_out_dir=images_out_dir,
            _timing=timings,
        )
        result["parser"] = "pymupdf"
        result["parser_fallback_reason"] = fallback_reason
        result["parser_warning"] = (
            "Advanced image/table extraction unavailable because fallback parser was used. "
            "Only text and basic tables are extracted."
        )
        return result

    # ---- Docling success path ----
    _PARSER_USED = "docling"

    doc = getattr(result, "document", None)

    if doc is not None:
        try:
            np = doc.num_pages() if callable(doc.num_pages) else doc.num_pages
        except Exception:
            np = len(doc.pages)
        print(f"[DoclingParser] doc.num_pages={np}  texts={len(doc.texts)}  tables={len(doc.tables)}  pictures={len(doc.pictures)}")

    # ---- pages_processed ----
    pages_processed = 1
    if doc is not None:
        try:
            np = doc.num_pages() if callable(doc.num_pages) else doc.num_pages
            pages_processed = int(np or 1)
            pages_processed = max(pages_processed, 1)
        except Exception:
            pages_processed = len(doc.pages) if doc.pages else 1

    extracted_elements: List[ParsedElement] = []
    images: List[Dict[str, Any]] = []

    # ---- Text extraction ----
    t0 = time.perf_counter()
    text_count = 0
    if doc is not None:
        texts = getattr(doc, "texts", None) or []
        for tx in list(texts):
            try:
                t = getattr(tx, "text", None) or getattr(tx, "content", None)
                if not isinstance(t, str):
                    t = str(t) if t is not None else ""
                t = t.strip()
                if not t:
                    continue

                page = _get_page(tx, 1)
                label = str(getattr(tx, "label", "") or "").lower()

                if label in ("section_header", "title"):
                    typ = "heading"
                elif label == "caption":
                    typ = "caption"
                elif label in ("footnote", "page_footer"):
                    typ = "footnote"
                elif label == "list_item":
                    typ = "list_item"
                elif label == "formula":
                    typ = "formula"
                else:
                    typ = "paragraph"

                extracted_elements.append(
                    ParsedElement(
                        element_id=_node_id(typ),
                        type=typ,
                        page=page,
                        content=t,
                        metadata={"source": "docling_texts", "docling_label": label},
                    )
                )
                text_count += 1
            except Exception:
                continue
    timings["text_extraction"] = time.perf_counter() - t0

    # ---- Image extraction ----
    t0 = time.perf_counter()
    image_count = 0
    if doc is not None:
        pictures = getattr(doc, "pictures", None) or []
        export_root = os.path.join(Config.PROCESSED_DIR, "images")
        _ensure_dir(export_root)
        pic_dir = images_out_dir if images_out_dir and "images" in images_out_dir else os.path.join(export_root, _safe_filename(doc_id))
        _ensure_dir(pic_dir)

        for idx, pic in enumerate(list(pictures)):
            try:
                page = _get_page(pic, 1)
                cap = getattr(pic, "caption", None) or getattr(pic, "title", None) or None
                if not isinstance(cap, str):
                    cap = None
                else:
                    cap = cap.strip() or None

                img_file = os.path.join(pic_dir, f"{_safe_filename(doc_id)}_img_{idx}.png")

                pil_img = None
                if pic.image is not None:
                    pil_img = pic.image.pil_image
                if pil_img is None:
                    get_img = getattr(pic, "get_image", None)
                    if callable(get_img):
                        pil_img = get_img(doc)
                if pil_img is not None and hasattr(pil_img, "save"):
                    pil_img.save(img_file)
                    print(f"[DoclingParser] Saved image {idx} to {img_file}")
                else:
                    continue

                if not os.path.exists(img_file):
                    continue

                fig_num = _extract_figure_number(cap or "")
                img_elem_id = _node_id("image")
                extracted_elements.append(
                    ParsedElement(
                        element_id=img_elem_id,
                        type="image",
                        page=page,
                        content="",
                        metadata={
                            "figure_caption": cap,
                            "image_path": img_file,
                            "image_index": idx,
                            "figure_number": fig_num,
                        },
                    )
                )
                image_count += 1

                if cap:
                    cap_elem_id = _node_id("caption")
                    extracted_elements.append(
                        ParsedElement(
                            element_id=cap_elem_id,
                            type="caption",
                            page=page,
                            content=cap,
                            metadata={
                                "linked_image_element_id": img_elem_id,
                                "figure_number": fig_num,
                            },
                        )
                    )

                images.append({
                    "image_id": img_elem_id,
                    "image_path": img_file,
                    "page": page,
                    "caption": cap,
                    "figure_number": fig_num,
                })

            except Exception:
                continue
    timings["image_extraction"] = time.perf_counter() - t0

    # ---- Table extraction ----
    t0 = time.perf_counter()
    table_count = 0
    if doc is not None:
        tables = getattr(doc, "tables", None) or []
        for idx, tbl in enumerate(list(tables)):
            try:
                page = _get_page(tbl, 1)
                content = ""
                fn = getattr(tbl, "export_to_markdown", None)
                if callable(fn):
                    try:
                        content = fn(doc)
                    except Exception:
                        try:
                            content = fn()
                        except Exception:
                            pass
                if not isinstance(content, str) or not content.strip():
                    content = str(getattr(tbl, "text", "")) if getattr(tbl, "text", None) else ""
                    content = content.strip()
                if not content:
                    continue

                # ── Author table filter ──────────────────────────────────
                # Skip tables that look like author/affiliation metadata
                content_lower = content.lower()
                has_email = re.search(r'\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b', content_lower) is not None
                has_author_keywords = any(kw in content_lower for kw in
                    ['corresponding author', 'e-mail', 'email address', 'tel:', 'fax:'])
                has_orcid = 'orcid' in content_lower
                if has_email or has_author_keywords or has_orcid:
                    print(f"[AuthorTableFilter] Skipping table {idx} on page {page} (author/email metadata)")
                    continue
                # Also skip tables with very few rows (<2 actual data rows) that look like key-value pairs
                if content_lower.count('\n') <= 3 and any(kw in content_lower for kw in
                    ['university', 'institute', 'department', 'laboratory', 'college', 'school']):
                    print(f"[AuthorTableFilter] Skipping table {idx} on page {page} (likely affiliation metadata)")
                    continue

                tbl_num = _extract_table_number(str(getattr(tbl, "caption", "")) if hasattr(tbl, "caption") else "")
                tbl_caption = str(getattr(tbl, "caption", "") or "").strip()

                table_headers: list = []
                table_rows: list = []
                try:
                    grid = None
                    td = getattr(tbl, "data", None)
                    if td is not None and hasattr(td, "grid"):
                        try:
                            grid = td.grid
                        except Exception:
                            pass
                    if grid is None:
                        grid = getattr(tbl, "table", None)
                    if grid is not None:
                        all_rows = []
                        for row in grid:
                            cells = []
                            for cell in row:
                                if cell is None:
                                    cells.append("")
                                elif hasattr(cell, "text"):
                                    cells.append(str(cell.text))
                                else:
                                    cells.append(str(cell))
                            all_rows.append(cells)
                        if all_rows:
                            table_headers = all_rows[0]
                            table_rows = all_rows[1:]
                except Exception:
                    pass

                extracted_elements.append(
                    ParsedElement(
                        element_id=_node_id("table"),
                        type="table",
                        page=page,
                        content=content,
                        metadata={
                            "source": "docling_tables",
                            "table_index": idx,
                            "table_number": tbl_num,
                            "table_caption": tbl_caption,
                            "table_headers": table_headers,
                            "table_rows": table_rows,
                        },
                    )
                )
                table_count += 1
            except Exception:
                continue
    timings["table_extraction"] = time.perf_counter() - t0

    # ---- Post-process: link images/tables to captions by page ----
    # Collect images and figure captions in document order for one-to-one matching
    cap_candidates = []  # (index, elem) for figure captions, preserving doc order
    for idx, ce in enumerate(extracted_elements):
        if ce.type == "caption" and _extract_figure_number(ce.content):
            cap_candidates.append((idx, ce))
    cap_idx = 0
    for img_elem in extracted_elements:
        if img_elem.type != "image":
            continue
        img_page = int(img_elem.page) if img_elem.page else None
        if not img_page:
            continue
        existing_fig_num = str(img_elem.metadata.get("figure_number", "") or "")
        if existing_fig_num:
            continue
        # Find next unused figure caption on same page
        while cap_idx < len(cap_candidates):
            ci, ce = cap_candidates[cap_idx]
            ce_page = int(ce.page) if ce.page else None
            if ce_page != img_page or ce.metadata.get("linked_image_element_id"):
                cap_idx += 1
                continue
            fn = _extract_figure_number(ce.content)
            if fn:
                img_elem.metadata["figure_number"] = fn
                img_elem.metadata["figure_caption"] = ce.content
                ce.metadata["linked_image_element_id"] = img_elem.element_id
                ce.metadata["figure_number"] = fn
                cap_idx += 1
                break
            else:
                cap_idx += 1

    for tbl_elem in extracted_elements:
        if tbl_elem.type != "table":
            continue
        tbl_page = int(tbl_elem.page) if tbl_elem.page else None
        if not tbl_page:
            continue
        existing_tbl_num = str(tbl_elem.metadata.get("table_number", "") or "")
        if existing_tbl_num:
            continue
        caps_on_page = [c for c in extracted_elements if c.type == "caption" and (int(c.page) if c.page else None) == tbl_page]
        for cap_elem in caps_on_page:
            cap_text = cap_elem.content
            tn = _extract_table_number(cap_text)
            if tn:
                tbl_elem.metadata["table_number"] = tn
                tbl_elem.metadata["table_caption"] = cap_text
                break

    # Also update images list metadata from the linked elements (one-to-one order)
    img_by_page_order = {}
    for e in extracted_elements:
        if e.type == "image":
            p = int(e.page) if e.page else None
            if p and e.metadata.get("figure_number"):
                img_by_page_order.setdefault(p, []).append(e)
    for img in images:
        p = int(img.get("page", 1))
        if img.get("figure_number"):
            continue
        matches = img_by_page_order.get(p, [])
        if not matches:
            continue
        m = matches.pop(0)
        fn = str(m.metadata.get("figure_number", "") or "")
        if fn:
            img["figure_number"] = fn
            img["caption"] = img.get("caption") or m.metadata.get("figure_caption", "")

    # ---- Build output ----
    elements_out = [
        {
            "element_id": e.element_id,
            "type": e.type,
            "page": e.page,
            "content": e.content,
            "metadata": e.metadata,
        }
        for e in extracted_elements
    ]

    timings["total_parser"] = sum(timings.get(k, 0) for k in ("conversion", "text_extraction", "image_extraction", "table_extraction"))

    print(f"[DoclingParser] pages={pages_processed}  texts={text_count}  tables={table_count}  images={image_count}  elements={len(elements_out)}")
    print(f"[DoclingParser] Timing: conversion={timings.get('conversion',0):.2f}s  text={timings.get('text_extraction',0):.2f}s  images={timings.get('image_extraction',0):.2f}s  tables={timings.get('table_extraction',0):.2f}s")

    return {
        "doc_id": doc_id,
        "document_name": document_name,
        "pages_processed": pages_processed,
        "text_count": text_count,
        "table_count": table_count,
        "image_count": image_count,
        "elements": elements_out,
        "images": images,
        "parser": "docling",
    }


def parse_documents_from_uploads() -> List[Dict[str, Any]]:
    _ensure_dir(Config.UPLOADS_DIR)
    docs: List[Dict[str, Any]] = []
    for fn in os.listdir(Config.UPLOADS_DIR):
        if not fn:
            continue
        _, ext = os.path.splitext(fn.lower())
        if ext not in {".pdf", ".docx"}:
            continue
        file_path = os.path.join(Config.UPLOADS_DIR, fn)
        doc_id = os.path.splitext(fn)[0]
        docs.append(parse_document(file_path=file_path, doc_id=doc_id))
    return docs
