# DocuMind Project: Single Source of Truth (SSOT)

Welcome to the **DocuMind Graph** SSOT! This document provides a comprehensive overview of what the project does, the entire technology stack in detail, how the dual-memory graph is built, a mapped-out folder structure, and complete setup instructions for a new developer.

---

## 1. Project Overview: What is it doing?

DocuMind is an **Agentic KG-RAG (Knowledge Graph - Retrieval-Augmented Generation) system featuring Negative Graph Expansion**. 

Unlike standard RAG systems that only retrieve information supporting a query, DocuMind uses multi-modal ingestion (text, tables, images) to build a complex Knowledge Graph. It actively retrieves and evaluates **negative edges** (exceptions, contradictions, risks, limitations, warnings) related to the user's query. This means when a user asks a question, the LLM not only provides an answer based on supporting context but also explicitly highlights contradicting evidence or risks found elsewhere in the document(s). 

**Key capabilities:**
- **Multi-modal Parsing**: Understands PDFs and DOCX files, extracting paragraphs, tables, footnotes, headings, and images.
- **Vision Integration**: Leverages Llama Vision models to describe and semantically process images embedded in documents.
- **Dual Memory Architecture**: 
  - *Semantic Memory*: Vector Database (Weaviate) for standard semantic and keyword hybrid searches.
  - *Structural Memory*: Graph Database (NetworkX in-memory) for mapping positive and negative relations between nodes.
- **Risk-Aware AI Generation**: Uses Groq (Llama 3.3 70B) to generate highly contextual answers that flag contradictions and calculate confidence scores.

---

## 2. Technology Stack: Everything Used in Detail

This project relies on a 100% free-tier-friendly modern AI stack. Here is a detailed breakdown of every component and why it is used.

### Backend Core
* **Python 3.12+**: Primary backend language.
* **FastAPI & Uvicorn**: High-performance asynchronous API framework used for routing (`/upload`, `/query`, `/graph`). Chosen for its speed and native Pydantic integration.
* **Pydantic**: Used for strict data validation and request/response type hinting.

### Document Parsing & Ingestion
* **Docling (`ingestion/parser.py`)**: The primary ML-based parser. It highly accurately extracts document structures, recognizing paragraphs, tables, footnotes, figures, and captions, and retains spatial metadata.
* **PyMuPDF / fitz (`ingestion/pymupdf_parser.py`)**: **The Fallback Parser.** Used for large or highly complex PDFs where Docling's ML layout model might crash (e.g., `std::bad_alloc` errors). It operates with zero ML models, relying purely on C++ PDF rendering and font-size heuristics (e.g., classifying text as "headings" if the font size is 1.25x the page's median size, or "footnotes" if they are small and at the bottom).

### AI & Embeddings
* **Sentence-Transformers**: Runs locally to generate embeddings for semantic search (using `all-MiniLM-L6-v2` or `BGE` models). Avoids API costs for vectorization.
* **Groq API (`meta-llama/llama-4-scout-17b-16e-instruct`)**: Used for Vision processing to summarize images and charts extracted from the documents.
* **Groq API (`Llama 3.3 70B`)**: Used as the primary LLM for final response generation due to its ultra-fast inference speed.

### Dual Memory Databases
* **Weaviate (`vectorstore/weaviate_client.py`)**: The vector database used for Semantic Memory. It stores the embeddings of the parsed nodes and performs Hybrid Search (combining vector similarity with keyword BM25 search) to find the most relevant "Seed Nodes".
* **NetworkX (`graph/graph_engine.py`)**: An in-memory graph library used for Structural Memory. It maps out how different nodes (paragraphs, tables, images) relate to each other sequentially and semantically.

### Frontend & Visualization
* **Next.js (React 19)**: The modern UI frontend (`next-js-frontend`). Handles the chat interface and document upload.
* **react-force-graph-2d**: A React component that natively renders the NetworkX graph data in the browser using HTML5 Canvas, creating a dynamic, interactive visualization of the knowledge graph.
* **Tailwind CSS v4**: Utility-first CSS framework for rapid UI styling.

---

## 3. How the Graph is Built (Architecture & Logic)

The core innovation of DocuMind is its Structural Memory (Knowledge Graph). Here is exactly how it is built.

### A. Semantic Node Creation
During ingestion, the parser (Docling or PyMuPDF) extracts raw elements. The `node_builder.py` normalizes these into standardized semantic nodes. 
**Valid Node Types:** `heading`, `paragraph`, `table`, `image`, `figure`, `caption`, `footnote`, `chart`, `list_item`, `formula`.

### B. Positive Edge Inference (The Structural Skeleton)
Once nodes are created, `graph_engine.py` infers **positive edges** (supporting relationships) to build the skeleton of the graph:
- **`belongs_to`**: Links paragraphs, tables, and images back to their parent section heading.
- **`follows`**: Links sequential paragraphs within the same section together.
- **Type-Based Links**: Connects co-occurring elements on the same page. E.g., `caption_to_image` connects a caption to its adjacent image; `paragraph_to_figure` links text to a chart; `has_footnote` links a paragraph to a footnote at the bottom of the page.

### C. Negative Edge Detection (The Risk Engine)
After the positive skeleton is built, `negative_expansion.py` runs. This module scans the content of every node for specific trigger keywords to forge **negative edges**:
1. **Low Risk (`qualifies`)**: Triggered by words like *"however"*, *"although"*, *"note that"*.
2. **Medium Risk (`exception_to`, `warning_for`, `limitation_of`)**: Triggered by words like *"except"*, *"unless"*, *"caution"*, *"limited to"*.
3. **High Risk (`contradicts`, `risk_for`)**: Triggered by words like *"contradicts"*, *"invalidates"*, *"supersedes"*.

When a trigger keyword is found in a node (e.g., a footnote saying "Except in Q3..."), the system creates a negative edge pointing from that footnote to its target (usually the paragraphs it `belongs_to` or shares a page with).

### D. Graph Expansion at Query Time
When a user asks a question:
1. **Hybrid Search**: Weaviate finds the top relevant "Seed Nodes".
2. **Positive Expansion**: The system traverses 1-hop along positive edges to grab supporting context (e.g., fetching the table that a seed paragraph describes).
3. **Negative Expansion**: The system traverses along negative edges. If a seed paragraph has a negative edge pointing to a footnote containing a warning, that footnote is pulled into the context as "Risk Evidence". The overall risk level of the answer is escalated (Low/Medium/High) based on what negative nodes are found.

---

## 4. Folder Structure & Key Files

Here is the mapped-out architecture of the repository:

```text
DocuMind/
├── .env.example                     # Template for environment variables
├── config.py                        # Centralized configuration (Groq keys, Weaviate URL, Feature flags)
├── main.py                          # FastAPI Entry Point (routes: /upload, /query, /graph)
├── pyproject.toml / requirements.txt# Python dependency definitions
├── Readme.md                        # Original architectural outline
│
├── frontend/                        # User Interfaces
│   ├── app.py.obsolete              # Legacy Streamlit UI
│   └── next-js-frontend/            # Modern React/Next.js Application
│       ├── package.json             # Node dependencies
│       └── src/                     # React components, pages, force-graph logic
│
├── ingestion/                       # Phase 1: Parsing & Extraction
│   ├── parser.py                    # Primary parser using Docling ML models
│   ├── pymupdf_parser.py            # High-performance C++ fallback parser using fitz (PyMuPDF) heuristics
│   ├── vision_processor.py          # Sends images to Groq Vision API for summarization
│   └── node_builder.py              # Structures raw parsed elements into standard graph "nodes"
│
├── vectorstore/                     # Phase 2: Semantic Memory
│   └── weaviate_client.py           # Connects to Weaviate, manages the "DocuMindNode" schema and imports
│
├── graph/                           # Phase 2 & 3: Structural Memory & Graph Expansion
│   ├── graph_engine.py              # Defines the NetworkX 'KnowledgeGraph' (nodes, positive edges, serializers)
│   ├── positive_expansion.py        # Traverses positive supporting edges (e.g., belongs_to)
│   └── negative_expansion.py        # Detects keywords to forge negative edges and traverses them
│
├── retrieval/                       # Phase 3: Hybrid Search Pipeline
│   ├── hybrid_search.py             # Interfaces with Weaviate for Vector + Keyword search
│   └── evidence_fusion.py           # Deduplicates and merges Hybrid Search + Graph Expansion contexts
│
├── generation/                      # Phase 4: Risk-Aware LLM Generation
│   ├── risk_detector.py             # Analyzes negative evidence to output Risk Levels (High, Medium, Low)
│   ├── prompt_builder.py            # Injects evidence, risks, and queries into the LLM system prompt
│   └── groq_client.py               # Wrapper for the Groq LLM API client
│
├── visualization/                   # Backend Graph Visualization Tools
│   └── graph_snapshot.py            # Generates PyVis interactive HTML graphs (Legacy)
│
├── data/                            # Local Storage Directory
│   ├── uploads/                     # Uploaded raw PDFs/DOCX files
│   └── processed/                   # Where processed/cached data resides
```

---

## 5. Setup Instructions (From Scratch)

If you are a new developer setting up DocuMind locally, follow these steps.

### Prerequisites
- **Python 3.12+**
- **Node.js 20+**
- A **Weaviate Cloud** cluster (Free Sandbox is fine) or a local dockerized Weaviate instance.
- A **Groq API Key** (Free tier from console.groq.com).

### Step 1: Backend Setup
1. **Clone the repository** and open a terminal in the project root (`DocuMind/`).
2. **Create a Python Virtual Environment**:
   ```bash
   python -m venv .venv
   
   # Windows:
   .venv\Scripts\activate
   # macOS/Linux:
   source .venv/bin/activate
   ```
3. **Install Dependencies** (You can use `pip` or `uv`):
   ```bash
   pip install -r requirements.txt
   ```
4. **Environment Variables**:
   Copy `.env.example` to `.env`.
   ```bash
   cp .env.example .env
   ```
   Open `.env` and fill in the critical fields:
   - `GROQ_API_KEY=your_groq_key`
   - `WEAVIATE_URL=your_weaviate_cluster_url`
   - `WEAVIATE_API_KEY=your_weaviate_api_key`
   *(Note: You can toggle feature flags like `ENABLE_VISION=true` or `ENABLE_WEAVIATE=true` in this file).*

5. **Start the FastAPI Server**:
   ```bash
   uvicorn main:app --reload
   ```
   The backend will now be running on `http://127.0.0.1:8000`.

### Step 2: Frontend Setup
1. **Navigate to the Next.js directory**:
   ```bash
   cd frontend/next-js-frontend
   ```
2. **Install Node modules**:
   ```bash
   npm install
   # or, if facing peer-dependency issues:
   npm install --legacy-peer-deps
   ```
3. **Start the Next.js Development Server**:
   ```bash
   npm run dev
   ```
   The frontend will start on `http://localhost:3000`.

### Step 3: Usage
1. Open your browser to `http://localhost:3000`.
2. Ensure both your FastAPI terminal and Next.js terminal are running without errors.
3. Upload a sample document (PDF/DOCX) via the UI. Watch the FastAPI terminal for ingestion logs.
4. Once ingested, ask a question in the chat interface. You should receive a generated response, risk assessment, and see the interactive Knowledge Graph update visually!
