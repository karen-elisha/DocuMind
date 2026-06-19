# Quick Start Guide

## 1. Prerequisites

- Python 3.10+
- Git
- VS Code (optional)

## 2. Clone Repository

```bash
git clone <repo_url>
cd Dell
```

## 3. Create Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

**Linux/Mac:**
```bash
python -m venv .venv
source .venv/bin/activate
```

## 4. Install Dependencies

```bash
pip install -r requirements.txt
```

## 5. Configure Environment

Copy `.env.example` to `.env` and fill in:

```env
GROQ_API_KEY=your_groq_key
WEAVIATE_URL=https://your-cluster.weaviate.cloud
WEAVIATE_API_KEY=your_weaviate_key
```

Options (all default to `false` for dev speed):
- `ENABLE_VISION=true` — Groq image summarization
- `ENABLE_EMBEDDINGS=true` — Vector embeddings
- `ENABLE_WEAVIATE=true` — Store to Weaviate
- `ENABLE_OCR=true` — OCR for scanned PDFs

## 6. Place a PDF

```text
data/uploads/your_file.pdf
```

## 7. Test Parser

```powershell
python test_parser.py "data\uploads\your_file.pdf"
```

Expected:
```
Pages: XX
Text elements: XX
Tables: XX
Images: XX
```

## 8. Test Nodes & Chunks

```powershell
python test_nodes.py "data\uploads\your_file.pdf"
```

## 9. Test Embeddings

```powershell
python test_embeddings.py "data\uploads\your_file.pdf"
```

Expected:
```
Embedding dimension: 384
Chunks generated: XX
```

## 10. Test Full Pipeline

```powershell
python test_weaviate.py "data\uploads\your_file.pdf"
```

Requires `ENABLE_EMBEDDINGS=true` and `ENABLE_WEAVIATE=true` in `.env`.

## 11. Output Locations

| Artifact | Path |
|----------|------|
| Extracted images | `data/processed/images/` |
| Docs & reports | `docs/` |

## Pipeline

```
PDF  →  Docling  →  Text / Tables / Images  →  Nodes  →  Chunks  →  Embeddings  →  Weaviate
```

## Common Issues

| Symptom | Fix |
|---------|-----|
| Weaviate connection error | Check `WEAVIATE_URL` and `WEAVIATE_API_KEY` in `.env` |
| Groq error | Check `GROQ_API_KEY` |
| No PDF found | Place file inside `data/uploads/` |
| Slow first run | Models load on first use; subsequent runs are faster |
| Empty elements | Some PDFs need `ENABLE_OCR=true` in `.env` |
