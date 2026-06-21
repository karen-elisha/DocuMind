# -*- coding: utf-8 -*-
"""Phase 1: Docling Structure Inspection"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Force UTF-8 for stdout
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from docling.document_converter import DocumentConverter

pdf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "uploads", "NIPS-2017-attention-is-all-you-need-Paper (1).pdf")
converter = DocumentConverter()
result = converter.convert(pdf_path)
doc = result.document

print("=== PHASE 1: DOCLING STRUCTURE INSPECTION ===")
print("num_pages:", doc.num_pages)
print("pages type:", type(doc.pages))
print("pages len:", len(doc.pages))
print()
print("texts type:", type(doc.texts))
print("texts len:", len(doc.texts))
print()
print("tables type:", type(doc.tables))
print("tables len:", len(doc.tables))
print()
print("pictures type:", type(doc.pictures))
print("pictures len:", len(doc.pictures))
print()

# Inspect first 5 texts
print("=== First 5 texts ===")
texts = list(doc.texts)
for i, t in enumerate(texts[:5]):
    print(f"--- text[{i}] ---")
    print(f"  type: {type(t).__name__}")
    for attr in ["label", "type", "kind"]:
        val = getattr(t, attr, "N/A")
        print(f"  {attr}: {val}")
    print(f"  page: {getattr(t, 'page', 'N/A')}")
    prov = getattr(t, "prov", None) or []
    if prov:
        print(f"  prov[0] page_no: {getattr(prov[0], 'page_no', 'N/A')}")
    txt = getattr(t, "text", None) or getattr(t, "content", None) or ""
    print(f"  text[:150]: {str(txt)[:150]}")
    print()

# Inspect first 3 tables
print("=== First 3 tables ===")
tables = list(doc.tables)
for i, tbl in enumerate(tables[:3]):
    print(f"--- table[{i}] ---")
    print(f"  type: {type(tbl).__name__}")
    for attr in ["label", "type"]:
        val = getattr(tbl, attr, "N/A")
        print(f"  {attr}: {val}")
    print(f"  page: {getattr(tbl, 'page', 'N/A')}")
    prov = getattr(tbl, "prov", None) or []
    if prov:
        print(f"  prov[0] page_no: {getattr(prov[0], 'page_no', 'N/A')}")
    for method in ["export_to_markdown", "to_markdown", "to_markdown_str", "export_to_text"]:
        fn = getattr(tbl, method, None)
        if callable(fn):
            try:
                md = fn()
                print(f"  {method}(): {str(md)[:300]}")
                break
            except:
                pass
    print()

# Inspect first 3 pictures
print("=== First 3 pictures ===")
pictures = list(doc.pictures)
for i, pic in enumerate(pictures[:3]):
    print(f"--- picture[{i}] ---")
    print(f"  type: {type(pic).__name__}")
    for attr in ["label", "type", "caption", "title"]:
        val = getattr(pic, attr, "N/A")
        print(f"  {attr}: {val}")
    print(f"  page: {getattr(pic, 'page', 'N/A')}")
    prov = getattr(pic, "prov", None) or []
    if prov:
        print(f"  prov[0] page_no: {getattr(prov[0], 'page_no', 'N/A')}")
    for method in ["save_picture", "export_picture", "pil_image", "image", "get_image"]:
        fn = getattr(pic, method, None)
        if callable(fn):
            print(f"  {method}: exists and is callable")
        elif fn is not None:
            print(f"  {method}: exists (type={type(fn).__name__})")
        else:
            print(f"  {method}: None")
    img = getattr(pic, "image", None)
    if img is not None:
        print(f"  image type: {type(img).__name__}")
    print()

# More detailed - check text labels to understand classification
print("=== Text label distribution ===")
label_counts = {}
for t in texts:
    l = str(getattr(t, "label", "") or getattr(t, "type", "") or "unknown")
    label_counts[l] = label_counts.get(l, 0) + 1
for k, v in sorted(label_counts.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")
print()

print("=== Checking prov objects on text items (first 20) ===")
for i, t in enumerate(texts[:20]):
    prov = getattr(t, "prov", None) or []
    if prov:
        p0 = prov[0]
        pn = getattr(p0, "page_no", "?")
        print(f"  text[{i}] label={getattr(t,'label','?')} page_no={pn}")
    else:
        print(f"  text[{i}] label={getattr(t,'label','?')} no prov")
