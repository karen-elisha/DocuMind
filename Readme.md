# 🧠 DocuMind Graph

### Agentic KG-RAG with Negative Graph Expansion

> **Core innovation:** negative edges surface exceptions, contradictions, and risks

✅ **100% FREE TIER** — Groq • Weaviate • NetworkX • Streamlit • FastAPI • PyVis

---

## Phase 1 — MULTI-MODAL INGESTION

> Text, tables, and images all handled • No local GPU needed

```
1. Input Documents  →  2. Docling Parser  →  3. Llama 3.2 Vision 11B  →  4. Semantic Nodes
                                                (Via Groq API - Free)
```

### 1. Input Documents
- PDF, DOCX
- Reports, manuals
- Multi-doc support

### 2. Docling Parser
Extracts:
- 📝 Paragraphs
- 📊 Tables
- 🔤 Headings
- 💬 Captions
- 📌 Footnotes
- 🖼️ Figures / Images

### 3. Llama 3.2 Vision 11B (Via Groq API — Free)
- Image → description
- Chart understanding
- Figure/diagram reasoning
- Caption linking
- Visual metadata extraction

### 4. Semantic Nodes
Create atomic semantic nodes with metadata:

| ID | Type | Content |
|---|---|---|
| `para_12` | Paragraph | Paragraph |
| `table_04` | Table | Table |
| `image_07` | Image | Image |
| `caption_02` | Caption | Caption |
| `footnote_03` | Footnote | Footnote |
| `heading_01` | Heading | Heading |

### Examples of Extracted Elements

| Icon | Element |
|---|---|
| 📝 | Paragraph |
| 📊 | Table |
| 🖼️ | Image / Figure |
| 📈 | Chart |
| 💬 | Caption |
| 📌 | Footnote |
| **H1** | Heading |

> **Output:** Clean multi-modal semantic nodes ready for graph construction + vector storage

---

## Phase 2 — DUAL MEMORY GRAPH

> Built once on ingestion • Both memories queried in parallel at retrieval time

### A. Structural Memory — NetworkX
**Hierarchical Knowledge Graph**

**Positive edges (supporting):**
- `belongs_to`
- `references`
- `follows`
- `describes`
- `has_footnote`
- `caption_to_image`
- `paragraph_to_figure`
- `figure_to_table`

**Negative edges (risk / exception):**
- `exception_to`
- `contradicts`
- `limits`
- `warns`
- `doc_id_tag`
- `cross-doc traversal`

### B. Semantic Memory — Weaviate
**Vector Database (Hybrid Search)**

- BGE-small-en-v1.5 embeddings
- Hybrid search: vector + keyword
- Filters: type • page • section • doc_id
- Cross-document references

| ID | Type | Page | Section | Doc_ID | Embedding (...) |
|---|---|---|---|---|---|
| `para_12` | paragraph | 4 | Revenue | doc_A | `[0.12, 0.83, …]` |
| `table_04` | table | 5 | Revenue | doc_A | `[0.11, 0.42, …]` |
| `image_07` | image | 5 | Revenue | doc_A | `[0.21, 0.76, …]` |
| `caption_02` | caption | 5 | Revenue | doc_A | `[0.09, 0.33, …]` |
| `footnote_03` | footnote | 6 | Revenue | doc_A | `[0.14, 0.28, …]` |

### Edge Types (NetworkX)

**Positive edges (supporting):**
`belongs_to` · `references` · `follows` · `describes` · `has_footnote` · `caption_to_image` · `paragraph_to_figure` · `figure_to_table`

**Negative edges (risk / exception):**
`exception_to` · `contradicts` · `limits` · `warns` · `doc_id_tag` · `risk_for`

**Example negative link:**
```
Table
  ↑ exception_to
Footnote
  ↑ contradicts
Paragraph
```

> **Output:** Clean multi-modal semantic nodes ready for graph construction + vector storage

---

## Phase 3 — RETRIEVAL PIPELINE

> Positive context (what supports) + negative context (what contradicts/qualifies)

```
1. User Query  →  2. Hybrid Search  →  3. Positive Expansion  →  4. Supporting Evidence
                     (Weaviate)           (1-hop)
                                                                        ↓
              5. Negative Expansion  →  6. Risk Evidence  →  7. Risk Flags  →  6. Evidence Package
                   (1-hop)
```

### 1. User Query
- Natural language
- `cross_doc=True` flag optional

### 2. Hybrid Search (Weaviate)
- Vector + keyword
- Re-rank by score
- `doc_id` filter

### 3. Positive Expansion (1-hop)
- 1-hop: parent section
- Siblings + children
- Supporting context

### 4. Supporting Evidence
- Para + Table + Image from positive path

### 5. Negative Expansion (1-hop)
- ← same seeds, negative path
- 1-hop negative edges
- `exception_to` • `contradicts`
- `limits` • `warns` • `risk_for`
- Risk level: L/M/H

### 6. Risk Evidence
- Exception nodes
- Qualifier nodes
- Contradiction nodes
- Risk level: L/M/H

### 7. Risk Flags
- Low / Med / High
- Injected into Groq prompt with evidence

### 6. Evidence Package
Structured context ready for generation:
- Paragraphs
- Tables
- Images
- Charts
- Footnotes
- Captions
- Headings

### Node Types

| Color | Type |
|---|---|
| 🔵 | Heading |
| 🟣 | Paragraph |
| 🟢 | Table |
| 🟡 | Image / Figure |
| 🟠 | Caption |
| 🔴 | Footnote |
| 🟤 | Chart / Diagram |

> **Output:** Comprehensive evidence including what supports AND what contradicts

---

## Phase 4 — RISK-AWARE GENERATION + EXPLAINABILITY

> Answer knows what it doesn't know

### 1. Groq — Llama 3.3 70B
Prompt includes:
- Supporting evidence
- Risk evidence + flags
- Node types + pages
- **Output:** main claim + surfaced exceptions

### 2. Explainability UI (Streamlit)
- Streamlit only
- Answer + confidence
- Evidence nodes used
- Risk flags visible
- Provenance: search vs neg expansion

### 3. Graph Snapshot (PyVis)
- NetworkX + matplotlib
- Positive: solid edges
- Negative: dashed red
- Color: node type
- Cross-doc nodes labeled by `doc_id`

> **Output:** Final answer with confidence, citations, and risk-aware context

---

## 🌟 STRETCH GOAL — CROSS-DOCUMENT QA (BONUS)

```
Query with           Weaviate filters        NetworkX traverses       Answer synthesizes        Provenance shows
cross_doc=True  →  across all doc_ids  →  inter-document edges  →  evidence from Doc A    →  per-doc citations
                                                                    + Doc B simultaneously
```

---

## 🛠️ TECH STACK — 100% FREE TIER

| Component | Technology |
|---|---|
| Document Parsing | **Docling** |
| Vision Understanding | **Llama 3.2 Vision 11B** via Groq API (free) |
| Embeddings | **BGE-small-en-v1.5** |
| Hybrid Search | **Weaviate** (Vector + Keyword) |
| Graph Engine | **NetworkX** |
| LLM Generation | **Groq** — Llama 3.3 70B |
| Frontend | **Streamlit** |
| Backend | **FastAPI** |
| Visualization | **PyVis** |

---

> ⭐ **CORE INNOVATION:** Negative Graph Expansion retrieves hidden exceptions, contradictions, and risks — delivering truthful, complete, and trustworthy answers.
