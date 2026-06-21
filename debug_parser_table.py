"""Debug Docling Table.data structure directly."""
import json, sys
sys.path.insert(0, "C:\\Users\\tharu\\OneDrive\\Desktop\\Dell")
from config import Config
from ingestion.parser import parse_document

doc_id = "embedded-images-tables"
file_path = "C:\\Users\\tharu\\OneDrive\\Desktop\\Dell\\data\\uploads\\embedded-images-tables.pdf"

result = parse_document(file_path=file_path, doc_id=doc_id)

elements = result.get("elements", [])
for el in elements:
    if el.get("type") == "table":
        md = el.get("metadata", {})
        print(f"table_index: {md.get('table_index')}")
        print(f"table_number: {md.get('table_number')}")
        print(f"table_caption: {md.get('table_caption')}")
        print(f"table_headers type: {type(md.get('table_headers', [])).__name__}")
        print(f"table_headers len: {len(md.get('table_headers', []))}")
        print(f"table_headers: {md.get('table_headers', [])}")
        print(f"table_rows type: {type(md.get('table_rows', [])).__name__}")
        print(f"table_rows len: {len(md.get('table_rows', []))}")
        for i, row in enumerate(md.get('table_rows', [])):
            print(f"  row {i}: {row}")
        print(f"content (markdown):")
        print(el.get("content", "")[:500])
        break
