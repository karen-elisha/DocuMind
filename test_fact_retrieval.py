"""Validate factual retrieval fixes for 3M 2015 10-K."""
import time

from ingestion.pymupdf_parser import parse_document_pymupdf
from ingestion.node_builder import build_nodes, chunk_nodes
from retrieval.hybrid_search import retrieve_candidates
from retrieval.reranker import rerank

DOC_ID = "3M_2015_10K"
PDF = "data/uploads/3M_2015_10K.pdf"

TESTS = [
    (
        "As of December 31, 2015, how many employees did 3M have in total, and how many inside vs outside the United States?",
        ["89,446", "35,973", "53,473"],
    ),
    (
        "How much did 3M spend in 2015 on research, development and related expenses, and on environmental capital projects?",
        ["1.763", "26"],
    ),
    (
        "What were 3M's net sales in 2015 and net income attributable to 3M in 2015, and how did both compare to 2014?",
        ["30,274", "4,833", "31,821", "4,956"],
    ),
]


def check_chunks():
    result = parse_document_pymupdf(PDF, DOC_ID)
    nodes = build_nodes(result, {})
    chunked = chunk_nodes(nodes)
    employee = [c for c in chunked["chunks"] if "89,446" in c.get("content", "")]
    rd = [c for c in chunked["chunks"] if "1.763" in c.get("content", "")]
    financial = [c for c in chunked["chunks"] if "30,274" in c.get("content", "") and "4,833" in c.get("content", "")]
    fact_chunks = [c for c in chunked["chunks"] if c.get("type") == "fact"]
    print(f"Chunks total: {len(chunked['chunks'])} (fact={len(fact_chunks)})")
    print(f"Employee chunks: {len(employee)}")
    print(f"R&D chunks: {len(rd)}")
    print(f"Annual financial chunks: {len(financial)}")
    return bool(employee), bool(rd), bool(financial)


def check_retrieval():
    all_pass = True
    for query, needles in TESTS:
        t0 = time.perf_counter()
        all_candidates = retrieve_candidates(query, doc_id=DOC_ID)
        top = rerank(query, all_candidates, top_k=5)
        elapsed = time.perf_counter() - t0
        top3_text = " ".join(str(t.get("content", "")) for t in top[:3])
        hits = [n for n in needles if n in top3_text]
        passed = len(hits) >= max(1, len(needles) // 2)
        all_pass = all_pass and passed

        print(f"\nQuery: {query[:70]}...")
        print(f"Time: {elapsed:.1f}s | Needles in top-3: {hits}/{needles} | PASS={passed}")
        for i, t in enumerate(top[:3], 1):
            content = (t.get("content") or "")[:160].replace("\n", " ")
            print(f"  {i}. page={t.get('page')} type={t.get('type')} score={t.get('score', 0):.3f}")
            print(f"     {content}")
    return all_pass


if __name__ == "__main__":
    print("=== Chunk enrichment check ===")
    emp_ok, rd_ok, fin_ok = check_chunks()
    print(f"Chunk checks: employees={emp_ok} rd={rd_ok} financial={fin_ok}")
    print("\n=== Live retrieval check (requires indexed doc) ===")
    ok = check_retrieval()
    print(f"\n=== OVERALL: {'PASS' if ok else 'FAIL'} ===")
