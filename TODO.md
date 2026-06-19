## DocuMind Graph v2.0 Ingestion Implementation TODO

### Step 1: Fix broken repo files (required)
- [ ] Resolve merge conflict markers in `requirements.txt`
- [ ] Resolve merge conflict markers in `main.py` and ensure FastAPI skeleton endpoints work
- [x] Fix truncated `Config.validate()` in `config.py` (was causing runtime failure)

### Step 2: Implement ingestion pipeline (Tasks 1–6)
- [x] `ingestion/parser.py`: Docling PDF/DOCX parsing + extract headings/paragraphs/tables/images/captions/footnotes with page info + save images locally
- [x] `ingestion/vision_processor.py`: Groq Vision semantic summaries for images/diagrams/charts/figures/workflow diagrams
- [x] `ingestion/node_builder.py`: Normalize extracted elements into nodes with required fields + Groq summaries on image nodes
- [x] Add chunking using LangChain `RecursiveCharacterTextSplitter` (chunk_size=1200, chunk_overlap=150) while preserving structure & keeping captions close to images and avoiding table breaks
- [x] Generate embeddings using `HuggingFaceEmbeddings` with `sentence-transformers/all-MiniLM-L6-v2`
- [x] `vectorstore/weaviate_client.py`: Implement Weaviate storage compatible with future graph construction/retrieval needs

### Step 3: Integrate orchestration + stats
- [ ] Add an ingestion runner callable from the API
- [ ] Update `main.py` `/upload` to trigger ingestion (or return ingestion-ready message + background processing)

### Step 4: Validate end-to-end
- [ ] Ingest a single test document placed in `data/uploads`
- [ ] Verify local image extraction + vision summaries
- [ ] Verify nodes/chunks embedded and stored in Weaviate
- [ ] Output processing statistics (doc name, pages processed, node count, image count, chunks created)
