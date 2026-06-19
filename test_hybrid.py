# test_hybrid.py

from retrieval.hybrid_search import HybridRetriever

retriever = HybridRetriever()

results = retriever.retrieve(
     "What does the decoder do?"
)

print("\n===== SEMANTIC =====\n")

for i, obj in enumerate(results["semantic_results"][:3], start=1):
    print(f"{i}.")
    print(obj.properties.get("content", "")[:300])
    print()

print("\n===== KEYWORD =====\n")

for i, obj in enumerate(results["keyword_results"][:3], start=1):
    print(f"{i}.")
    print(obj.properties.get("content", "")[:300])
    print()

retriever.close()