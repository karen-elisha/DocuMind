import weaviate, json
from weaviate.classes.query import MetadataQuery

client = weaviate.connect_to_local(timeout={"init": 5, "query": 10})
try:
    collection = client.collections.get("DocumentNode")
    count = collection.aggregate.over_all().total_count
    print("Total nodes:", count)

    objs = collection.query.fetch_objects(limit=5)
    for o in objs.objects:
        p = dict(o.properties)
        print("  type=%s page=%s content=%s" % (p.get("type","?"), p.get("page","?"), p.get("content","")[:80]))

    # Try BM25
    for q in ["summarize", "document", "the"]:
        print()
        print("BM25 query: %s" % q)
        res = collection.query.bm25(q, limit=5, return_metadata=MetadataQuery(score=True))
        print("  results:", len(res.objects))
        for o in res.objects:
            p = dict(o.properties)
            score = o.metadata.score if o.metadata else "?"
            print("  score=%s type=%s content=%s" % (score, p.get("type","?"), p.get("content","")[:100]))
finally:
    client.close()
