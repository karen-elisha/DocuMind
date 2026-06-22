"""Profile optimized query pipeline latency."""
import os
import time

os.environ.setdefault("ENABLE_EMBEDDINGS", "true")
os.environ.setdefault("ENABLE_WEAVIATE", "true")

DOC_ID = "3M_2015_10K"
QUERY = "As of December 31, 2015, how many employees did 3M have in total, and how many inside vs outside the United States?"

from retrieval.hybrid_search import retrieve_candidates, warm_retrieval
from retrieval.reranker import rerank, warm_reranker
from generation.prompt_builder import build_prompt
from generation.groq_client import chat

print("=== WARMUP ===")
t0 = time.perf_counter()
warm_reranker()
warm_retrieval()
print(f"  Warmup: {time.perf_counter()-t0:.2f}s")

QUESTIONS = [
    QUERY,
    "How much did 3M spend in 2015 on research, development and related expenses?",
    "What were 3M's net sales in 2015 and net income attributable to 3M in 2015?",
]

for q in QUESTIONS:
    print(f"\n=== {q[:60]}... ===")
    t_total = time.perf_counter()

    t0 = time.perf_counter()
    candidates = retrieve_candidates(q, doc_id=DOC_ID)
    t_ret = time.perf_counter() - t0

    t0 = time.perf_counter()
    top = rerank(q, candidates)
    t_rer = time.perf_counter() - t0

    t0 = time.perf_counter()
    prompt = build_prompt(query=q, supporting=top, exceptions=[], contradictions=[], risks=[])
    answer = chat(prompt["user"], system=prompt["system"], factual=True)
    t_llm = time.perf_counter() - t0

    total = time.perf_counter() - t_total
    print(f"  retrieval={t_ret:.2f}s  rerank={t_rer:.2f}s  llm={t_llm:.2f}s  TOTAL={total:.2f}s")
    print(f"  candidates={len(candidates)}  answer={answer[:100]}...")
