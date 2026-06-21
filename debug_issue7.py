"""Debug Issue 7 query - explain the figure about polarization."""
import json, urllib.request, sys

API = "http://localhost:8000"
doc_id = "embedded-images-tables"

# Test query
data = json.dumps({"query": "explain the figure about polarization", "doc_id": doc_id, "cross_doc": False}).encode()
req = urllib.request.Request(f"{API}/query", data=data, headers={"Content-Type": "application/json"}, method="POST")
r = urllib.request.urlopen(req, timeout=30)
resp = json.loads(r.read().decode())

print("=== RESPONSE ===")
print(f"routed: {resp.get('routed')}")
print(f"has answer: {bool(resp.get('answer'))}")
print(f"confidence: {resp.get('confidence_score')}")

ev = resp.get("evidence", {})
supporting = ev.get("supporting", [])
print(f"\n=== SUPPORTING NODES ({len(supporting)}) ===")
for i, n in enumerate(supporting):
    print(f"\n  Node {i}:")
    print(f"    type: {n.get('type')}")
    print(f"    node_id: {n.get('node_id')}")
    print(f"    doc_id: {n.get('doc_id')}")
    print(f"    page: {n.get('page')}")
    print(f"    has image_data: {bool(n.get('image_data'))}")
    print(f"    figure_number: {n.get('figure_number')}")
    print(f"    content: {(n.get('content') or '')[:80]}")
    print(f"    score: {n.get('score')}")

# Also check the figure_number values in retrieved nodes
img_nodes = [n for n in supporting if str(n.get("type", "")).lower() in ("image", "figure", "chart")]
print(f"\n=== IMAGE/FIGURE NODES: {len(img_nodes)} ===")
for n in img_nodes:
    print(f"  type={n.get('type')}, fn={n.get('figure_number')}, caption={n.get('caption','')[:50]}")
