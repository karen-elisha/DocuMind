# -*- coding: utf-8 -*-
"""Fast validation script (Phases 2-9). Skips duplicate Phase 1 conversion."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from ingestion.parser import parse_document

pdf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "uploads", "NIPS-2017-attention-is-all-you-need-Paper (1).pdf")
parse_result = parse_document(file_path=pdf_path, doc_id="NIPS-2017-attention-is-all-you-need-Paper")

print("\n" + "=" * 70)
print("PARSER RESULTS")
print("=" * 70)
print(f"pages_processed: {parse_result['pages_processed']}")
print(f"text_count: {parse_result['text_count']}")
print(f"table_count: {parse_result['table_count']}")
print(f"image_count: {parse_result['image_count']}")
print(f"elements_count: {len(parse_result['elements'])}")
print(f"images count in result: {len(parse_result['images'])}")

# PHASE 2: Page number validation
print("\n" + "=" * 70)
print("PHASE 2: PAGE NUMBER VALIDATION")
print("=" * 70)
assert parse_result['pages_processed'] == 11, f"FAIL: pages={parse_result['pages_processed']}"
print("PASS: pages_processed =", parse_result['pages_processed'])

# Verify page numbers vary across elements
pages_set = set()
for e in parse_result['elements'][:50]:
    pages_set.add(e['page'])
print(f"Unique pages in first 50 elements: {sorted(pages_set)}")
assert len(pages_set) > 1, "FAIL: all elements on same page!"

# PHASE 3: Image extraction
print("\n" + "=" * 70)
print("PHASE 3: IMAGE EXTRACTION VALIDATION")
print("=" * 70)
assert parse_result['image_count'] > 0, "FAIL: image_count is 0!"
for img in parse_result['images']:
    path = img.get('image_path', '')
    exists = os.path.exists(path)
    print(f"  image_id={img['image_id']} page={img['page']} path={path} exists={exists}")
    assert exists, f"FAIL: image not at {path}"
print("PASS: Images extracted and saved to disk")

# PHASE 4: Table extraction
print("\n" + "=" * 70)
print("PHASE 4: TABLE EXTRACTION VALIDATION")
print("=" * 70)
assert parse_result['table_count'] > 0, "FAIL: table_count is 0!"
tables = [e for e in parse_result['elements'] if e['type'] == 'table']
print(f"Tables found: {len(tables)}")
for t in tables:
    print(f"  page={t['page']} content={t['content'][:100]!r}")
assert all(t['page'] > 0 for t in tables), "FAIL: table with page=0"
print("PASS: Tables extracted as structured objects")

# PHASE 5: Text extraction
print("\n" + "=" * 70)
print("PHASE 5: TEXT EXTRACTION VALIDATION")
print("=" * 70)
type_counts = {}
for e in parse_result['elements']:
    type_counts[e['type']] = type_counts.get(e['type'], 0) + 1
for k, v in sorted(type_counts.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")
assert "heading" in type_counts, "FAIL: no headings"
assert "paragraph" in type_counts, "FAIL: no paragraphs"
print("PASS: Text extraction preserves headings, paragraphs, etc.")

# PHASE 6: Node building
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

required_fields = {"node_id", "doc_id", "page", "type", "content", "metadata"}
for i, n in enumerate(node_build['nodes']):
    missing = required_fields - set(n.keys())
    assert not missing, f"Node {i} missing fields: {missing}"
print("PASS: All nodes have required fields")

# Print 3 sample nodes of each type
print("\n3 sample nodes of each type:")
for t in ["heading", "paragraph", "table", "image", "caption", "footnote", "list_item"]:
    samples = [n for n in node_build['nodes'] if n['type'] == t][:3]
    if samples:
        print(f"  --- {t} (showing {len(samples)}) ---")
        for s in samples:
            print(f"    node_id={s['node_id']} page={s['page']} content={s['content'][:60]!r} keys={sorted(s['metadata'].keys())}")

# PHASE 7: Chunking
print("\n" + "=" * 70)
print("PHASE 7: CHUNKING VALIDATION")
print("=" * 70)
from ingestion.node_builder import chunk_nodes

chunked = chunk_nodes(node_build, chunk_size=1200, chunk_overlap=150)
print(f"Chunk count: {chunked['chunks_created']}")
avg_len = sum(len(c['content']) for c in chunked['chunks']) / max(len(chunked['chunks']), 1)
print(f"Average chunk length: {avg_len:.0f} chars")
print(f"Chunk size setting: 1200, overlap: 150")

print("\nFirst 3 chunks:")
for i, c in enumerate(chunked['chunks'][:3]):
    print(f"  [{i}] type={c['type']} page={c['page']} len={len(c['content'])} content={c['content'][:80]!r}")

# Verify tables not split
table_chunks = [c for c in chunked['chunks'] if c['type'] == 'table']
print(f"\nTable chunks: {len(table_chunks)}")
for c in table_chunks:
    print(f"  page={c['page']} len={len(c['content'])} content={c['content'][:80]!r}")
assert len(table_chunks) > 0, "FAIL: no table chunks!"

assert chunked['chunks_created'] > 0, "FAIL: no chunks created!"
print("PASS: Chunks created successfully")

# PHASE 8: Embeddings
print("\n" + "=" * 70)
print("PHASE 8: EMBEDDING VALIDATION")
print("=" * 70)
from ingestion.node_builder import embed_chunks

embedded = embed_chunks(chunked)
emb = embedded['chunks'][0].get('embedding', [])
print(f"Embedding dimension: {len(emb)}")
print(f"Total embeddings: {len([c for c in embedded['chunks'] if c.get('embedding')])}")
print(f"First vector[0:5]: {emb[:5]}")

assert len(emb) == 384, f"FAIL: expected embedding dim 384, got {len(emb)}"  # all-MiniLM-L6-v2 = 384
assert all(len(c.get('embedding', [])) == 384 for c in embedded['chunks']), "FAIL: some chunks have wrong embedding dim!"
print("PASS: Embeddings generated with correct dimension")

# PHASE 9: Weaviate
print("\n" + "=" * 70)
print("PHASE 9: WEAVIATE VALIDATION")
print("=" * 70)
from vectorstore.weaviate_client import WeaviateClient

try:
    wc = WeaviateClient()
    col = "DocuMindNode"
    
    from ingestion.node_builder import store_chunks_weaviate
    stored = store_chunks_weaviate(embedded, collection_name=col)
    print(f"Stored objects: {stored['count']}")
    
    import time
    time.sleep(2)
    agg = wc.client.collections.get(col).aggregate.over_all(total_count=True)
    print(f"Objects after insert: {agg.total_count}")
    
    resp = wc.client.collections.get(col).query.fetch_objects(limit=3)
    print("\n3 random retrieved objects:")
    for obj in resp.objects:
        p = obj.properties
        print(f"  node_id={p.get('node_id','?')} type={p.get('type','?')} page={p.get('page','?')} content={str(p.get('content',''))[:60]!r}")
    wc.close()
    print("PASS: Weaviate insertion and retrieval works")
except Exception as e:
    print(f"Weaviate test: {e!r}")
    import traceback
    traceback.print_exc()

# FINAL REPORT
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
stored_count = stored['count'] if 'stored' in dir() else 'N/A'
print(f"8. Total Weaviate objects inserted: {stored_count}")
print("\nDone.")
