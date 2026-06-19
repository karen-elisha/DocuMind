"""
Isolated test: parser + node builder.
Usage:  python test_nodes.py <pdf_path>
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

pdf_path = sys.argv[1] if len(sys.argv) > 1 else None
if not pdf_path or not os.path.exists(pdf_path):
    print("Usage: python test_nodes.py <path_to_pdf>")
    sys.exit(1)

doc_id = os.path.splitext(os.path.basename(pdf_path))[0]

print(f"Testing nodes on: {pdf_path}")
print()

from ingestion.parser import parse_document
from ingestion.node_builder import build_nodes, chunk_nodes

t0 = time.perf_counter()

parse_result = parse_document(file_path=pdf_path, doc_id=doc_id)
t1 = time.perf_counter()
print(f"[test] Parse:  {t1-t0:.2f}s")

node_build = build_nodes(parse_result=parse_result, vision_results={})
t2 = time.perf_counter()
print(f"[test] Build:  {t2-t1:.2f}s")

chunked = chunk_nodes(node_build)
t3 = time.perf_counter()
print(f"[test] Chunk:  {t3-t2:.2f}s")

print()
print("=" * 50)
print("  NODE & CHUNK RESULTS")
print("=" * 50)
print(f"  Nodes:              {node_build['node_count']}")
from collections import Counter
type_counts = Counter(n['type'] for n in node_build['nodes'])
for t, c in type_counts.most_common():
    print(f"    {t:15s}  {c}")
print(f"  Chunks:             {chunked['chunks_created']}")
avg = sum(len(x['content']) for x in chunked['chunks']) / max(chunked['chunks_created'], 1)
print(f"  Avg chunk len:      {avg:.0f} chars")
print(f"  Total time:         {t3-t0:.2f}s")
print("=" * 50)
