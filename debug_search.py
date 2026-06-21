"""Debug Weaviate search directly."""
import sys, os, io
sys.path.insert(0, os.getcwd())
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from vectorstore.weaviate_client import DocuMindWeaviateClient
from weaviate.classes.query import MetadataQuery, Filter

client = DocuMindWeaviateClient()
with client.client:
    col = client.client.collections.get(client.collection_name)
    count = col.aggregate.over_all().total_count
    print("Total objects:", count)

    for q in ["document", "figure", "page", "inhibitor", "Langmuir"]:
        res = col.query.bm25(q, limit=5, return_metadata=MetadataQuery(score=True))
        print("BM25 %r: %d results" % (q, len(res.objects)))
        for o in res.objects:
            p = dict(o.properties)
            s = o.metadata.score if o.metadata else "?"
            print("  score=%s type=%s doc_id=%s" % (s, p.get("type",""), p.get("doc_id","")))

    # Filter by doc_id
    print()
    print("With doc_id filter:")
    res = col.query.bm25(
        "inhibitor", limit=5,
        filters=Filter.by_property("doc_id").equal("embedded-images-tables"),
        return_metadata=MetadataQuery(score=True)
    )
    print("BM25 'inhibitor' filtered: %d results" % len(res.objects))
    for o in res.objects:
        p = dict(o.properties)
        s = o.metadata.score if o.metadata else "?"
        print("  score=%s type=%s content=%s" % (s, p.get("type",""), p.get("content","")[:120]))
