"""
Isolated test: parser → nodes → chunks → embeddings.
Usage:  python test_embeddings.py <pdf_path>
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

pdf_path = sys.argv[1] if len(sys.argv) > 1 else None
if not pdf_path or not os.path.exists(pdf_path):
    print("Usage: python test_embeddings.py <path_to_pdf>")
    sys.exit(1)

doc_id = os.path.splitext(os.path.basename(pdf_path))[0]

print(f"Testing embeddings on: {pdf_path}")
print()

from ingestion.parser import parse_document
from ingestion.node_builder import build_nodes, chunk_nodes, embed_chunks

t0 = time.perf_counter()

parse_result = parse_document(file_path=pdf_path, doc_id=doc_id)
t1 = time.perf_counter()
print(f"[test] Parse:      {t1-t0:.2f}s")

node_build = build_nodes(parse_result=parse_result, vision_results={})
t2 = time.perf_counter()
print(f"[test] Build:      {t2-t1:.2f}s")

chunked = chunk_nodes(node_build)
t3 = time.perf_counter()
print(f"[test] Chunk:      {t3-t2:.2f}s")

embedded = embed_chunks(chunked)
t4 = time.perf_counter()
print(f"[test] Embeddings: {t4-t3:.2f}s")

print()
print("=" * 50)
print("  EMBEDDING RESULTS")
print("=" * 50)
chunks = embedded['chunks']
embed_dims = set()
for c in chunks:
    emb = c.get('embedding', [])
    if emb:
        embed_dims.add(len(emb))
print(f"  Chunks:             {len(chunks)}")
print(f"  With embeddings:    {sum(1 for c in chunks if c.get('embedding'))}")
print(f"  Embedding dims:     {embed_dims if embed_dims else 'N/A'}")
if chunks and chunks[0].get('embedding'):
    v = chunks[0]['embedding']
    print(f"  Sample vec[:5]:    {[round(x,4) for x in v[:5]]}")
print(f"  Total time:         {t4-t0:.2f}s")
print("=" * 50)
