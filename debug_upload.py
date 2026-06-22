"""Upload PDF and check table data."""
import json, urllib.request, os

API = "http://localhost:8000"

# Upload
filepath = "C:\\Users\\tharu\\OneDrive\\Desktop\\Dell\\data\\uploads\\embedded-images-tables.pdf"
filename = "embedded-images-tables.pdf"

class MultipartFormData:
    def __init__(self):
        self.boundary = "----" + hex(hash(os.urandom(16)))[2:18]
        self.body = b""
    def add_file(self, name, filename, data, mimetype):
        self.body += f"--{self.boundary}\r\n".encode()
        self.body += f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode()
        self.body += f"Content-Type: {mimetype}\r\n\r\n".encode()
        self.body += data + b"\r\n"
    def finish(self):
        self.body += f"--{self.boundary}--\r\n".encode()
    def header(self):
        return {"Content-Type": f"multipart/form-data; boundary={self.boundary}"}

with open(filepath, "rb") as f:
    pdf_data = f.read()

mfd = MultipartFormData()
mfd.add_file("file", filename, pdf_data, "application/pdf")
mfd.finish()

req = urllib.request.Request(f"{API}/upload", data=mfd.body, headers=mfd.header())
r = urllib.request.urlopen(req, timeout=120)
result = json.loads(r.read().decode())
print("Upload:", result.get("status"))

# Check insights table data
r = urllib.request.urlopen(f"{API}/document/embedded-images-tables/insights", timeout=15)
insight = json.loads(r.read().decode())
tables = insight.get("tables", [])
print(f"\n=== TABLES ({len(tables)}) ===")
for t in tables:
    h = t.get("headers", [])
    print(f"\nheaders ({len(h)}):")
    for i, x in enumerate(h):
        print(f"  [{i}]: {x!r}")
    rr = t.get("rows", [])
    print(f"rows ({len(rr)}):")
    for i, row in enumerate(rr):
        print(f"  row {i} ({len(row)}): {[x[:20] if isinstance(x, str) else type(x).__name__ for x in row]}")

# Check table endpoint
r = urllib.request.urlopen(f"{API}/document/embedded-images-tables/table/1", timeout=15)
tbl = json.loads(r.read().decode())
h = tbl.get("headers", [])
print(f"\n=== TABLE ENDPOINT ===")
print(f"headers ({len(h)}): {[x[:30] if isinstance(x, str) else type(x).__name__ for x in h]}")
print(f"rows ({len(tbl.get('rows',[]))}):")
for i, row in enumerate(tbl.get("rows", [])):
    print(f"  row {i}: {[x[:15] if isinstance(x, str) else type(x).__name__ for x in row]}")
