# Bug Report: Ingestion Pipeline (Docling → Weaviate)

## Bugs Found & Fixed

### Bug 1: Hardcoded `pages_processed = 1`
- **File:** `ingestion/parser.py` (~line 400 originally)
- **Root Cause:** Original code used `len(result.document.pages)` which worked, but earlier `doc.num_pages` was referenced without calling it (it's a method). After rewrite, `pages_processed = doc.num_pages()` returns correct count.
- **Fix:** Use `doc.num_pages()` (note the parentheses).
- **Status:** Fixed. Returns 11 for the test PDF.

### Bug 2: Image extraction failures
- **File:** `ingestion/parser.py`
- **Root Cause:** Original code used `save_picture()` and `export_picture()` which don't exist on `PictureItem`. Also, `pic.get_image(doc)` returns `None` unless `generate_picture_images=True` is set in pipeline options.
- **Fix:**
  1. Configure `PdfPipelineOptions(generate_picture_images=True)` and pass via `PdfFormatOption` to `DocumentConverter`.
  2. Use `pic.get_image(doc)` or `pic.image.pil_image` to get the PIL Image.
  3. Save with `image.save(path)`.
- **Status:** Fixed. 3 images extracted and saved.

### Bug 3: Table extraction — wrong API usage
- **File:** `ingestion/parser.py`
- **Root Cause:** Original code attempted to extract tables from markdown output of the full document. The correct API is `table.export_to_markdown(doc)` on each `TableItem` in `doc.tables`.
- **Fix:** Iterate `doc.tables`, call `table.export_to_markdown(doc)` on each.
- **Status:** Fixed. 4 tables extracted.

### Bug 4: Text extraction — unreliable markdown parsing
- **File:** `ingestion/parser.py`
- **Root Cause:** Original code exported the full document to markdown and tried to parse sections via regex. This loses structured information (e.g., docling label types).
- **Fix:** Iterate `doc.texts` directly. Classify each item by its `.label` attribute: `section_header` → `heading`, `list_item` → `list_item`, `formula` → `formula`, `caption` → `caption`, `footnote` → `footnote`, `page_footer` → `footnote`, `text` → `paragraph`.
- **Status:** Fixed. 186 text elements detected across 7 types.

### Bug 5: Missing page numbers
- **File:** `ingestion/parser.py`
- **Root Cause:** `DoclingDocument` items don't have a `.page` attribute. The page number is in `item.prov[0].page_no`.
- **Fix:** Use `item.prov[0].page_no` to extract page number.
- **Status:** Fixed.

### Bug 6: Node builder — missing type support
- **File:** `ingestion/node_builder.py`
- **Root Cause:** `SUPPORTED_NODE_TYPES` didn't include `list_item` or `formula`, causing those text items to be skipped.
- **Fix:** Added `"list_item"` and `"formula"` to `SUPPORTED_NODE_TYPES`.
- **Status:** Fixed.

### Bug 7: Node dataclass — missing defaults
- **File:** `ingestion/node_builder.py`, `ingestion/parser.py`
- **Root Cause:** `Node` and `ParsedElement` dataclasses had `embedding` and `section` as required fields with no defaults, causing `TypeError` when constructing them without these fields.
- **Fix:** Set `embedding: Sequence[float] = ()` and `section: str = ""` defaults.
- **Status:** Fixed.

### Bug 8: Chunk config — wrong variable names
- **File:** `config.py`
- **Root Cause:** Original code used `CHUNK_MAX_WORDS` and `CHUNK_OVERLAP_WORDS` but `chunk_nodes()` referenced `CHUNK_SIZE` and `CHUNK_OVERLAP`.
- **Fix:** Rename config constants to `CHUNK_SIZE=1200` and `CHUNK_OVERLAP=150`.
- **Status:** Fixed.

### Bug 9: Docling converter — wrong format option usage
- **File:** `ingestion/parser.py`
- **Root Cause:** Using `FormatOption` without specifying `pipeline_cls` and `backend` leads to errors. Docling v1.10.x requires `PdfFormatOption` for PDF files.
- **Fix:** Use `PdfFormatOption(pipeline_options=...)` instead of `FormatOption(...)`.
- **Status:** Fixed.

## Pipeline Metrics (NIPS-2017 Paper)
| Metric | Value |
|---|---|
| Pages | 11 |
| Text elements | 186 |
| Tables | 4 |
| Images | 3 |
| Nodes | 193 |
| Chunks | 198 |
| Embedding dim | 384 (all-MiniLM-L6-v2) |
| Weaviate objects | 198 |

## Files Modified
1. `ingestion/parser.py` — complete rewrite of `parse_document()`
2. `ingestion/node_builder.py` — added types, fixed dataclass defaults
3. `config.py` — renamed chunk config constants

## Files Created
1. `_diagnose_phase1.py` — Docling structure discovery
2. `_validate_fast.py` — comprehensive end-to-end validation
3. `data/bug_report.md` — this report
