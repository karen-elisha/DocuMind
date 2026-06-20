"""
Isolated test: parser only.
Usage:  python test_parser.py <pdf_path>
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

pdf_path = sys.argv[1] if len(sys.argv) > 1 else None
if not pdf_path or not os.path.exists(pdf_path):
    print("Usage: python test_parser.py <path_to_pdf>")
    sys.exit(1)

doc_id = os.path.splitext(os.path.basename(pdf_path))[0]

print(f"Testing parser on: {pdf_path}")
print()

from ingestion.parser import parse_document

t0 = time.perf_counter()
parse_result = parse_document(file_path=pdf_path, doc_id=doc_id)
elapsed = time.perf_counter() - t0

print()
print("=" * 50)
print("  PARSER RESULTS")
print("=" * 50)
print(f"  Pages:              {parse_result['pages_processed']}")
print(f"  Text elements:      {parse_result['text_count']}")
print(f"  Tables:             {parse_result['table_count']}")
print(f"  Images:             {parse_result['image_count']}")
print(f"  Total elements:     {len(parse_result['elements'])}")
print(f"  Time:               {elapsed:.2f}s")
print("=" * 50)
