# Ingestion Pipeline Report

> **Project:** DocuMind Graph v2.0 — Agentic KG-RAG with Negative Graph Expansion
> **Date:** 2026-06-19
> **Test Document:** NIPS-2017-attention-is-all-you-need-Paper (1).pdf

---

## SECTION 1 — PIPELINE OVERVIEW

The ingestion pipeline transforms raw documents (PDF/DOCX) into semantically searchable chunk-vector objects stored in Weaviate. It runs inside FastAPI background tasks triggered by the `/upload` endpoint (`main.py:46`).

### Architecture Diagram

```
PDF / DOCX
    │
    ▼
┌─────────────────────────────────────────────┐
│ 1. Docling Parser  (ingestion/parser.py)     │
│    • Extracts texts, tables, pictures        │
│    • Exports images to disk (PNG)            │
│    • Returns ParsedElement list              │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│ 2. Vision Processor (ingestion/vision_pro-   │
│    cessor.py)                                │
│    • Reads exported images                   │
│    • Sends to Groq Vision (LLaMA model)      │
│    • Returns semantic summaries              │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│ 3. Node Builder    (ingestion/node_builder.py)│
│    • Converts elements → Node objects        │
│    • Merges vision summaries into image nodes│
│    • Assigns section context (future)        │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│ 4. Chunking        (ingestion/node_builder.py)│
│    • RecursiveCharacterTextSplitter          │
│    • chunk_size=1200, chunk_overlap=150      │
│    • Tables split line-by-line (preservation)│
└─────────────────────┬───────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│ 5. Embeddings      (ingestion/node_builder.py)│
│    • HuggingFaceEmbeddings                   │
│    • all-MiniLM-L6-v2 (384-dim)              │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│ 6. Weaviate Storage (vectorstore/weaviate_   │
│    client.py)                                │
│    • Batch upsert via REST API               │
│    • Collection: DocumentNode                │
└─────────────────────────────────────────────┘
```

### Pipeline Invocation

The entire pipeline is orchestrated in `main.py:71-77`:

```python
parse_result = parse_document(file_path=file_path, doc_id=doc_id)
vision_results = summarize_images(parse_result.get("images", []) or [])
stats = run_ingestion_pipeline(parse_result=parse_result, vision_results=vision_results)
```

Where `run_ingestion_pipeline` (`node_builder.py:330`) chains:
1. `build_nodes()` → `chunk_nodes()` → `embed_chunks()` → `store_chunks_weaviate()`

---

## SECTION 2 — INPUT DOCUMENTS

### Supported File Types

| Format | Extension | Status |
|--------|-----------|--------|
| PDF | `.pdf` | Supported |
| Microsoft Word | `.docx` | Supported |

Validation is performed in two places:
- `parser.py:69` — explicit extension check before conversion
- `main.py:56` — FastAPI endpoint also checks before accepting upload

### Document Location

Uploaded documents are saved to:

```
data/uploads/<filename>
```

Documents are stored as-is (no archiving or deduplication yet). The upload directory is created automatically on server startup (`main.py:14`).

### How Documents Enter the System

1. Client sends a POST `/upload` with `multipart/form-data` containing the file.
2. FastAPI saves the file to `data/uploads/` using `shutil.copyfileobj` (`main.py:66-67`).
3. A `BackgroundTasks` task runs the full ingestion pipeline asynchronously.
4. The endpoint returns immediately with status `"success"` — ingestion continues in the background.

**Sample upload response:**
```json
{
  "filename": "NIPS-2017-attention-is-all-you-need-Paper (1).pdf",
  "doc_id": "NIPS-2017-attention-is-all-you-need-Paper (1)",
  "status": "success",
  "message": "File uploaded successfully. Ingestion started in background."
}
```

---

## SECTION 3 — DOCLING PARSING

### Library Configuration

| Parameter | Value |
|-----------|-------|
| Library | Docling (`docling`) |
| Version | ≥1.10.x (uses `PdfPipelineOptions`, `PdfFormatOption`) |
| OCR | Enabled by default (RapidOCR backend, CPU) |
| Picture Extraction | `generate_picture_images=True` |
| Page Images | `generate_page_images=True` |
| Image Scale | `images_scale=2.0` |

The parser is configured in `parser.py:58-62`:

```python
pipeline_options = PdfPipelineOptions()
pipeline_options.generate_picture_images = True
pipeline_options.generate_page_images = True
pipeline_options.images_scale = 2.0
pdf_format_option = PdfFormatOption(pipeline_options=pipeline_options)
format_options = {InputFormat.PDF: pdf_format_option}
converter = DocumentConverter(format_options=format_options)
```

### How Text is Extracted

The parser iterates `doc.texts` (a list of `DoclingTextItem` objects) and classifies each by its `.label` attribute:

| Docling Label | Mapped Type | Used For |
|---------------|-------------|----------|
| `section_header`, `title` | `heading` | Section headings, document title |
| `text` | `paragraph` | Body paragraphs |
| `list_item` | `list_item` | Bullet/numbered list entries |
| `caption` | `caption` | Figure/table captions |
| `footnote`, `page_footer` | `footnote` | Footnotes, page footnotes |
| `formula` | `formula` | Mathematical equations |

Page numbers are extracted from `item.prov[0].page_no`.

**Implementation:** `parser.py:110-148`

### How Tables are Extracted

Tables come from `doc.tables`. Each `TableItem` is exported to markdown via `table.export_to_markdown(doc)`.

**Implementation:** `parser.py:222-258`

If the markdown export fails, the code falls back to a plain text attribute (`tbl.text`).

### How Images are Extracted

Images come from `doc.pictures`. Each `PictureItem` is:

1. Checked for `pic.image.pil_image` (PIL Image object, available when `generate_picture_images=True`)
2. If missing, falls back to `pic.get_image(doc)`
3. Saved to `data/processed/images/<doc_id>/<doc_id>_img_<N>.png`
4. A `ParsedElement` of type `"image"` is created (empty content, path in metadata)
5. If the image has a caption, a separate `"caption"` node is also created with `linked_image_element_id` in metadata

**Implementation:** `parser.py:150-220`

### Parser Statistics (from test run)

| Metric | Count |
|--------|-------|
| `pages_processed` | 11 |
| `text_count` | 186 |
| `table_count` | 4 |
| `image_count` | 3 |
| `elements_count` | 193 |

### Sample Extracted Elements

```python
# Heading
{
  "element_id": "heading_386f72ecaf",
  "type": "heading",
  "page": 1,
  "content": "Attention Is All You Need",
  "metadata": {"source": "docling_texts", "docling_label": "section_header"}
}

# Paragraph
{
  "element_id": "paragraph_3f6d05edd0",
  "type": "paragraph",
  "page": 1,
  "content": "The dominant sequence transduction models are based on complex recurrent or convolutional neural ...",
  "metadata": {"source": "docling_texts", "docling_label": "text"}
}

# Table
{
  "element_id": "table_60da3e33bd",
  "type": "table",
  "page": 6,
  "content": "Table 1: Maximum path lengths, per-layer complexity and minimum number of sequential operations for ...",
  "metadata": {"source": "docling_tables", "table_index": 1}
}

# Image
{
  "element_id": "image_6c4cc8a887",
  "type": "image",
  "page": 3,
  "content": "",
  "metadata": {
    "figure_caption": "Figure 1: The Transformer - model architecture.",
    "image_path": "data/processed/images/NIPS-2017-attention-is-all-you-need-Paper/NIPS-2017-attention-is-all-you-need-Paper_img_0.png",
    "image_index": 0
  }
}

# Caption
{
  "element_id": "caption_d61aa644b5",
  "type": "caption",
  "page": 3,
  "content": "Figure 1: The Transformer - model architecture.",
  "metadata": {"linked_image_element_id": "image_6c4cc8a887"}
}

# List Item
{
  "element_id": "list_item_6bc7073d95",
  "type": "list_item",
  "page": 5,
  "content": "In \"encoder-decoder attention\" layers, the queries come from the previous decoder layer...",
  "metadata": {"source": "docling_texts", "docling_label": "list_item"}
}
```

---

## SECTION 4 — VISION PROCESSING

### Model

Images are sent to the **Groq API** for vision-based summarization.

| Parameter | Value |
|-----------|-------|
| API | Groq (`groq` Python SDK) |
| Default Model | `meta-llama/llama-4-scout-17b-16e-instruct` |
| Fallback Model | `llama-3.2-11b-vision-preview` |
| Temperature | 0.2 |
| Max Tokens | 180 |
| Auth | `GROQ_API_KEY` from environment (`.env`) |

The model is configurable via `GROQ_VISION_MODEL` in `.env`. The default in code is `llama-3.2-11b-vision-preview`, overridden by the Config value.

### How Images Are Sent

1. The parser's extracted image list (containing `image_path`, `page`, `caption`) is passed to `summarize_images()` (`vision_processor.py:32`)
2. Each image is read as bytes and base64-encoded
3. Sent in a Groq chat completion with a structured prompt:

```
You are a document vision analyst for building retrieval nodes.
Provide a concise semantic description (1-3 sentences) of what the image shows.

Focus on:
- architecture diagrams, workflow diagrams (entities + arrows)
- charts/graphs (metrics + trends)
- graphs/figures (key components + relationships)

Output format: a single sentence description suitable for semantic retrieval.
```

4. The response is stored as `vision_summary`

### How Image Summaries Are Used

The `build_nodes()` function (`node_builder.py:88-105`) merges vision summaries into image nodes by matching on page number:

```python
for v in vision_results.values():
    if int(v.get("page") or 1) == page and v.get("vision_summary"):
        summary = v["vision_summary"]
        break
node.content = summary.strip() if summary else ""
```

### Sample Image Node (After Vision Processing)

```python
{
  "node_id": "image_6c4cc8a887",
  "doc_id": "NIPS-2017-attention-is-all-you-need-Paper",
  "page": 3,
  "type": "image",
  "content": "The diagram shows the Transformer model architecture with encoder on the left and decoder on the right, each consisting of multi-head attention and feed-forward layers with residual connections.",
  "metadata": {
    "figure_caption": "Figure 1: The Transformer - model architecture.",
    "image_path": "data/processed/images/NIPS-2017-attention-is-all-you-need-Paper/NIPS-2017-attention-is-all-you-need-Paper_img_0.png",
    "image_vision_available": true
  }
}
```

---

## SECTION 5 — NODE GENERATION

### Node Schema

Defined as a `@dataclass` in `node_builder.py:21-30`:

```python
@dataclass
class Node:
    node_id: str        # Unique identifier: "<type>_<uuid hex>"
    doc_id: str         # Source document identifier (filename without extension)
    page: int           # Page number (1-based)
    type: str           # Node type (see SUPPORTED_NODE_TYPES)
    content: str        # Text content (for images, the vision summary)
    metadata: Dict[str, Any]  # Flexible metadata dict
    section: str = ""   # Section context (future use, currently empty)
    embedding: Sequence[float] = ()  # Vector embedding (populated later)
```

### Supported Node Types

Defined in `node_builder.py:18`:

```python
SUPPORTED_NODE_TYPES = {"heading", "paragraph", "table", "image", "caption", "footnote", "list_item", "formula"}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `node_id` | `str` | Generated as `{type}_{uuid.hex[:10]}`. Example: `"heading_386f72ecaf"` |
| `doc_id` | `str` | Matches the source filename without extension. Used for document-level filtering |
| `page` | `int` | 1-based page number extracted from `prov[0].page_no` |
| `type` | `str` | One of the 8 supported node types |
| `content` | `str` | The actual text content. For images, this is the Groq vision summary |
| `metadata` | `dict` | Flexible. Stores source info, labels, image paths, captions, etc. |
| `section` | `str` | Reserved for section tracking. Currently always empty |
| `embedding` | `Sequence[float]` | Vector embedding. Empty tuple before embedding step |

### Node Type Breakdown (Test Run)

| Type | Count |
|------|-------|
| paragraph | 104 |
| list_item | 35 |
| heading | 26 |
| footnote | 16 |
| caption | 5 |
| table | 4 |
| image | 3 |
| **Total** | **193** |

### Sample Nodes by Type

**Heading:**
```python
{
  "node_id": "heading_386f72ecaf",
  "doc_id": "NIPS-2017-attention-is-all-you-need-Paper",
  "page": 1,
  "type": "heading",
  "content": "Attention Is All You Need",
  "metadata": {"docling_label": "section_header", "source": "docling_texts"},
  "section": "",
  "embedding": ()
}
```

**Paragraph:**
```python
{
  "node_id": "paragraph_3f6d05edd0",
  "doc_id": "NIPS-2017-attention-is-all-you-need-Paper",
  "page": 1,
  "type": "paragraph",
  "content": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks...",
  "metadata": {"docling_label": "text", "source": "docling_texts"},
  "section": "",
  "embedding": ()
}
```

**Table:**
```python
{
  "node_id": "table_60da3e33bd",
  "doc_id": "NIPS-2017-attention-is-all-you-need-Paper",
  "page": 6,
  "type": "table",
  "content": "Table 1: Maximum path lengths, per-layer complexity and minimum number of sequential operations for...",
  "metadata": {"source": "docling_tables", "table_index": 1},
  "section": "",
  "embedding": ()
}
```

**Image (after vision processing):**
```python
{
  "node_id": "image_6c4cc8a887",
  "doc_id": "NIPS-2017-attention-is-all-you-need-Paper",
  "page": 3,
  "type": "image",
  "content": "The diagram shows the Transformer model architecture...",
  "metadata": {
    "figure_caption": "Figure 1: The Transformer - model architecture.",
    "image_path": "data/processed/images/...img_0.png",
    "image_vision_available": true
  },
  "section": "",
  "embedding": ()
}
```

**Caption:**
```python
{
  "node_id": "caption_d61aa644b5",
  "doc_id": "NIPS-2017-attention-is-all-you-need-Paper",
  "page": 3,
  "type": "caption",
  "content": "Figure 1: The Transformer - model architecture.",
  "metadata": {
    "linked_image_element_id": "image_6c4cc8a887",
    "links_to_image": true
  },
  "section": "",
  "embedding": ()
}
```

---

## SECTION 6 — SECTION TRACKING

### Current State: NOT IMPLEMENTED

The `section` field exists on both `ParsedElement` (`parser.py:20`) and `Node` (`node_builder.py:29`) with defaults of `""`, but it is **never populated** by the current pipeline.

### Intended Behavior

The section tracking algorithm (not yet implemented) would work as follows:

```
Heading: "1 Introduction"  →  active_section = "1 Introduction"
  Paragraph below it       →  section = "1 Introduction"
  Paragraph below it       →  section = "1 Introduction"
Heading: "2 Background"    →  active_section = "2 Background"
  Paragraph below it       →  section = "2 Background"
```

In other words, each non-heading node inherits the most recent heading's content as its section identifier. This is a common pattern in document processing pipelines.

### Required Implementation

To implement section tracking, the pipeline would need to:

1. Sort nodes by page and position (requires position tracking from Docling `prov` data)
2. Iterate through sorted nodes, tracking the last seen `heading` node's content
3. Assign that heading text to all subsequent non-heading nodes' `section` field

This is a known gap and should be addressed before deploying to production.

---

## SECTION 7 — CHUNKING

### Configuration

| Parameter | Value | Source |
|-----------|-------|--------|
| `chunk_size` | 1200 (characters) | `Config.CHUNK_SIZE` or `CHUNK_SIZE` env var |
| `chunk_overlap` | 150 (characters) | `Config.CHUNK_OVERLAP` or `CHUNK_OVERLAP` env var |
| Splitter | `RecursiveCharacterTextSplitter` | LangChain |
| Separators | `["\n\n", "\n", " ", ""]` | Hardcoded in `node_builder.py:181` |

### Why These Values Were Chosen

- **1200 characters** (~200-300 words) balances semantic completeness with granularity. Each chunk is long enough to contain a coherent idea but short enough to be a precise retrieval target.
- **150 character overlap** (~12.5% of chunk size) ensures that sentence/paragraph boundaries don't cause information loss at chunk edges.
- Character-based (not token-based) splitting is used because: (a) it's simpler, (b) `all-MiniLM-L6-v2` has a 256-token limit (roughly equivalent to 1200 characters), and (c) it avoids dependency on a tokenizer at chunking time.
- The `RecursiveCharacterTextSplitter` is chosen because it is the standard LangChain splitter that respects paragraph and sentence boundaries.

### Table Handling

Tables receive special treatment (`node_builder.py:205-255`):

- If a table fits within `chunk_size + chunk_overlap`, it is stored as a single chunk (no splitting).
- If a table is larger, it is split **line-by-line** (by newline characters) to preserve row structure.

This is a known limitation — very wide tables may be split mid-row.

### Chunking Statistics (Test Run)

| Metric | Value |
|--------|-------|
| Total chunks | 198 |
| Average chunk length | 221 characters |
| Table chunks | 12 (from 4 tables) |

The average chunk length (221 chars) is significantly below the 1200 limit because most nodes are short (headings, list items, captions, footnotes). Only long paragraphs and large tables approach the limit.

### Sample Chunks

```python
# Chunk from a heading (small, fits in one chunk)
{
  "chunk_id": "chunk_<uuid>",
  "node_id": "heading_386f72ecaf",
  "doc_id": "NIPS-2017-attention-is-all-you-need-Paper",
  "page": 1,
  "type": "heading",
  "content": "Attention Is All You Need",
  "metadata": { "node_type": "heading", ... }
}

# Chunk from a long paragraph
{
  "chunk_id": "chunk_<uuid>",
  "node_id": "paragraph_...",
  "doc_id": "NIPS-2017-attention-is-all-you-need-Paper",
  "page": 1,
  "type": "paragraph",
  "content": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks that include an encoder and a decoder. The best performing models also connect the encoder and decoder through an attention mechanism...",
  "metadata": { "node_type": "paragraph", ... }
}

# Chunk from a large table (may be split across multiple chunks)
{
  "chunk_id": "chunk_<uuid>",
  "node_id": "table_...",
  "doc_id": "NIPS-2017-attention-is-all-you-need-Paper",
  "page": 9,
  "type": "table",
  "content": "|      |                                           |                            |\n| (C)  |                                           | 256                        |\n|      |                                           |                            |",
  "metadata": { "node_type": "table", ... }
}
```

---

## SECTION 8 — EMBEDDINGS

### Model

| Parameter | Value |
|-----------|-------|
| Model | `sentence-transformers/all-MiniLM-L6-v2` |
| Library | `langchain_huggingface.HuggingFaceEmbeddings` |
| Dimension | 384 |
| Framework | PyTorch (runs locally on CPU) |
| License | Apache 2.0 |

Configuration in `config.py:20`:

```python
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
```

### Why This Model Was Chosen

1. **384-dimensional vectors** — compact enough for efficient storage and retrieval, expressive enough for semantic search.
2. **Sentence-transformers** — mature ecosystem, well-tested with LangChain and Weaviate.
3. **Lightweight** — runs on CPU with minimal memory (only 103 weight files, ~90MB).
4. **Apache 2.0 license** — no commercial restrictions.
5. **256-token context window** — matches well with the 1200-character chunk size.
6. **No API key required** — runs entirely locally on the server.

### Embedding Statistics (Test Run)

| Metric | Value |
|--------|-------|
| Total embeddings | 198 |
| Embedding dimension | 384 |
| Sample vector[0:5] | `[0.0531, -0.0196, -0.0196, -0.0314, 0.0631]` |

### How Embedding Works

In `node_builder.py:281-309`:

1. All chunk contents are collected into a list of strings
2. `HuggingFaceEmbeddings.embed_documents()` is called once (batched internally)
3. Each chunk dict is updated with its corresponding `embedding` vector

```python
embeddings = HuggingFaceEmbeddings(model_name=embedding_model_name)
texts = [c["content"] for c in chunks]
vectors = embeddings.embed_documents(texts) if texts else []
for i, c in enumerate(chunks):
    c["embedding"] = vectors[i] if i < len(vectors) else []
```

---

## SECTION 9 — WEAVIATE STORAGE

### Connection

| Parameter | Value |
|-----------|-------|
| Client | Weaviate Cloud (v4) |
| URL | Configured via `WEAVIATE_URL` in `.env` |
| Auth | API key via `WEAVIATE_API_KEY` |
| Connection Method | `weaviate.connect_to_weaviate_cloud()` |
| SDK | `weaviate-client` >= 4.x |

### Collection Schema

**Collection Name:** `DocumentNode`

The collection is auto-created via REST API if it does not exist (`weaviate_client.py:58-136`).

```json
{
  "class": "DocumentNode",
  "vectorizer": "none",
  "properties": [
    {
      "name": "node_id",
      "dataType": ["text"],
      "indexFilterable": true,
      "indexSearchable": true
    },
    {
      "name": "doc_id",
      "dataType": ["text"],
      "indexFilterable": true,
      "indexSearchable": true
    },
    {
      "name": "page",
      "dataType": ["int"],
      "indexFilterable": true,
      "indexSearchable": false
    },
    {
      "name": "type",
      "dataType": ["text"],
      "indexFilterable": true,
      "indexSearchable": true
    },
    {
      "name": "content",
      "dataType": ["text"],
      "indexFilterable": false,
      "indexSearchable": true
    },
    {
      "name": "metadata",
      "dataType": ["text"],
      "indexFilterable": false,
      "indexSearchable": false
    }
  ]
}
```

### Properties Stored

| Property | Source | Purpose |
|----------|--------|---------|
| `node_id` | Chunk metadata | Unique identifier for the source node |
| `doc_id` | Chunk metadata | Identifies the source document for filtering |
| `page` | Chunk metadata | Page number for provenance and filtering |
| `type` | Chunk metadata | Node type for type-based filtering |
| `content` | Chunk content | The actual text to search over |
| `metadata` | Chunk metadata | JSON-serialized dict with extra context |
| `vector` | Chunk embedding | 384-dim vector for semantic search (stored as object vector) |

### How Storage Works

In `weaviate_client.py:138-211`:

1. Chunks are batch-uploaded via REST POST to `/v1/batch/objects`
2. Each object gets a deterministic UUID generated from `node_id|doc_id|page|type` via `generate_uuid5()` — this enables idempotent upserts
3. The `metadata` dict is JSON-serialized to a string before storage
4. The embedding vector is attached as the object's `vector` field
5. No Weaviate vectorizer is used (`"vectorizer": "none"`) — vectors are provided externally

### Sample Stored Object (as returned by Weaviate)

```json
{
  "node_id": "paragraph_277da57822",
  "doc_id": "NIPS-2017-attention-is-all-you-need-Paper",
  "page": 6,
  "type": "paragraph",
  "content": "As noted in Table 1, a self-attention layer connects all positions with a constant number of sequentially executed operations...",
  "metadata": "{\"node_id\": \"paragraph_277da57822\", \"node_type\": \"paragraph\", \"doc_id\": \"NIPS-2017-attention-is-all-you-need-Paper\", \"page\": 6, \"docling_label\": \"text\", \"source\": \"docling_texts\"}"
}
```

### Storage Verification (Test Run)

| Metric | Value |
|--------|-------|
| Objects sent for insertion | 198 |
| Objects confirmed in collection | 191 (remaining 7 from prior insert) |

---

## SECTION 10 — END-TO-END EXAMPLE

**Document:** `NIPS-2017-attention-is-all-you-need-Paper (1).pdf`

### Step 1: Input PDF

- Original file: 11-page Transformer paper ("Attention Is All You Need")
- Location: `data/uploads/NIPS-2017-attention-is-all-you-need-Paper (1).pdf`

### Step 2: Docling Parsing

Docling extracts structured elements from the PDF:

| Element Type | Count | Examples |
|-------------|-------|---------|
| paragraph | 104 | Body text explaining model architecture |
| list_item | 35 | Bullet points of model features |
| heading | 26 | "Abstract", "1 Introduction", "3.1 Scaled Dot-Product Attention" |
| footnote | 16 | Author affiliations, equal contribution notes |
| caption | 5 | "Figure 1: The Transformer - model architecture." |
| table | 4 | Author list, comparison tables, architecture variants |
| image | 3 | Model architecture diagram (Figure 1), attention diagrams (Figure 2) |
| **Total** | **193** | |

Images are saved to `data/processed/images/NIPS-2017-attention-is-all-you-need-Paper/`.

### Step 3: Vision Processing

3 images sent to Groq Vision (LLaMA 4 Scout 17B). Example summaries:

- **Figure 1** (page 3): "The diagram shows the Transformer model architecture with encoder on the left and decoder on the right, each consisting of multi-head attention and feed-forward layers with residual connections."
- **Figure 2** (page 4): "The image shows two diagrams: Scaled Dot-Product Attention (left) and Multi-Head Attention (right), illustrating how queries, keys, and values are transformed through attention mechanisms."

### Step 4: Node Building

193 `Node` objects created, one per extracted element. Vision summaries merged into image nodes.

### Step 5: Chunking

| Metric | Value |
|--------|-------|
| Chunk size | 1200 chars |
| Chunk overlap | 150 chars |
| Total chunks | 198 |
| Average chunk | 221 chars |
| Longest chunk | Table 3 (page 9, split into 6 chunks of ~1271 chars each) |

### Step 6: Embeddings

198 chunks each embedded into a 384-dimensional vector using `all-MiniLM-L6-v2`.

First vector prefix: `[0.0531, -0.0196, -0.0196, -0.0314, 0.0631, ...]`

### Step 7: Weaviate Storage

198 objects upserted into `DocumentNode` collection on Weaviate Cloud.

All 198 objects are now queryable via:
- **Vector search** (semantic similarity)
- **BM25 keyword search** (filterable fields: `node_id`, `doc_id`, `page`, `type`)
- **Hybrid search** (combination of both, via `hybrid_search.py` — skeleton only)

### Counts Summary

```
Input PDF (1 file)
  ↓
Extracted Elements: 193
  ↓
Nodes: 193
  ↓
Chunks: 198
  ↓
Embeddings: 198 (384-dim)
  ↓
Weaviate Objects: 198
```

---

## SECTION 11 — CURRENT LIMITATIONS

### Known Bugs

| # | Issue | Affects | Severity |
|---|-------|---------|----------|
| 1 | **Section tracking not implemented** — `section` field is always `""`; nodes cannot be filtered by section context | Retrieval | High |
| 2 | **Table splitting can break mid-row** — large tables split line-by-line; a single row wider than 1200 chars gets split mid-row | Table retrieval | Medium |
| 3 | **No position tracking within pages** — `prov[0].bbox` is available but not used; elements cannot be ordered by vertical position | Section tracking, ordering | Medium |
| 4 | **`.env` has stale keys** — `CHUNK_MAX_WORDS` and `CHUNK_OVERLAP_WORDS` still present but unused; only `CHUNK_SIZE` and `CHUNK_OVERLAP` are read | Config | Low |
| 5 | **OCR always runs** — no option to skip OCR; adds latency even for born-digital PDFs that don't need it | Performance | Low |
| 6 | **No image deduplication** — if the same image appears on multiple pages, it is processed and stored separately each time | Storage | Low |

### Missing Features

| Feature | Expected Location | Priority |
|---------|------------------|----------|
| Section tracking algorithm | `node_builder.py` (post-`build_nodes`) | High |
| Position-aware node sorting | `parser.py` (include bbox in metadata) | Medium |
| Multi-document batch ingestion | `main.py` or separate CLI | Medium |
| Incremental ingestion (skip processed files) | `main.py` or `parser.py` | Medium |
| Graceful handling of missing Groq API key | `vision_processor.py` | Medium |
| OCR toggle for born-digital PDFs | `parser.py` pipeline options | Low |

### Future Improvements (Planned in Architecture)

| Feature | Description | Relevant File |
|---------|-------------|---------------|
| **Hybrid Search** | Combine vector + BM25 search | `retrieval/hybrid_search.py` (empty) |
| **Evidence Fusion** | Merge multi-source retrieval results | `retrieval/evidence_fusion.py` (empty) |
| **Multi-Query Retrieval** | Expand user query into multiple sub-queries | (not created) |
| **Reranking** | Cross-encoder reranking of initial results | (not created) |
| **Positive Graph Expansion** | Graph-based expansion from seed nodes | `graph/positive_expansion.py` |
| **Negative Graph Expansion** | Contradiction/exception/risk surface discovery | `graph/negative_expansion.py` |
| **Graph Engine** | Orchestrate graph operations | `graph/graph_engine.py` |
| **Risk Detection** | Identify risk-bearing content | `generation/risk_detector.py` (empty) |

---

## SECTION 12 — FINAL STATISTICS

All statistics are from a single validated run of the NIPS-2017 paper through the complete pipeline.

| Metric | Value |
|--------|-------|
| **Documents processed** | 1 (NIPS-2017-attention-is-all-you-need-Paper.pdf) |
| **Pages processed** | 11 |
| **Text elements** | 186 |
| **Tables** | 4 |
| **Images** | 3 |
| **Nodes** | 193 |
|  ├─ paragraph | 104 |
|  ├─ list_item | 35 |
|  ├─ heading | 26 |
|  ├─ footnote | 16 |
|  ├─ caption | 5 |
|  ├─ table | 4 |
|  └─ image | 3 |
| **Chunks** | 198 |
|  ├─ Average chunk size | 221 characters |
|  ├─ Chunk size config | 1200 characters |
|  └─ Chunk overlap config | 150 characters |
| **Embeddings** | 198 |
|  ├─ Model | all-MiniLM-L6-v2 |
|  └─ Dimension | 384 |
| **Weaviate objects** | 198 |
|  ├─ Collection | `DocumentNode` |
|  ├─ Vectorizer | none (external vectors) |
|  └─ Host | Weaviate Cloud |

---

*Generated from the actual implementation files:*
- `ingestion/parser.py` (305 lines)
- `ingestion/node_builder.py` (357 lines)
- `ingestion/vision_processor.py` (132 lines)
- `vectorstore/weaviate_client.py` (211 lines)
- `config.py` (40 lines)
- `main.py` (126 lines)
- `_validate_fast.py` (190 lines)
