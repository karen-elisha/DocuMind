"""
Isolated test: parser → nodes → chunks → embeddings → Weaviate.
Usage:  python test_weaviate.py <pdf_path>
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

pdf_path = sys.argv[1] if len(sys.argv) > 1 else None
if not pdf_path or not os.path.exists(pdf_path):
    print("Usage: python test_weaviate.py <path_to_pdf>")
    sys.exit(1)

doc_id = os.path.splitext(os.path.basename(pdf_path))[0]

print(f"Testing full pipeline on: {pdf_path}")
print()

from ingestion.parser import parse_document
from ingestion.node_builder import build_nodes, chunk_nodes, embed_chunks, store_chunks_weaviate

t0 = time.perf_counter()

parse_result = parse_document(file_path=pdf_path, doc_id=doc_id)
t1 = time.perf_counter()
print(f"[test] Parse:        {t1-t0:.2f}s")

node_build = build_nodes(parse_result=parse_result, vision_results={})
t2 = time.perf_counter()
print(f"[test] Nodes:        {t2-t1:.2f}s")

chunked = chunk_nodes(node_build)
t3 = time.perf_counter()
print(f"[test] Chunks:       {t3-t2:.2f}s")

embedded = embed_chunks(chunked)
t4 = time.perf_counter()
print(f"[test] Embeddings:   {t4-t3:.2f}s")

stored = store_chunks_weaviate(embedded)
t5 = time.perf_counter()
print(f"[test] Weaviate:     {t5-t4:.2f}s")

print()
print("=" * 50)
print("  FULL PIPELINE RESULTS")
print("=" * 50)
print(f"  Pages:             {parse_result['pages_processed']}")
print(f"  Elements:          {len(parse_result['elements'])}")
print(f"  Nodes:             {node_build['node_count']}")
print(f"  Chunks:            {chunked['chunks_created']}")
print(f"  Embeddings:        {sum(1 for c in embedded['chunks'] if c.get('embedding'))}")
print(f"  Weaviate stored:   {stored['count']}")
print(f"  Total time:        {t5-t0:.2f}s")
print("=" * 50)
