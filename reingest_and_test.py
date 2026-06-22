"""Re-ingest 3M 2015 10-K and validate factual retrieval."""
import os
import time

os.environ.setdefault("ENABLE_EMBEDDINGS", "true")
os.environ.setdefault("ENABLE_WEAVIATE", "true")

from ingestion.pymupdf_parser import parse_document_pymupdf
from ingestion.node_builder import run_ingestion_pipeline
from retrieval.hybrid_search import HybridRetriever
from retrieval.reranker import rerank
from retrieval.query_expansion import expand_query

DOC_ID = "3M_2015_10K"
PDF = "data/uploads/3M_2015_10K.pdf"

QUESTIONS = [
    {
        "query": "As of December 31, 2015, how many employees did 3M have in total, and how many inside vs outside the United States?",
        "needles": ["89,446", "35,973", "53,473"],
    },
    {
        "query": "How much did 3M spend in 2015 on research, development and related expenses, and on environmental capital projects?",
        "needles": ["1.763", "26"],
    },
    {
        "query": "What were 3M's net sales in 2015 and net income attributable to 3M in 2015, and how did both compare to 2014?",
        "needles": ["30,274", "4,833", "31,821", "4,956"],
    },
]


def ingest():
    print("=== INGESTING ===")
    t0 = time.perf_counter()
    result = parse_document_pymupdf(PDF, DOC_ID)
    stats = run_ingestion_pipeline(parse_result=result, vision_results={})
    print(f"Ingest done in {time.perf_counter() - t0:.1f}s: {stats}")
    return stats


def test_retrieval():
    print("\n=== RETRIEVAL TESTS ===")
    all_pass = True
    for q in QUESTIONS:
        query = q["query"]
        needles = q["needles"]
        variants = expand_query(query)
        all_candidates = []
        seen = set()
        retriever = HybridRetriever()
        try:
            for v in variants:
                hr = retriever.retrieve(query=v, doc_id=DOC_ID, semantic_limit=40, keyword_limit=40)
                for n in hr["semantic_results"] + hr["keyword_results"]:
                    nid = n.get("node_id")
                    if nid and nid not in seen:
                        seen.add(nid)
                        all_candidates.append(n)
        finally:
            retriever.close()

        top = rerank(query, all_candidates, top_k=5)
        top3_text = " ".join(str(t.get("content", "")) for t in top[:3])
        hits = [n for n in needles if n in top3_text]
        passed = len(hits) >= max(1, len(needles) // 2)
        all_pass = all_pass and passed

        print(f"\nQ: {query[:70]}...")
        print(f"  Variants: {len(variants)} | Candidates: {len(all_candidates)} | Needles found: {hits}/{needles}")
        print(f"  PASS: {passed}")
        for i, t in enumerate(top[:3], 1):
            content = (t.get("content") or "")[:200].replace("\n", " ")
            print(f"  {i}. page={t.get('page')} type={t.get('type')} score={t.get('score', 0):.3f}")
            print(f"     {content}")

    return all_pass


if __name__ == "__main__":
    ingest()
    ok = test_retrieval()
    print(f"\n=== OVERALL: {'PASS' if ok else 'FAIL'} ===")
