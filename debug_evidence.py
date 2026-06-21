"""Debug evidence enrichment."""
import json, urllib.request

API = 'http://localhost:8000'

# Get insights
r = urllib.request.urlopen(API + '/document/embedded-images-tables/insights')
ins = json.loads(r.read())
print('=== INSIGHT IMAGES ===')
for img in ins.get('images', []):
    print(f'  image_id={str(img.get("image_id"))[:30] if img.get("image_id") else None}')
    print(f'  figure_num={img.get("figure_number")}')
    print(f'  has_data={bool(img.get("image_data"))}')
    print(f'  page={img.get("page")}')
    print(f'  caption={str(img.get("caption"))[:50] if img.get("caption") else None}')
    print()

print('=== INSIGHT TABLES ===')
for t in ins.get('tables', []):
    print(f'  table_num={t.get("table_number")}')
    print(f'  has_headers={bool(t.get("headers"))}')
    print(f'  has_rows={bool(t.get("rows"))}')
    print(f'  page={t.get("page")}')
    print(f'  caption={str(t.get("caption"))[:50] if t.get("caption") else None}')
    print()

print('=== QUERY EVIDENCE ===')
body = json.dumps({'query': 'summarize the document', 'doc_id': 'embedded-images-tables', 'cross_doc': False}).encode()
req = urllib.request.Request(API + '/query', data=body, headers={'Content-Type': 'application/json'}, method='POST')
r = urllib.request.urlopen(req)
q = json.loads(r.read())
print(f'confidence_score={q.get("confidence_score")}')
print(f'risk_level={q.get("risk_level")}')
ev = q.get('evidence', {})
supporting = ev.get('supporting', [])
print(f'Number of supporting nodes: {len(supporting)}')
if supporting:
    s = supporting[0]
    print(f'First node:')
    print(f'  type={s.get("type")}')
    print(f'  doc_id={s.get("doc_id")}')
    print(f'  page={s.get("page")}')
    print(f'  pdf_url={bool(s.get("pdf_url"))}')
    print(f'  document_name={s.get("document_name")}')
    print(f'  has_image_data={bool(s.get("image_data"))}')
    print(f'  has_headers={bool(s.get("headers"))}')
    print(f'  figure_number={s.get("figure_number")}')
    print(f'  table_number={s.get("table_number")}')
    print(f'  content={str(s.get("content"))[:80]}')
doc_ids = set()
for n in supporting:
    did = n.get('doc_id')
    if did:
        doc_ids.add(did)
    pdf = n.get('pdf_url')
print(f'  Unique doc_ids: {doc_ids}')
print(f'  Supporting with pdf_url: {sum(1 for n in supporting if n.get("pdf_url"))}')
print(f'  Supporting with image_data: {sum(1 for n in supporting if n.get("image_data"))}')
print(f'  Supporting with headers: {sum(1 for n in supporting if n.get("headers"))}')
