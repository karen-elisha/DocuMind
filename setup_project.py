from pathlib import Path

folders = [
    "ingestion",
    "ingestion/parser",
    "ingestion/vision",
    "ingestion/chunking",
    "ingestion/schemas",
    "storage",
    "config",
    "uploads",
    "processed",
    "processed/images",
    "processed/tables",
    "processed/json",
    "tests"
]

files = [
    "ingestion/__init__.py",

    "ingestion/parser/__init__.py",
    "ingestion/parser/docling_parser.py",
    "ingestion/parser/pdf_parser.py",
    "ingestion/parser/document_processor.py",

    "ingestion/vision/__init__.py",
    "ingestion/vision/groq_vision.py",
    "ingestion/vision/image_summarizer.py",

    "ingestion/chunking/__init__.py",
    "ingestion/chunking/chunker.py",
    "ingestion/chunking/metadata_builder.py",

    "ingestion/schemas/__init__.py",
    "ingestion/schemas/document_node.py",

    "storage/__init__.py",
    "storage/weaviate_client.py",
    "storage/embeddings.py",
    "storage/vector_store.py",

    "config/__init__.py",
    "config/settings.py",

    "tests/__init__.py",
]

root = Path(".")

for folder in folders:
    Path(root / folder).mkdir(parents=True, exist_ok=True)

for file in files:
    path = root / file

    if not path.exists():
        path.touch()

print("Project structure created successfully.")