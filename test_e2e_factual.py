"""End-to-end factual answer validation for 3M 2015 10-K."""
import os

os.environ.setdefault("ENABLE_EMBEDDINGS", "true")
os.environ.setdefault("ENABLE_WEAVIATE", "true")

from retrieval.hybrid_search import retrieve_candidates
from retrieval.reranker import rerank
from generation.prompt_builder import build_prompt
from generation.groq_client import chat

DOC_ID = "3M_2015_10K"

QUESTIONS = [
    "As of December 31, 2015, how many employees did 3M have in total, and how many inside vs outside the United States?",
    "How much did 3M spend in 2015 on research, development and related expenses, and on environmental capital projects?",
    "What were 3M's net sales in 2015 and net income attributable to 3M in 2015, and how did both compare to 2014?",
]

GROUND_TRUTH = {
    0: ["89,446", "35,973", "53,473"],
    1: ["1.763", "26"],
    2: ["30,274", "4,833", "31,821", "4,956"],
}


def answer_query(query: str) -> str:
    candidates = retrieve_candidates(query, doc_id=DOC_ID)
    top = rerank(query, candidates)
    prompt = build_prompt(query=query, supporting=top, exceptions=[], contradictions=[], risks=[])
    return chat(prompt["user"], system=prompt["system"], factual=prompt.get("factual", False))


if __name__ == "__main__":
    for i, q in enumerate(QUESTIONS):
        print(f"\n{'='*60}\nQ: {q}\n{'='*60}")
        try:
            answer = answer_query(q)
            print(f"ANSWER:\n{answer}")
            hits = [n for n in GROUND_TRUTH[i] if n in answer.replace(",", ",")]
            print(f"\nGround truth hits: {len(hits)}/{len(GROUND_TRUTH[i])} -> {hits}")
        except Exception as e:
            print(f"ERROR: {e}")
