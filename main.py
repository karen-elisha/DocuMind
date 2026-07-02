import os
import re
import json
import base64
import io
import sys
import shutil
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from pydantic import BaseModel
from PIL import Image

from config import Config
from ingestion.parser import parse_document
from ingestion.vision_processor import summarize_images
from ingestion.node_builder import run_ingestion_pipeline
from graph.graph_engine import KnowledgeGraph
from graph.positive_expansion import PositiveExpander
from graph.negative_expansion import NegativeExpander
from retrieval.hybrid_search import retrieve_candidates, close_shared_client, warm_retrieval
from retrieval.reranker import rerank, warm_reranker
from generation.prompt_builder import build_prompt_from_fusion, build_prompt
from generation.risk_detector import score_nodes, confidence_from_risk, calculate_confidence, score_text
from generation.groq_client import chat, chat_stream
from generation.fact_verifier import verify_answer
from retrieval.risk_radar import build_risk_radar
from demo_questions import get_demo_questions, set_demo_questions
from generation.demo_question_generator import generate_demo_questions
from ingestion.mindmap_builder import build_mindmap
from ingestion.doc_cache import save as cache_save, load as cache_load, delete as cache_delete
from visualization.graph_snapshot import GraphVisualizer

kg = KnowledgeGraph()
visualizer = GraphVisualizer()
pos_expander = PositiveExpander()
neg_expander = NegativeExpander()
_query_pool = ThreadPoolExecutor(max_workers=6, thread_name_prefix="query")

Config.validate()
os.makedirs(Config.UPLOADS_DIR, exist_ok=True)
os.makedirs(Config.PROCESSED_DIR, exist_ok=True)
os.makedirs(Config.CACHE_DIR, exist_ok=True)

_DOCUMENT_INSIGHTS: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-load ML models and Weaviate connection so first query is fast."""
    try:
        warm_reranker()
        warm_retrieval()
    except Exception as exc:
        print(f"[Startup] Model warmup failed (non-fatal): {exc}")
    yield
    close_shared_client()


app = FastAPI(
    title="DocuMind Graph API",
    description="Agentic KG-RAG with Negative Graph Expansion",
    version="2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

VALID_GRAPH_TYPES = {"heading", "paragraph", "table", "image", "figure", "caption", "footnote", "chart"}
CHART_KEYWORDS = ["chart", "graph", "plot", "axis", "trend", "bar chart", "line chart", "pie chart", "scatter", "histogram", "distribution"]
FIGURE_PATTERN = re.compile(r'(?:figure|fig)[.\s]*(\d+)', re.IGNORECASE)
TABLE_PATTERN = re.compile(r'(?:table)[.\s]*(\d+)', re.IGNORECASE)
CHART_PATTERN = re.compile(r'(?:chart|graph)[.\s]*(\d+)', re.IGNORECASE)


class QueryRequest(BaseModel):
    query: str
    cross_doc: bool = False
    doc_id: str | None = None


def _image_to_base64(image_path: str, max_width: int = 800) -> str | None:
    try:
        img = Image.open(image_path)
        if img.mode != "RGB":
            img = img.convert("RGB")
        if img.width > max_width:
            ratio = max_width / img.width
            img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


def _is_chart(vision_summary: str) -> bool:
    if not vision_summary:
        return False
    s = vision_summary.lower()
    return any(re.search(r'\b' + re.escape(kw) + r'\b', s) for kw in CHART_KEYWORDS)


def _build_element_counts(elements: list) -> dict:
    counts: dict = {}
    for el in elements:
        t = el.get("type", "unknown")
        counts[t] = counts.get(t, 0) + 1
    return counts


def _group_text_by_page(elements: list) -> dict:
    pages: dict = {}
    for el in elements:
        t = el.get("type")
        if t not in ("heading", "paragraph", "caption", "footnote", "list_item", "formula"):
            continue
        page = str(el.get("page", 1))
        pages.setdefault(page, {"headings": [], "caption": [], "paragraphs": []})
        if t == "heading":
            pages[page]["headings"].append(el["content"])
        elif t == "caption":
            pages[page]["caption"].append(el["content"])
        else:
            pages[page]["paragraphs"].append(el["content"])
    return pages


def _build_insights(doc_id: str, parse_result: dict, vision_results: dict) -> dict:
    """Build and cache document insights including images, tables, charts, headings."""
    elements = parse_result.get("elements", [])
    img_list = parse_result.get("images", [])
    element_counts = _build_element_counts(elements)
    grouped_text = _group_text_by_page(elements)

    vision_by_image_id: dict = {}
    if vision_results:
        for img_key, vres in vision_results.items():
            if isinstance(vres, dict):
                vision_by_image_id[img_key] = vres

    images_data = []
    for img in img_list:
        img_id = img.get("image_id", "")
        img_path = img.get("image_path", "")
        cap = img.get("caption")
        vres = vision_by_image_id.get(img_id, {})
        vision_summary = vres.get("vision_summary", "") if isinstance(vres, dict) else ""
        vision_detail = vres.get("vision_detail", {}) if isinstance(vres, dict) else {}
        img_b64 = _image_to_base64(img_path) if os.path.exists(img_path) else None
        figure_number = img.get("figure_number", "")
        # Ensure vision_summary is never empty
        if not vision_summary:
            if cap:
                vision_summary = cap
            elif figure_number:
                vision_summary = f"[Figure {figure_number}] image on page {img.get('page', 1)}"
            else:
                vision_summary = f"image on page {img.get('page', 1)}"
        images_data.append({
            "image_id": img_id,
            "image_data": img_b64,
            "page": img.get("page", 1),
            "caption": cap,
            "figure_number": figure_number,
            "vision_summary": vision_summary,
            "vision_detail": vision_detail,
            "is_chart": _is_chart(vision_summary),
        })

    tables_data = []
    for el in elements:
        if el.get("type") == "table":
            content = el.get("content", "")
            md = dict(el.get("metadata") or {})
            headers = md.get("table_headers", [])
            rows = md.get("table_rows", [])
            tables_data.append({
                "page": el.get("page", 1),
                "element_id": el.get("element_id", ""),
                "markdown": content,
                "summary": content[:200].strip(),
                "table_number": md.get("table_number", ""),
                "caption": md.get("table_caption", ""),
                "headers": headers,
                "rows": rows,
            })

    headings_data = []
    for el in elements:
        if el.get("type") == "heading":
            headings_data.append({
                "page": el.get("page", 1),
                "content": el.get("content", ""),
                "level": el.get("metadata", {}).get("heading_level", 1),
            })

    parser_used = parse_result.get("parser", "unknown")
    parser_warning = parse_result.get("parser_warning")

    insight = {
        "document_name": parse_result.get("document_name", ""),
        "document_id": doc_id,
        "upload_time": datetime.now().isoformat(),
        "parser": parser_used,
        "parser_warning": parser_warning,
        "stats": {
            "pages": parse_result.get("pages_processed", 0),
            "headings": element_counts.get("heading", 0),
            "paragraphs": element_counts.get("paragraph", 0),
            "tables": element_counts.get("table", 0),
            "images": element_counts.get("image", 0),
            "captions": element_counts.get("caption", 0),
            "footnotes": element_counts.get("footnote", 0),
            "list_items": element_counts.get("list_item", 0),
            "formulas": element_counts.get("formula", 0),
            "charts": sum(1 for img in images_data if img.get("is_chart")),
        },
        "images": images_data,
        "tables": tables_data,
        "headings": headings_data,
        "extracted_text": grouped_text,
        "mindmap": build_mindmap(
            doc_id,
            parse_result.get("document_name", doc_id),
            elements,
            img_list,
            parse_result.get("pages_processed", 0),
        ),
    }
    _DOCUMENT_INSIGHTS[doc_id] = insight
    return insight


def _generate_and_store_demo_questions(doc_id: str, insight: dict) -> list[dict]:
    """Generate tailored demo questions and attach to document insights."""
    try:
        if doc_id in _DOCUMENT_INSIGHTS:
            _DOCUMENT_INSIGHTS[doc_id]["demo_questions_status"] = "generating"
        questions = generate_demo_questions(doc_id, insight)
        set_demo_questions(doc_id, questions, _DOCUMENT_INSIGHTS)
        if doc_id in _DOCUMENT_INSIGHTS:
            _DOCUMENT_INSIGHTS[doc_id]["demo_questions_status"] = "ready"
        return questions
    except Exception as exc:
        print(f"[Upload] Demo question generation failed (non-fatal): {exc}")
        if doc_id in _DOCUMENT_INSIGHTS:
            _DOCUMENT_INSIGHTS[doc_id]["demo_questions_status"] = "failed"
        return []


def _generate_demo_questions_async(doc_id: str, insight: dict) -> None:
    threading.Thread(
        target=_generate_and_store_demo_questions,
        args=(doc_id, insight),
        daemon=True,
    ).start()


def _find_figure(doc_id: str, figure_number: str) -> dict | None:
    insight = _DOCUMENT_INSIGHTS.get(doc_id)
    if not insight:
        return None
    for img in insight.get("images", []):
        if str(img.get("figure_number", "")) == str(figure_number):
            return img
    return None


def _find_table(doc_id: str, table_number: str) -> dict | None:
    insight = _DOCUMENT_INSIGHTS.get(doc_id)
    if not insight:
        return None
    for tbl in insight.get("tables", []):
        if str(tbl.get("table_number", "")) == str(table_number):
            return tbl
    return None


def _detect_figure_table_query(query: str, doc_id: str | None) -> dict | None:
    """Check if query references a figure/table and return it."""
    m = FIGURE_PATTERN.search(query)
    if m and doc_id:
        fig = _find_figure(doc_id, m.group(1))
        if fig:
            return {"type": "figure", "data": fig, "number": m.group(1)}

    m = TABLE_PATTERN.search(query)
    if m and doc_id:
        tbl = _find_table(doc_id, m.group(1))
        if tbl:
            return {"type": "table", "data": tbl, "number": m.group(1)}

    m = CHART_PATTERN.search(query)
    if m and doc_id:
        fig = _find_figure(doc_id, m.group(1))
        if fig:
            return {"type": "chart", "data": fig, "number": m.group(1)}

    return None


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"status": "healthy", "message": "DocuMind Graph v2.0 API is running."}


@app.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(file: UploadFile = File(...)):
    _, ext = os.path.splitext(file.filename.lower())
    if ext not in {".pdf", ".docx"}:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {ext}")

    file_path = os.path.join(Config.UPLOADS_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    doc_id = os.path.splitext(file.filename)[0]

    try:
        from_cache = False
        cached = cache_load(doc_id)

        if cached:
            # ── Cache hit: skip parse + vision + Weaviate check ──────────
            parse_result, vision_results, insight = cached
            from_cache = True
            stats = {"document_name": parse_result.get("document_name"), "note": "loaded from disk cache"}
            _DOCUMENT_INSIGHTS[doc_id] = insight

        else:
            # ── Cold path: full parse + vision + embed + store ───────────
            parse_result = parse_document(file_path=file_path, doc_id=doc_id)

            vision_results = {}
            if Config.ENABLE_VISION:
                vision_results = summarize_images(parse_result.get("images", []) or [])

            try:
                stats = run_ingestion_pipeline(parse_result=parse_result, vision_results=vision_results)
            except Exception as pipe_exc:
                print(f"[Upload] Pipeline step failed (non-fatal): {pipe_exc}")
                import traceback as tb
                tb.print_exc()
                stats = {"document_name": parse_result.get("document_name"), "note": f"Pipeline error: {pipe_exc}"}

            insight = _build_insights(doc_id, parse_result, vision_results)
            # Save to disk cache for future restarts
            cache_save(doc_id, parse_result, vision_results, insight)

        # ── Graph build (always runs — fast, in-memory only) ─────────────
        nodes_for_graph = [
            {
                "id":      el["element_id"],
                "type":    el["type"] if el["type"] in VALID_GRAPH_TYPES else "paragraph",
                "content": el["content"],
                "page":    el["page"],
                "section": el.get("metadata", {}).get("section", ""),
                "doc_id":  doc_id,
            }
            for el in parse_result.get("elements", [])
            if el.get("content", "").strip()
        ]

        def _build_graph(nodes):
            try:
                if nodes:
                    kg.build_from_nodes(nodes)
                    neg_expander.detect_negative_edges(kg)
            except Exception as graph_exc:
                print(f"[Upload] Graph build failed (non-fatal): {graph_exc}")

        threading.Thread(target=_build_graph, args=(nodes_for_graph,), daemon=True).start()

        # Snapshot counts before graph thread mutates the graph
        node_count = len(nodes_for_graph)
        edge_count = 0

        # ── Demo questions (always async) ─────────────────────────────────
        insight["demo_questions"] = insight.get("demo_questions") or []
        insight["demo_questions_status"] = "generating"
        _generate_demo_questions_async(doc_id, insight)

        return {
            "filename": file.filename,
            "doc_id": doc_id,
            "status": "success",
            "from_cache": from_cache,
            "message": f"{'Cache hit' if from_cache else 'Ingested'}. Graph: {node_count} nodes.",
            "graph_nodes": node_count,
            "graph_edges": edge_count,
            "stats": stats or {},
            "demo_questions_status": "generating",
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@app.post("/query")
async def query_pipeline(request: QueryRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    try:
        # ── Check for document summary queries ──────────────────────────
        is_summary_query = any(w in request.query.lower() for w in
            ["summarize", "summary", "overview", "what is this document about", "what does this document cover"])

        if is_summary_query and request.doc_id:
            insight = _DOCUMENT_INSIGHTS.get(request.doc_id, {})
            if insight:
                doc_name = insight.get("document_name", request.doc_id)
                stats = insight.get("stats", {})
                headings = insight.get("headings", []) or []
                tables = insight.get("tables", []) or []
                images = insight.get("images", []) or []
                extracted = insight.get("extracted_text", {})
                pages_list = sorted(extracted.keys(), key=int)

                heading_text = "\n".join(
                    f"{'#' * h.get('level', 1)} {h.get('content', '')}"
                    for h in headings[:20]
                ) if headings else ""

                table_summaries = "\n".join(
                    f"Table {t.get('table_number', '?')}: {t.get('caption', '')[:100]}"
                    for t in tables[:5] if t.get('table_number') or t.get('caption')
                ) if tables else ""

                figure_summaries = "\n".join(
                    f"Figure {i.get('figure_number', '?')}: {i.get('vision_summary', '')[:150]}"
                    for i in images[:5] if i.get('figure_number') or i.get('vision_summary')
                ) if images else ""

                # Get first and last page paragraphs for intro/conclusion
                first_page = pages_list[0] if pages_list else ""
                last_page = pages_list[-1] if len(pages_list) > 1 else ""
                first_paras = "\n".join(extracted.get(first_page, {}).get("paragraphs", [])[:3]) if first_page else ""
                last_paras = "\n".join(extracted.get(last_page, {}).get("paragraphs", [])[-3:]) if last_page else ""

                summary_context = f"""Document: {doc_name}
Pages: {stats.get('pages', '?')}
Sections/Headings:
{heading_text or '(none)'}

{'--- Tables ---' if table_summaries else ''}
{table_summaries}

{'--- Figures ---' if figure_summaries else ''}
{figure_summaries}

--- Opening paragraphs ---
{first_paras[:500]}

--- Closing paragraphs ---
{last_paras[:500]}"""

                summary_prompt = build_prompt(
                    query=request.query,
                    supporting=[{
                        "type": "paragraph",
                        "page": 1,
                        "content": summary_context,
                        "figure_number": "",
                        "table_number": "",
                        "caption": "",
                        "vision_summary": "",
                    }],
                    exceptions=[], contradictions=[], risks=[],
                    overall_risk_level="None",
                    cross_doc=request.cross_doc,
                )
                answer = chat(summary_prompt["user"], system=summary_prompt["system"])
                summary_conf = calculate_confidence("None", support_count=len(headings) + len(tables), has_media=bool(images))

                return {
                    "query": request.query,
                    "routed": False,
                    "answer": answer,
                    "confidence_score": summary_conf,
                    "risk_level": "None",
                    "evidence": {
                        "supporting": [{
                            "type": "paragraph",
                            "page": 1,
                            "content": summary_context[:500],
                            "document_id": request.doc_id,
                            "document_name": doc_name,
                            "pdf_url": f"http://localhost:8000/document/file/{request.doc_id}.pdf#page=1",
                            "anchor": "page-1",
                        }],
                        "exceptions": [], "contradictions": [], "risks": [], "warnings": [], "limitations": [],
                    },
                    "documents_used": [request.doc_id],
                }

        # ── Query routing: check for figure/table references ───────────
        routed = _detect_figure_table_query(request.query, request.doc_id)

        if routed:
            fig_data = routed["data"]
            rtype = routed["type"]
            rnum = routed["number"]
            insight = _DOCUMENT_INSIGHTS.get(request.doc_id, {})
            doc_name = insight.get("document_name", request.doc_id) if request.doc_id else ""

            # Build evidence from graph neighbors + nearby paragraphs
            evidence_nodes = []
            nearby_text = ""

            # Find related paragraph nodes via graph edges
            if request.doc_id:
                for nid, attrs in kg.graph.nodes(data=True):
                    if attrs.get("doc_id") != request.doc_id:
                        continue
                    ntype = attrs.get("type", "")
                    n_fig = attrs.get("metadata", {}).get("figure_number", "") or ""
                    n_tbl = attrs.get("metadata", {}).get("table_number", "") or ""
                    if rtype in ("figure", "chart") and n_fig and str(n_fig) == str(rnum):
                        evidence_nodes.append({"node_id": nid, **attrs})
                    if rtype == "table" and n_tbl and str(n_tbl) == str(rnum):
                        evidence_nodes.append({"node_id": nid, **attrs})

            # Add image data to figure nodes
            supporting = []
            if rtype in ("figure", "chart"):
                for ev in evidence_nodes:
                    ev["document_id"] = request.doc_id or ""
                    ev["document_name"] = doc_name
                    ev["page"] = ev.get("page", 1)
                    ev["pdf_url"] = f"http://localhost:8000/document/file/{request.doc_id}.pdf#page={ev.get('page',1)}" if request.doc_id else ""
                    ev["anchor"] = f"fig-{rnum}"
                    # Add figure data from insight
                    if fig_data and fig_data.get("image_data"):
                        ev["image_data"] = fig_data["image_data"]
                        ev["vision_summary"] = fig_data.get("vision_summary", "")
                        ev["figure_number"] = rnum
                        ev["caption"] = fig_data.get("caption", "")
                    supporting.append(ev)
                if not supporting:
                    # Fallback: directly use fig_data as a standalone node
                    if fig_data:
                        supporting.append({
                            "node_id": f"figure_{rnum}",
                            "type": "figure",
                            "page": fig_data.get("page", 1),
                            "content": fig_data.get("caption", "") or fig_data.get("vision_summary", "") or "",
                            "document_id": request.doc_id or "",
                            "document_name": doc_name,
                            "pdf_url": f"http://localhost:8000/document/file/{request.doc_id}.pdf#page={fig_data.get('page',1)}" if request.doc_id else "",
                            "anchor": f"fig-{rnum}",
                            "image_data": fig_data.get("image_data", ""),
                            "vision_summary": fig_data.get("vision_summary", ""),
                            "figure_number": rnum,
                            "caption": fig_data.get("caption", ""),
                            "vision_detail": fig_data.get("vision_detail", {}),
                        })

            elif rtype == "table":
                for ev in evidence_nodes:
                    ev["document_id"] = request.doc_id or ""
                    ev["document_name"] = doc_name
                    ev["page"] = ev.get("page", 1)
                    ev["pdf_url"] = f"http://localhost:8000/document/file/{request.doc_id}.pdf#page={ev.get('page',1)}" if request.doc_id else ""
                    ev["anchor"] = f"tbl-{rnum}"
                    if fig_data:
                        ev["headers"] = fig_data.get("headers", [])
                        ev["rows"] = fig_data.get("rows", [])
                        ev["table_number"] = rnum
                        ev["caption"] = fig_data.get("caption", "")
                        ev["table_markdown"] = fig_data.get("markdown", "")
                    supporting.append(ev)
                if not supporting and fig_data:
                    supporting.append({
                        "node_id": f"table_{rnum}",
                        "type": "table",
                        "page": fig_data.get("page", 1),
                        "content": fig_data.get("markdown", fig_data.get("caption", ""))[:300],
                        "document_id": request.doc_id or "",
                        "document_name": doc_name,
                        "pdf_url": f"http://localhost:8000/document/file/{request.doc_id}.pdf#page={fig_data.get('page',1)}" if request.doc_id else "",
                        "anchor": f"tbl-{rnum}",
                        "headers": fig_data.get("headers", []),
                        "rows": fig_data.get("rows", []),
                        "table_number": rnum,
                        "caption": fig_data.get("caption", ""),
                    })

            # Gather nearby paragraphs from extracted text
            extracted = insight.get("extracted_text", {})
            page_str = str(fig_data.get("page", 1))
            if page_str in extracted:
                page_content = extracted[page_str]
                paras = page_content.get("paragraphs", [])
                if paras:
                    nearby_text = "\n".join(paras[:8])
                    supporting.append({
                        "node_id": f"nearby_{page_str}",
                        "type": "paragraph",
                        "page": int(page_str),
                        "content": nearby_text[:500],
                        "document_id": request.doc_id or "",
                        "document_name": doc_name,
                        "pdf_url": f"http://localhost:8000/document/file/{request.doc_id}.pdf#page={page_str}" if request.doc_id else "",
                        "anchor": f"page-{page_str}",
                    })

            # Build prompt and run LLM
            rt = rtype
            has_media = rt in ("figure", "chart", "table")
            # Confidence: exact figure/table match >= 85%, higher with more evidence
            routed_conf = calculate_confidence("None", support_count=max(len(supporting), 3), has_media=has_media)
            if routed_conf < 0.85:
                routed_conf = min(0.85 + 0.02 * len(supporting), 0.98)

            if supporting:
                prompt = build_prompt(
                    query=request.query,
                    supporting=supporting,
                    exceptions=[], contradictions=[], risks=[],
                    overall_risk_level="None",
                    cross_doc=request.cross_doc,
                )
                answer = chat(
                    prompt["user"],
                    system=prompt["system"],
                    factual=prompt.get("factual", False),
                )
            else:
                answer = ""

            return {
                "query": request.query,
                "routed": True,
                "routed_type": rt,
                "routed_number": rnum,
                "figure": fig_data if rt in ("figure", "chart") else None,
                "table": fig_data if rt == "table" else None,
                "answer": answer,
                "nearby_text": nearby_text,
                "confidence_score": routed_conf,
                "risk_level": "None",
                "evidence": {
                    "supporting": supporting,
                    "exceptions": [], "contradictions": [], "risks": [],
                },
                "documents_used": [request.doc_id] if request.doc_id else [],
            }

        # ── Step 1+2: Adaptive hybrid retrieval (shared connection) ────
        all_candidates = retrieve_candidates(
            request.query,
            doc_id=request.doc_id,
            cross_doc=request.cross_doc,
        )

        # Pre-compute seed_ids for parallel graph expansion
        _seed_ids_pre = [
            n.get("node_id") for n in all_candidates
            if n.get("node_id") and n.get("node_id") in kg.graph.nodes
        ]

        # ── Step 3+4+5: Rerank + graph expansion in parallel ───────────
        loop = asyncio.get_event_loop()
        reranked_fut = loop.run_in_executor(_query_pool, rerank, request.query, all_candidates)
        pos_fut = loop.run_in_executor(_query_pool, pos_expander.expand, _seed_ids_pre, kg)
        neg_fut = loop.run_in_executor(_query_pool, neg_expander.expand, _seed_ids_pre, kg)
        reranked, pos_result, neg_result = await asyncio.gather(reranked_fut, pos_fut, neg_fut)

        # ── Step 4: Noise Removal ───────────────────────────────────────
        def _is_noise(node: dict) -> bool:
            content = str(node.get("content", "")).strip().lower()
            ntype = str(node.get("type", "") or "").lower()
            # Reference/bibliography/acknowledgement headings
            if ntype == "heading" and any(w in content for w in
                ["reference", "bibliography", "acknowledgement", "acknowledgment"]):
                return True
            # Citation-heavy content (reference list entries)
            citation_count = len(re.findall(r'\[\d+\]', content))
            if citation_count >= 5 and ntype != "table":
                return True
            # Very short non-image content
            if len(content) < 30 and ntype not in ("image", "figure"):
                return True
            # Content that is only whitespace/punctuation
            if content and all(c in " \t\n\r.,;:!?-" for c in content):
                return True
            return False

        filtered = [n for n in reranked if not _is_noise(n)]

        # ── Step 5: Context Filtering — keep only relevant ──────────────
        SCORE_THRESHOLD = 0.05
        quality = [n for n in filtered if n.get("_rerank_score", 0) >= SCORE_THRESHOLD]
        if not quality:
            quality = filtered[:5]  # fallback: keep top 5 if all scores are low

        # ── Step 6: Dedup by content hash ───────────────────────────────
        seen_hashes: set = set()
        deduped: list[dict] = []
        for n in quality:
            content = str(n.get("content", "")).strip()
            chash = hash(content) if content else 0
            if chash and chash in seen_hashes:
                continue
            if chash:
                seen_hashes.add(chash)
            deduped.append(n)
        filtered = deduped

        # pos_result and neg_result already computed in parallel above
        # Re-use _seed_ids_pre; pos/neg results are already available

        # ── Enrich evidence with View PDF data + media for display ─────
        enriched_supporting = []
        media_candidates = list(filtered) + pos_result.get("evidence", [])
        seen_in_pool = {id(n) for n in media_candidates}
        for n in all_candidates:
            if id(n) not in seen_in_pool:
                ntype = str(n.get("type", "")).lower()
                if ntype in ("image", "figure", "chart", "caption", "table"):
                    media_candidates.append(n)
                    seen_in_pool.add(id(n))

        for node in media_candidates:
            ndoc_id = node.get("doc_id", "") or (request.doc_id if not request.cross_doc else "")
            npage = node.get("page", 1)
            doc_insight = _DOCUMENT_INSIGHTS.get(ndoc_id, {})
            doc_name = doc_insight.get("document_name", ndoc_id) if doc_insight else ndoc_id

            node["document_id"] = ndoc_id
            node["document_name"] = doc_name
            node["page"] = npage
            node["pdf_url"] = f"http://localhost:8000/document/file/{ndoc_id}.pdf#page={npage}" if ndoc_id else ""

            ntype = str(node.get("type", "")).lower()
            fn = str(node.get("figure_number", "") or node.get("metadata", {}).get("figure_number", "") or "")
            tn = str(node.get("table_number", "") or node.get("metadata", {}).get("table_number", "") or "")
            if ntype in ("image", "figure", "chart") and fn:
                node["anchor"] = f"fig-{fn}"
            elif ntype == "table" and tn:
                node["anchor"] = f"tbl-{tn}"
            else:
                node["anchor"] = f"page-{npage}"

            # Media for evidence panel display (NOT for LLM)
            if ntype in ("image", "figure", "chart") and ndoc_id:
                fig = _find_figure(ndoc_id, fn) if fn else None
                if not fig:
                    for img in doc_insight.get("images", []):
                        if int(img.get("page", 1)) == int(npage):
                            fig = img
                            break
                if not fig:
                    all_imgs = doc_insight.get("images", [])
                    if all_imgs:
                        fig = all_imgs[0]
                if fig and fig.get("image_data"):
                    node["image_data"] = fig["image_data"]
                    node["vision_summary"] = fig.get("vision_summary", "")
                    node["figure_number"] = fig.get("figure_number", fn)
                    node["caption"] = fig.get("caption", node.get("caption", ""))
            if ntype == "table" and ndoc_id:
                tbl = _find_table(ndoc_id, tn) if tn else None
                if not tbl:
                    for t in doc_insight.get("tables", []):
                        if int(t.get("page", 1)) == int(npage):
                            tbl = t
                            break
                if tbl:
                    node["headers"] = tbl.get("headers", [])
                    node["rows"] = tbl.get("rows", [])
                    node["table_number"] = tbl.get("table_number", tn)
                    node["caption"] = tbl.get("caption", node.get("caption", ""))
                    node["table_markdown"] = tbl.get("markdown", "")
            enriched_supporting.append(node)

        # Inject figure nodes for caption-only references (display only)
        seen_fig_nums = set()
        for node in list(enriched_supporting):
            ntype = str(node.get("type", "")).lower()
            fn = str(node.get("figure_number", "") or node.get("metadata", {}).get("figure_number", "") or "")
            if ntype in ("caption", "heading") and fn and fn not in seen_fig_nums:
                seen_fig_nums.add(fn)
                ndoc_id = node.get("doc_id", "") or (request.doc_id if not request.cross_doc else "")
                ndoc_name = _DOCUMENT_INSIGHTS.get(ndoc_id, {}).get("document_name", ndoc_id) if ndoc_id else ndoc_id
                np = node.get("page", 1)
                fig = _find_figure(ndoc_id, fn)
                if fig and fig.get("image_data"):
                    enriched_supporting.insert(0, {
                        "node_id": f"figure_{fn}",
                        "type": "figure",
                        "page": np,
                        "content": fig.get("caption", "") or fig.get("vision_summary", "") or "",
                        "document_id": ndoc_id,
                        "document_name": ndoc_name,
                        "pdf_url": f"http://localhost:8000/document/file/{ndoc_id}.pdf#page={np}" if ndoc_id else "",
                        "anchor": f"fig-{fn}",
                        "image_data": fig.get("image_data", ""),
                        "vision_summary": fig.get("vision_summary", ""),
                        "figure_number": fn,
                        "caption": fig.get("caption", ""),
                    })

        # Dedup enriched supporting (injections may add duplicates)
        seen_combined: set = set()
        final_supporting: list[dict] = []
        for n in enriched_supporting:
            key = (n.get("node_id", ""), n.get("document_id", ""), n.get("page", ""))
            if key not in seen_combined:
                seen_combined.add(key)
                final_supporting.append(n)
        enriched_supporting = final_supporting

        # ── Compute confidence (retrieval quality only, no node count) ──
        rerank_scores = [n.get("_rerank_score", 0) for n in filtered if n.get("_rerank_score") is not None]
        avg_rerank = sum(rerank_scores) / len(rerank_scores) if rerank_scores else 0.0
        retrieval_scores = [n.get("score", 0.5) for n in filtered if isinstance(n.get("score"), (int, float))]
        avg_retrieval = sum(retrieval_scores) / len(retrieval_scores) if retrieval_scores else 0.0

        # Evidence consistency: agreement between reranker and retrieval scores
        # Low variance means high consistency
        if rerank_scores and retrieval_scores and len(rerank_scores) == len(retrieval_scores):
            diffs = [abs(r - s) for r, s in zip(rerank_scores, retrieval_scores)]
            evidence_consistency = 1.0 - min(sum(diffs) / len(diffs), 1.0)
        else:
            evidence_consistency = 0.5

        # Formula: 0.5 * reranker + 0.3 * retrieval + 0.2 * consistency
        confidence = 0.5 * avg_rerank + 0.3 * avg_retrieval + 0.2 * evidence_consistency

        # Cap based on evidence quality (never use node count)
        if not filtered:
            confidence = min(confidence, 0.35)
        elif avg_rerank < 0.1:
            confidence = min(confidence, 0.60)

        overall_risk = "None"
        if neg_result.get("contradictions") or neg_result.get("risks"):
            risk_result = score_nodes(neg_result.get("contradictions", []) + neg_result.get("risks", []))
            overall_risk = risk_result.get("overall_risk_level", "None")

        # Clamp
        confidence = max(0.10, min(confidence, 0.97))

        # ── Build prompt from reranked evidence only ────────────────────
        prompt = build_prompt(
            query=request.query,
            supporting=filtered,
            exceptions=neg_result.get("exceptions", []),
            contradictions=neg_result.get("contradictions", []),
            risks=neg_result.get("risks", []),
            overall_risk_level=overall_risk,
            cross_doc=request.cross_doc,
        )
        answer = chat(
            prompt["user"],
            system=prompt["system"],
            factual=prompt.get("factual", False),
        )

        evidence_for_verify = list(filtered)
        for bucket in ("exceptions", "contradictions", "risks", "warnings", "limitations", "qualifications"):
            evidence_for_verify.extend(neg_result.get(bucket, []))

        # Skip fact verifier for narrative answers (no numbers) — saves ~50-80ms
        if re.search(r'\d', answer):
            fact_lock = verify_answer(answer, evidence_for_verify)
        else:
            fact_lock = {"status": "narrative", "score": 1.0, "total_claims": 0, "verified_count": 0, "verified": [], "unverified": []}
        risk_radar = build_risk_radar(filtered, neg_result, kg)

        return {
            "query": request.query,
            "cross_doc": request.cross_doc,
            "answer": answer,
            "confidence_score": round(confidence, 4),
            "fact_lock": fact_lock,
            "risk_radar": risk_radar,
            "evidence": {
                "supporting":     enriched_supporting,
                "exceptions":     neg_result.get("exceptions", []),
                "contradictions": neg_result.get("contradictions", []),
                "risks":          neg_result.get("risks", []),
                "warnings":       neg_result.get("warnings", []),
                "limitations":    neg_result.get("limitations", []),
            },
            "risk_level": overall_risk,
            "documents_used": [request.doc_id] if request.doc_id else [],
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query/stream")
async def query_pipeline_stream(request: QueryRequest):
    """Streaming version of /query — returns SSE tokens as they arrive from Groq."""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    try:
        all_candidates = retrieve_candidates(
            request.query, doc_id=request.doc_id, cross_doc=request.cross_doc,
        )
        _seed_ids = [
            n.get("node_id") for n in all_candidates
            if n.get("node_id") and n.get("node_id") in kg.graph.nodes
        ]
        loop = asyncio.get_event_loop()
        reranked_fut = loop.run_in_executor(_query_pool, rerank, request.query, all_candidates)
        neg_fut = loop.run_in_executor(_query_pool, neg_expander.expand, _seed_ids, kg)
        reranked, neg_result = await asyncio.gather(reranked_fut, neg_fut)

        filtered = [n for n in reranked if len(str(n.get("content", "")).strip()) >= 30]
        filtered = filtered or reranked[:5]

        overall_risk = "None"
        if neg_result.get("contradictions") or neg_result.get("risks"):
            from generation.risk_detector import score_nodes
            risk_result = score_nodes(neg_result.get("contradictions", []) + neg_result.get("risks", []))
            overall_risk = risk_result.get("overall_risk_level", "None")

        prompt = build_prompt(
            query=request.query,
            supporting=filtered,
            exceptions=neg_result.get("exceptions", []),
            contradictions=neg_result.get("contradictions", []),
            risks=neg_result.get("risks", []),
            overall_risk_level=overall_risk,
            cross_doc=request.cross_doc,
        )

        def _sse_generator():
            try:
                for token in chat_stream(prompt["user"], system=prompt["system"], factual=prompt.get("factual", False)):
                    yield f"data: {json.dumps({'token': token})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(_sse_generator(), media_type="text/event-stream")

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ── Document insights endpoints ──────────────────────────────────────────────

@app.get("/document/{doc_id}/insights")
async def get_document_insights(doc_id: str):
    insight = _DOCUMENT_INSIGHTS.get(doc_id)
    if not insight:
        raise HTTPException(status_code=404, detail=f"No insights found for doc_id '{doc_id}'. Ingest the document first.")
    return insight


@app.get("/document/{doc_id}/mindmap")
async def get_document_mindmap(doc_id: str):
    insight = _DOCUMENT_INSIGHTS.get(doc_id)
    if not insight:
        raise HTTPException(status_code=404, detail=f"No mind map for '{doc_id}'. Ingest the document first.")
    mindmap = insight.get("mindmap")
    if not mindmap:
        raise HTTPException(status_code=404, detail=f"Mind map not built for '{doc_id}'.")
    return mindmap


@app.get("/document/{doc_id}/figure/{figure_number}")
async def get_figure(doc_id: str, figure_number: str):
    fig = _find_figure(doc_id, figure_number)
    if not fig:
        raise HTTPException(status_code=404, detail=f"Figure {figure_number} not found in doc_id '{doc_id}'.")
    return fig


@app.get("/document/{doc_id}/table/{table_number}")
async def get_table(doc_id: str, table_number: str):
    tbl = _find_table(doc_id, table_number)
    if not tbl:
        raise HTTPException(status_code=404, detail=f"Table {table_number} not found in doc_id '{doc_id}'.")
    return tbl


# ── Graph endpoints ──────────────────────────────────────────────────────────

@app.get("/graph", response_class=HTMLResponse)
async def get_graph():
    if kg.node_count == 0:
        return HTMLResponse(content="""
        <html><body style='background:#0f172a;color:#94a3b8;font-family:Inter,sans-serif;
        display:flex;align-items:center;justify-content:center;height:100vh;margin:0;'>
        <div style='text-align:center'>
            <div style='font-size:3rem'>🕸️</div>
            <h2 style='color:#818cf8'>No graph data yet</h2>
            <p>Ingest a document first to build the knowledge graph.</p>
        </div></body></html>""")

    output_path = os.path.join("data", "graph_interactive.html")
    visualizer.generate_interactive(kg, output_path=output_path)
    with open(output_path, "r", encoding="utf-8") as f:
        html = f.read()

    utils_path = os.path.join("lib", "bindings", "utils.js")
    if os.path.exists(utils_path):
        with open(utils_path, "r", encoding="utf-8") as f:
            utils_js = f.read()
        html = html.replace('<script src="lib/bindings/utils.js"></script>', f'<script>{utils_js}</script>')

    return HTMLResponse(content=html)


@app.get("/graph/data")
async def get_graph_data():
    if kg.node_count == 0:
        return {"nodes": [], "edges": []}
    return kg.export_graph()


@app.get("/graph/stats")
async def get_graph_stats():
    return kg.get_stats()


@app.post("/reset")
async def reset_collection():
    try:
        from vectorstore.weaviate_client import DocuMindWeaviateClient
        db = DocuMindWeaviateClient()
        db.clear_collection()
        db.close()
        kg.__init__()
        _DOCUMENT_INSIGHTS.clear()
        return {"status": "reset", "message": "Weaviate collection cleared, graph reset, insights cleared. Please re-ingest your documents."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reindex")
async def reindex_negative_edges():
    if kg.node_count == 0:
        raise HTTPException(status_code=400, detail="No graph loaded. Ingest a document first.")
    edges = neg_expander.detect_negative_edges(kg)
    return {
        "status": "reindexed",
        "negative_edges_created": len(edges),
        "graph_nodes": kg.node_count,
        "graph_edges": kg.edge_count,
    }


@app.get("/document/file/{filename}")
async def get_document_file(filename: str):
    file_path = os.path.join(Config.UPLOADS_DIR, filename)
    if not os.path.exists(file_path):
        file_path = os.path.join(Config.UPLOADS_DIR, f"{filename}.pdf")
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(file_path, content_disposition_type="inline")


@app.delete("/document/{filename}")
async def delete_document(filename: str):
    file_path = os.path.join(Config.UPLOADS_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")
    os.remove(file_path)
    doc_id = os.path.splitext(filename)[0]
    _DOCUMENT_INSIGHTS.pop(doc_id, None)
    return {"filename": filename, "status": "deleted"}


@app.get("/demo/questions")
async def demo_questions(doc_id: str | None = None):
    """Demo questions generated at ingest for the given document."""
    if not doc_id:
        return {"questions": [], "doc_id": None, "status": "empty"}
    insight = _DOCUMENT_INSIGHTS.get(doc_id, {})
    questions = get_demo_questions(doc_id, _DOCUMENT_INSIGHTS)
    status = insight.get("demo_questions_status", "ready" if questions else "empty")
    if not questions and status not in ("generating", "failed"):
        if insight:
            _generate_demo_questions_async(doc_id, insight)
            status = "generating"
    return {"questions": questions, "doc_id": doc_id, "status": status}


@app.get("/documents")
async def list_documents():
    return {"documents": list(_DOCUMENT_INSIGHTS.keys())}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
