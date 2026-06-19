# DocuMind Graph v2.0: 3-Day Hackathon Implementation Plan

**Multi-Modal Agentic KG-RAG with Negative Graph Expansion for Intelligent Document Understanding**

This plan outlines the team roles, feature divisions, Git repository architecture, and day-by-day milestones to deliver the updated DocuMind Graph v2.0 MVP within 2.5 to 3 days using a 100% free-tier stack.

### Architecture includes:
- Multi-Modal Document Understanding
- Llama 3.2 Vision (Groq)
- Weaviate Hybrid Retrieval
- NetworkX Knowledge Graph
- Positive Graph Expansion
- **Negative Graph Expansion (Core Innovation)**
- Risk-Aware Answer Generation
- Explainability Dashboard
- Cross-Document QA

---

## Git Branching & Collaborative Workflow

To minimize merge conflicts during the hackathon, every member works on isolated modules and merges through Pull Requests.

```
documind-graph/
├── .env.example
├── requirements.txt
├── config.py
├── main.py
│
├── ingestion/
│   ├── parser.py
│   ├── vision_processor.py
│   └── node_builder.py
│
├── graph/
│   ├── graph_engine.py
│   ├── positive_expansion.py
│   └── negative_expansion.py
│
├── vectorstore/
│   └── weaviate_client.py
│
├── retrieval/
│   ├── hybrid_search.py
│   └── evidence_fusion.py
│
├── generation/
│   ├── groq_client.py
│   ├── risk_detector.py
│   └── prompt_builder.py
│
├── visualization/
│   └── graph_snapshot.py
│
├── frontend/
│   └── app.py
│
└── data/
    ├── uploads/
    └── processed/
```

---

## Team Roles & Responsibilities

| Name | File / Module | Primary Focus | Key Deliverables |
|---|---|---|---|
| **Karen** | `graph/graph_engine.py`, `positive_expansion.py`, `negative_expansion.py` | Structural Memory & Graph Intelligence | Knowledge graph construction, positive/negative edge creation, graph traversal algorithms, graph visualization |
| **Rakshitha** | `vectorstore/weaviate_client.py`, `retrieval/evidence_fusion.py` | Semantic Memory & Retrieval | Weaviate schema, hybrid retrieval, metadata filtering, evidence fusion |
| **Sambhav** | `main.py`, `config.py` | Backend Integration | FastAPI APIs, environment configs, orchestration, startup scripts |
| **Tharun** | `ingestion/parser.py`, `vision_processor.py`, `node_builder.py` | Multi-Modal Ingestion | Docling parser, image processing, semantic node creation |
| **Surjith** | `generation/*.py`, `frontend/app.py` | LLM & Explainability | Groq integration, risk detection, Streamlit UI, explainability dashboard |

---

## Day 1: Multi-Modal Foundation

**Goal:** Convert documents into semantic nodes and store them in both memories.

---

### Sambhav — `feature/backend-skeleton`

**Tasks:**
- Setup repository structure
- Create `requirements.txt`
- Configure `.env`
- Build FastAPI skeleton
- Create upload endpoint

**Deliverables:**
```
POST /upload
POST /query
```

---

### Tharun — `feature/multimodal-ingestion`

**Tasks:**

Integrate Docling and extract:
- Paragraphs, Tables, Images, Charts
- Captions, Footnotes, Headings

Use **Llama 3.2 Vision 11B** via Groq for:
- Image description
- Chart understanding
- Figure explanation
- Visual metadata extraction

**Output semantic nodes:**
```json
{
  "id": "image_07",
  "type": "image",
  "page": 5,
  "doc_id": "report_A",
  "content": "Revenue growth chart showing 15% YoY increase"
}
```

---

### Karen — `feature/graph-foundation`

**Tasks:** Create NetworkX graph.

**Node types:** Heading, Paragraph, Table, Image, Figure, Caption, Footnote, Chart

**Positive edges:**
- `belongs_to`, `references`, `describes`
- `caption_to_image`, `paragraph_to_figure`, `figure_to_table`

---

### Rakshitha — `feature/weaviate-setup`

**Tasks:** Create Weaviate schema.

**Store:** `node_id`, `doc_id`, `page`, `section`, `type`, `content`, `embedding`

**Integrate:** BGE-small-en-v1.5 embeddings

---

### Surjith — `feature/groq-setup`

**Tasks:**
- Create API wrappers for Llama 3.3 70B and Llama 3.2 Vision 11B
- Build Streamlit chat interface skeleton

---

### Day 1 Milestone

```
PDF → Semantic Nodes → Weaviate + NetworkX
```
All working end-to-end on a test document.

---

## Day 2: Dual Memory & Negative Graph Expansion

**Goal:** Implement the unique retrieval engine — the core innovation.

---

### Tharun — `feature/footnotes-captions`

**Tasks:** Improve extraction of footnotes, captions, figure references, and table references. Link them through metadata.

---

### Karen — `feature/negative-expansion`

**Tasks:** Build negative edge heuristics.

**Trigger keywords:**
```
except, however, unless, excluding, despite,
warning, risk, limitation, note that, not applicable
```

**Negative edge types generated:**
- `qualifies`, `exception_to`, `contradicts`
- `limitation_of`, `warning_for`, `risk_for`

**Positive Expansion path:**
```
Paragraph → Table → Heading → Image
```

**Negative Expansion path:**
```
Paragraph → Footnote → Exception → Risk → Contradiction
```

**Graph visualization:**
- Positive edges: solid green
- Negative edges: dashed red

---

### Rakshitha — `feature/evidence-fusion`

**Tasks:** Implement full retrieval pipeline.

```
Weaviate Hybrid Search
       ↓
   Seed Nodes
       ↓
Positive Expansion
       ↓
Negative Expansion
       ↓
Evidence Fusion
```

**Output structure:**
```json
{
  "supporting": [],
  "exceptions": [],
  "contradictions": [],
  "risks": []
}
```

---

### Surjith — `feature/risk-engine`

**Tasks:** Build Risk Detection Engine.

**Risk levels:**

| Signal | Level |
|---|---|
| `however`, `note that` | Low |
| `warning`, `limitation` | Medium |
| `critical risk`, `does not apply` | High |

---

### Sambhav — `feature/api-integration`

**Tasks:** Connect Parser → Graph → Weaviate → Retrieval → Groq through FastAPI orchestration layer.

---

### Day 2 Milestone

Query retrieves: Paragraph + Table + Image + Footnote + Contradiction and displays graph snapshot.

---

## Day 3: Explainability, Cross-Document QA & Demo

**Goal:** Build demo-ready experience, add stretch goal, rehearse.

---

### Surjith — `feature/explainability-ui`

Build Streamlit dashboard showing:
- Final answer
- Confidence score
- Risk flags (Low / Med / High)
- Citations with page numbers
- Evidence source breakdown

**Example evidence panel:**
```
✓ Paragraph  — Page 4
✓ Table      — Page 5
✓ Footnote   — Page 6
✓ Figure     — Page 7
Risk Level: Medium
```

---

### Karen — `feature/graph-optimization`

**Tasks:**
- Optimize graph traversal and layout rendering
- Improve snapshot generation speed
- Add cross-document edges for bonus stretch goal

---

### Rakshitha — `feature/cross-doc-retrieval`

**Tasks:** Enable `cross_doc=True` flag.

Retrieve and synthesize from Doc A + Doc B + Doc C simultaneously using Weaviate `doc_id` filters and NetworkX inter-document edges.

---

### Sambhav — `feature/final-runner`

**Tasks:** Create `start.bat` and `start.sh` to launch FastAPI + Streamlit with a single command. Final integration testing.

---

### Tharun — `feature/testing`

**Tasks:** Run testing on annual reports, research papers, and technical manuals.

**Target metrics:**

| Metric | Target |
|---|---|
| Retrieval Accuracy | ≥ 75% |
| Answer Quality | ≥ 70% |
| Multi-modal Coverage | ≥ 2/3 modalities |
| Relationship Awareness | ≥ 3 cross-element questions |
| Demo Stability | No crashes on test docs |

---

### Day 3 Milestone

Fully integrated system with multi-modal understanding, negative graph expansion, explainability dashboard, and cross-document retrieval — ready for demo.

---

## Demo Flow

**Upload:** `Annual_Report_2024.pdf`

**Question:**
> *"Why did profit decrease despite revenue growth?"*

**Retrieval — system finds:**
- Revenue paragraph (Page 4)
- Expense table (Page 5)
- Growth chart (Page 7)
- Footnote: *"Excluding APAC region"* — `exception_to` edge triggered

**Answer:**
> Profit decreased because operating expenses rose 35%, driven by R&D costs increasing from $12M to $18M. **However**, this analysis excludes APAC, which reported 20% profit growth.

**Explainability panel:**
```
Confidence: 92%
Evidence:
  ✓ Paragraph  Page 4   [hybrid search]
  ✓ Table      Page 5   [positive expansion]
  ✓ Figure     Page 7   [positive expansion]
  ✓ Footnote   Page 6   [negative expansion ← exception_to]
Risk Level: Medium
```

---

## Technology Stack

| Component | Technology |
|---|---|
| Document Parsing | Docling |
| Vision Understanding | Llama 3.2 Vision 11B (Groq API) |
| Embeddings | BGE-small-en-v1.5 |
| Vector Database | Weaviate |
| Graph Engine | NetworkX |
| LLM | Llama 3.3 70B (Groq API) |
| Backend | FastAPI |
| Frontend | Streamlit |
| Visualization | NetworkX + Matplotlib |

> **One Groq API key serves both models. 100% free tier.**

---

## Core Innovation: Negative Graph Expansion

**Traditional RAG:**
```
Question → Supporting Evidence → Answer
```

**DocuMind Graph:**
```
Question
    ↓
Supporting Evidence  (positive expansion)
    ↓
Exceptions           (negative expansion → exception_to edges)
    ↓
Contradictions       (negative expansion → contradicts edges)
    ↓
Risks                (negative expansion → risk_for edges)
    ↓
Risk-Aware Answer with citations and confidence score
```

This produces more **complete**, **trustworthy**, and **explainable** document intelligence — the answer knows what it doesn't know.

---

*DocuMind Graph v2.0 — built for the Multi-Modal Semantic Integration Hackathon*
