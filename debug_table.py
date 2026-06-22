"""Debug table/insight state comprehensively."""
import json, urllib.request

API = "http://localhost:8000"
doc_id = "embedded-images-tables"

# Check insights
r = urllib.request.urlopen(f"{API}/document/{doc_id}/insights", timeout=15)
insight = json.loads(r.read().decode())

tables = insight.get("tables", [])
print(f"=== INSIGHTS TABLES ({len(tables)}) ===")
for i, t in enumerate(tables):
    print(f"\nTable {i}:")
    print(f"  table_number: {t.get('table_number')}")
    print(f"  caption: {t.get('caption', '')[:60]}")
    h = t.get("headers", [])
    print(f"  headers ({len(h)}): {h}")
    r = t.get("rows", [])
    print(f"  rows ({len(r)}): {[len(row) for row in r]} cols each")

# Check table endpoint
r = urllib.request.urlopen(f"{API}/document/{doc_id}/table/1", timeout=15)
tbl = json.loads(r.read().decode())
print(f"\n=== TABLE ENDPOINT ===")
h = tbl.get("headers", [])
print(f"headers ({len(h)}): {h}")
r = tbl.get("rows", [])
print(f"rows ({len(r)}): {[len(row) for row in r]} cols each")

# Check graph nodes for table info
r = urllib.request.urlopen(f"{API}/graph/stats", timeout=15)
stats = json.loads(r.read().decode())
print(f"\n=== GRAPH STATS ===")
print(json.dumps(stats, indent=2)[:300])

# Check all nodes in graph
r = urllib.request.urlopen(f"{API}/graph/data", timeout=15)
graph_data = json.loads(r.read().decode())
nodes = graph_data.get("nodes", [])
print(f"\n=== GRAPH NODES ({len(nodes)}) ===")
for n in nodes:
    if n.get("type") in ("table", "image", "figure", "caption"):
        print(f"  {n.get('id')}: type={n.get('type')}, page={n.get('page')}")
        meta_keys = list(n.get('metadata', {}).keys()) if n.get('metadata') else []
        if meta_keys:
            print(f"    metadata keys: {meta_keys}")
