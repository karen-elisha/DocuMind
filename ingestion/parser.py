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


# ---- Singleton DocumentConverter ----

_converter_instance = None


def _get_converter():
    global _converter_instance
    if _converter_instance is None:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions

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

# Page threshold above which PyMuPDF is used instead of Docling.
# Docling's ML layout model reliably crashes above ~38 pages on this machine.
_PYMUPDF_PAGE_THRESHOLD = int(os.getenv("DOCLING_MAX_PAGES", "30"))


def _count_pdf_pages(file_path: str) -> int:
    """Quick page count without loading the full PDF."""
    try:
        import fitz
        doc = fitz.open(file_path)
        n = len(doc)
        doc.close()
        return n
    except Exception:
        return 0


def parse_document(
    file_path: str,
    doc_id: str,
    images_out_dir: Optional[str] = None,
    _timing: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Smart hybrid parser: routes to PyMuPDF for large PDFs, Docling for small ones.

    - PDF  ≥ DOCLING_MAX_PAGES pages → PyMuPDF  (fast, no ML, handles huge docs)
    - PDF  <  DOCLING_MAX_PAGES pages → Docling  (rich metadata, table structure)
    - DOCX (any size)               → Docling  (Docling DOCX support is excellent)

    Parameters
    ----------
    _timing : optional dict
        If passed, timing intervals are written in-place for external collection.
    """
    timings: Dict[str, float] = {} if _timing is None else _timing

    document_name = os.path.basename(file_path)
    _, ext = os.path.splitext(document_name.lower())
    if ext not in {".pdf", ".docx"}:
        raise ValueError(f"Unsupported file type: {ext}")

    # Route large PDFs to PyMuPDF to avoid the bad_alloc ML crash
    if ext == ".pdf":
        num_pages = _count_pdf_pages(file_path)
        if num_pages >= _PYMUPDF_PAGE_THRESHOLD:
            print(
                f"[Parser] PDF has {num_pages} pages (≥{_PYMUPDF_PAGE_THRESHOLD}). "
                f"Using PyMuPDF (fast, no ML models)."
            )
            from ingestion.pymupdf_parser import parse_document_pymupdf
            return parse_document_pymupdf(
                file_path=file_path,
                doc_id=doc_id,
                images_out_dir=images_out_dir,
                _timing=timings,
            )
        else:
            print(
                f"[Parser] PDF has {num_pages} pages (<{_PYMUPDF_PAGE_THRESHOLD}). "
                f"Using Docling (rich metadata)."
            )

    converter = _get_converter()

    if images_out_dir is None:
        images_out_dir = os.path.join(Config.PROCESSED_DIR, "images", _safe_filename(doc_id))
    _ensure_dir(images_out_dir)

    # ---- Conversion (Docling path) ----
    t0 = time.perf_counter()
    print(f"[DoclingParser] Converting file: {file_path}")
    result = converter.convert(file_path)
    timings["conversion"] = time.perf_counter() - t0
    print(f"[DoclingParser] Conversion complete in {timings['conversion']:.2f}s")

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

    # ---- Text extraction (fast — no OCR overhead for machine-readable PDFs) ----
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

    # ---- Image extraction (export pictures to disk) ----
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

                img_elem_id = _node_id("image")
                extracted_elements.append(
                    ParsedElement(
                        element_id=img_elem_id,
                        type="image",
                        page=page,
                        content="",
                        metadata={"figure_caption": cap, "image_path": img_file, "image_index": idx},
                    )
                )
                image_count += 1

                if cap:
                    extracted_elements.append(
                        ParsedElement(
                            element_id=_node_id("caption"),
                            type="caption",
                            page=page,
                            content=cap,
                            metadata={"linked_image_element_id": img_elem_id},
                        )
                    )

                images.append({
                    "image_id": img_elem_id,
                    "image_path": img_file,
                    "page": page,
                    "caption": cap,
                })

            except Exception:
                continue
    timings["image_extraction"] = time.perf_counter() - t0

    # ---- Table extraction (avoid export_to_markdown(doc) — use doc-free call) ----
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
                        content = fn(doc)  # pass doc to suppress deprecation warning
                    except Exception:
                        try:
                            content = fn()  # fallback for older docling versions
                        except Exception:
                            pass
                if not isinstance(content, str) or not content.strip():
                    content = str(getattr(tbl, "text", "")) if getattr(tbl, "text", None) else ""
                    content = content.strip()
                if not content:
                    continue

                extracted_elements.append(
                    ParsedElement(
                        element_id=_node_id("table"),
                        type="table",
                        page=page,
                        content=content,
                        metadata={"source": "docling_tables", "table_index": idx},
                    )
                )
                table_count += 1
            except Exception:
                continue
    timings["table_extraction"] = time.perf_counter() - t0

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
