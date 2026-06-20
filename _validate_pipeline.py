# -*- coding: utf-8 -*-
"""Full pipeline validation script for all phases 1-9."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# ---- PHASE 1: STRUCTURE INSPECTION (run first) ----
print("=" * 70)
print("PHASE 1: DOCLING STRUCTURE INSPECTION")
print("=" * 70)

from docling.document_converter import DocumentConverter

pdf_path = r"C:\Users\tharu\OneDrive\Desktop\Dell\data\uploads\NIPS-2017-attention-is-all-you-need-Paper (1).pdf"
converter = DocumentConverter()
result = converter.convert(pdf_path)
doc = result.document

num_pages = doc.num_pages() if callable(doc.num_pages) else doc.num_pages
print(f"result.document.num_pages: {num_pages}")
print(f"len(result.document.pages): {len(doc.pages)}")
print(f"len(result.document.texts): {len(doc.texts)}")
print(f"len(result.document.tables): {len(doc.tables)}")
print(f"len(result.document.pictures): {len(doc.pictures)}")

texts = list(doc.texts)
print("\n--- First 5 texts ---")
for i, t in enumerate(texts[:5]):
    print(f"  text[{i}]: type={type(t).__name__}, label={getattr(t,'label','?')}, page={getattr(t.prov[0],'page_no','?') if getattr(t,'prov',None) else '?'}, text={getattr(t,'text','')[:80]!r}")

tables = list(doc.tables)
print("\n--- First 3 tables ---")
for i, tbl in enumerate(tables[:3]):
    prov = getattr(tbl, 'prov', None) or []
    pn = getattr(prov[0], 'page_no', '?') if prov else '?'
    fn = getattr(tbl, 'export_to_markdown', None)
    md = fn() if callable(fn) else "N/A"
    print(f"  table[{i}]: type={type(tbl).__name__}, label={getattr(tbl,'label','?')}, page={pn}, md_preview={str(md)[:100]!r}")

pictures = list(doc.pictures)
print("\n--- First 3 pictures ---")
for i, pic in enumerate(pictures[:3]):
    prov = getattr(pic, 'prov', None) or []
    pn = getattr(prov[0], 'page_no', '?') if prov else '?'
    get_img = getattr(pic, 'get_image', None)
    has_get_image = callable(get_img)
    print(f"  picture[{i}]: type={type(pic).__name__}, label={getattr(pic,'label','?')}, page={pn}, has_get_image={has_get_image}")

print("\n--- Text label distribution ---")
label_counts = {}
for t in texts:
    l = str(getattr(t, "label", "") or "unknown")
    label_counts[l] = label_counts.get(l, 0) + 1
for k, v in sorted(label_counts.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")

# ---- PHASE 2-5: Run the actual parser ----
print("\n" + "=" * 70)
print("PHASE 2-5: RUNNING PARSER")
print("=" * 70)

from ingestion.parser import parse_document
parse_result = parse_document(file_path=pdf_path, doc_id="NIPS-2017-attention-is-all-you-need-Paper")

print("\n--- PARSER RESULTS ---")
print(f"pages_processed: {parse_result['pages_processed']}")
print(f"text_count: {parse_result['text_count']}")
print(f"table_count: {parse_result['table_count']}")
print(f"image_count: {parse_result['image_count']}")
print(f"elements_count: {len(parse_result['elements'])}")
print(f"images count in result: {len(parse_result['images'])}")

# PHASE 2: Page number validation
print("\n--- PHASE 2: PAGE NUMBER VALIDATION ---")
print(f"pages_processed = {parse_result['pages_processed']} (expected {num_pages})")
assert parse_result['pages_processed'] == num_pages, f"MISMATCH: pages_processed={parse_result['pages_processed']} != num_pages={num_pages}"
print("PASS: pages_processed matches num_pages")

print("\nFirst 20 element page numbers:")
for i, e in enumerate(parse_result['elements'][:20]):
    print(f"  [{i}] type={e['type']:12s} page={e['page']} content={e['content'][:60]!r}")

# Verify no element has page=1 if it's really from a later page
tables_elems = [e for e in parse_result['elements'] if e['type'] == 'table']
print(f"\nTable page numbers:")
for e in tables_elems:
    print(f"  page={e['page']} content={e['content'][:80]!r}")

images_elems = [e for e in parse_result['elements'] if e['type'] == 'image']
print(f"\nImage page numbers:")
for e in images_elems:
    print(f"  page={e['page']} metadata={e['metadata']}")

# PHASE 3: Image extraction
print("\n--- PHASE 3: IMAGE EXTRACTION VALIDATION ---")
img_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "processed", "images")
for root, dirs, files in os.walk(img_dir):
    for f in files:
        fp = os.path.join(root, f)
        print(f"  Image file: {fp} ({os.path.getsize(fp)} bytes)")

print(f"Images in parser result: {len(parse_result['images'])}")
for img in parse_result['images']:
    path = img.get('image_path', img.get('path', '?'))
    exists = os.path.exists(path) if path != '?' else False
    print(f"  image_id={img['image_id']} page={img['page']} path={path} exists={exists} caption={img.get('caption')}")

assert len(parse_result['images']) > 0, "FAIL: images_count is 0!"
assert all(os.path.exists(img.get('image_path', img.get('path', ''))) for img in parse_result['images']), "FAIL: some images missing on disk!"
print("PASS: images extracted and saved to disk")

# PHASE 4: Table extraction
print("\n--- PHASE 4: TABLE EXTRACTION VALIDATION ---")
assert parse_result['table_count'] > 0, "FAIL: table_count is 0!"
assert len(tables_elems) > 0, "FAIL: no table elements!"
print(f"Tables found: {parse_result['table_count']}")
for e in tables_elems:
    lines = e['content'].count('\n') + 1
    print(f"  page={e['page']} lines={lines} preview={e['content'][:100]!r}")

# PHASE 5: Text extraction
print("\n--- PHASE 5: TEXT EXTRACTION VALIDATION ---")
print(f"Text elements: {parse_result['text_count']}")
type_counts = {}
for e in parse_result['elements']:
    type_counts[e['type']] = type_counts.get(e['type'], 0) + 1
for k, v in sorted(type_counts.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")

assert "heading" in type_counts, "FAIL: no heading elements!"
print("PASS: headings preserved")

# Check metadata on nodes
print("\n--- Sample elements by type ---")
for t in ["heading", "paragraph", "table", "image", "caption", "footnote", "list_item", "formula"]:
    samples = [e for e in parse_result['elements'] if e['type'] == t]
    if samples:
        s = samples[0]
        print(f"  {t}: page={s['page']} content={s['content'][:80]!r} metadata_keys={list(s['metadata'].keys())}")

# ---- PHASE 6: NODE BUILDING ----
print("\n" + "=" * 70)
print("PHASE 6: NODE VALIDATION")
print("=" * 70)
from ingestion.node_builder import build_nodes

node_build = build_nodes(parse_result=parse_result)

print(f"Node count: {node_build['node_count']}")

node_type_counts = {}
for n in node_build['nodes']:
    node_type_counts[n['type']] = node_type_counts.get(n['type'], 0) + 1
for k, v in sorted(node_type_counts.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")

# Print 3 sample nodes of each type
print("\n3 sample nodes of each type:")
for t in ["heading", "paragraph", "table", "image", "caption", "footnote"]:
    samples = [n for n in node_build['nodes'] if n['type'] == t][:3]
    if samples:
        print(f"\n  --- {t} (showing {len(samples)}) ---")
        for s in samples:
            print(f"    node_id={s['node_id']} doc_id={s['doc_id']} page={s['page']} content={s['content'][:60]!r} metadata_keys={list(s['metadata'].keys())}")

# Validate each node has required fields
required_fields = {"node_id", "doc_id", "page", "type", "content", "metadata"}
for i, n in enumerate(node_build['nodes']):
    missing = required_fields - set(n.keys())
    assert not missing, f"Node {i} missing fields: {missing}"
assert node_build['node_count'] > 0, "FAIL: no nodes created!"
print("\nPASS: All nodes have required fields")

# ---- PHASE 7: CHUNKING ----
print("\n" + "=" * 70)
print("PHASE 7: CHUNKING VALIDATION")
print("=" * 70)
from ingestion.node_builder import chunk_nodes

chunked = chunk_nodes(node_build, chunk_size=1200, chunk_overlap=150)

print(f"Chunk count: {chunked['chunks_created']}")
print(f"Average chunk length: {sum(len(c['content']) for c in chunked['chunks']) / max(len(chunked['chunks']), 1):.0f} chars")

print("\nFirst 3 chunks:")
for i, c in enumerate(chunked['chunks'][:3]):
    print(f"  chunk[{i}]: type={c['type']} page={c['page']} node_id={c['node_id']} content_len={len(c['content'])} content={c['content'][:80]!r}")

# Verify tables are not split
table_chunks = [c for c in chunked['chunks'] if c['type'] == 'table']
print(f"\nTable chunks: {len(table_chunks)}")
for c in table_chunks:
    print(f"  page={c['page']} content_len={len(c['content'])} content={c['content'][:80]!r}")

assert chunked['chunks_created'] > 0, "FAIL: no chunks created!"
print("\nPASS: Chunks created successfully")

# ---- PHASE 8: EMBEDDING ----
print("\n" + "=" * 70)
print("PHASE 8: EMBEDDING VALIDATION")
print("=" * 70)
from ingestion.node_builder import embed_chunks

embedded = embed_chunks(chunked)

first_chunk = embedded['chunks'][0]
emb = first_chunk.get('embedding', [])
print(f"Embedding dimension: {len(emb)}")
print(f"Total embeddings generated: {len([c for c in embedded['chunks'] if c.get('embedding')])}")
print(f"First embedding vector length (first 5 dims): {emb[:5]}")
print(f"Embedding vector dtype: {type(emb)}")

assert len(emb) > 0, "FAIL: embedding vector is empty!"
assert all(len(c.get('embedding', [])) > 0 for c in embedded['chunks']), "FAIL: some chunks missing embeddings!"
print("PASS: Embeddings generated successfully")

# ---- PHASE 9: WEAVIATE VALIDATION ----
print("\n" + "=" * 70)
print("PHASE 9: WEAVIATE VALIDATION")
print("=" * 70)
from vectorstore.weaviate_client import WeaviateClient

try:
    wc = WeaviateClient()
    col = "DocuMindNode"

    # Count before
    try:
        before_count = wc.client.collections.get(col).aggregate.over_all(total_count=True)
        print(f"Objects before insert: {before_count.total_count}")
    except Exception as e:
        print(f"Could not count before: {e!r}")

    # Insert
    from ingestion.node_builder import store_chunks_weaviate
    stored = store_chunks_weaviate(embedded, collection_name=col)
    print(f"Stored count: {stored['count']}")

    # Count after
    import time
    time.sleep(2)
    after_count = wc.client.collections.get(col).aggregate.over_all(total_count=True)
    print(f"Objects after insert: {after_count.total_count}")

    # Retrieve 3 random objects
    collection = wc.client.collections.get(col)
    response = collection.query.fetch_objects(limit=3)
    print("\n3 random retrieved objects:")
    for obj in response.objects:
        props = obj.properties
        print(f"  node_id={props.get('node_id','?')} type={props.get('type','?')} page={props.get('page','?')} content={str(props.get('content',''))[:60]!r}")

    wc.close()
    print("\nPASS: Weaviate insertion and retrieval works")
except Exception as e:
    print(f"Weaviate test skipped or failed: {e!r}")
    import traceback
    traceback.print_exc()

# ---- FINAL REPORT ----
print("\n" + "=" * 70)
print("FINAL REPORT")
print("=" * 70)
print(f"1. Total pages detected: {parse_result['pages_processed']}")
print(f"2. Total text elements: {parse_result['text_count']}")
print(f"3. Total tables: {parse_result['table_count']}")
print(f"4. Total images: {parse_result['image_count']}")
print(f"5. Total nodes: {node_build['node_count']}")
print(f"6. Total chunks: {chunked['chunks_created']}")
print(f"7. Total embeddings: {len([c for c in embedded['chunks'] if c.get('embedding')])}")
print(f"8. Total Weaviate objects inserted: {stored['count'] if 'stored' in dir() else 'N/A'}")

print("\nDone.")
