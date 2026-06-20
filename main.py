import os
import shutil
from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from config import Config
from ingestion.parser import parse_document
from ingestion.vision_processor import summarize_images
from ingestion.node_builder import run_ingestion_pipeline
from graph.graph_engine import KnowledgeGraph
from graph.positive_expansion import PositiveExpander
from graph.negative_expansion import NegativeExpander
from retrieval.hybrid_search import HybridRetriever
from retrieval.evidence_fusion import fuse_evidence
from generation.prompt_builder import build_prompt_from_fusion
from generation.risk_detector import score_nodes, confidence_from_risk, score_text
from generation.groq_client import chat
from visualization.graph_snapshot import GraphVisualizer

# Shared in-memory instances
kg = KnowledgeGraph()
visualizer = GraphVisualizer()
pos_expander = PositiveExpander()
neg_expander = NegativeExpander()

Config.validate()
os.makedirs(Config.UPLOADS_DIR, exist_ok=True)
os.makedirs(Config.PROCESSED_DIR, exist_ok=True)

app = FastAPI(
    title="DocuMind Graph API",
    description="Agentic KG-RAG with Negative Graph Expansion",
    version="2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

VALID_GRAPH_TYPES = {"heading", "paragraph", "table", "image", "figure", "caption", "footnote", "chart"}


class QueryRequest(BaseModel):
    query: str
    cross_doc: bool = False


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
        # 1. Parse
        parse_result = parse_document(file_path=file_path, doc_id=doc_id)

        # 2. Vision (optional)
        vision_results = {}
        if Config.ENABLE_VISION:
            vision_results = summarize_images(parse_result.get("images", []) or [])

        # 3. Nodes + embeddings + Weaviate
        stats = run_ingestion_pipeline(parse_result=parse_result, vision_results=vision_results)

        # 4. Build knowledge graph synchronously in the same process
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

        if nodes_for_graph:
            kg.build_from_nodes(nodes_for_graph)
            neg_expander.detect_negative_edges(kg)
            print(f"[Graph] ✅ Built {kg.node_count} nodes, {kg.edge_count} edges for doc_id={doc_id}")

        return {
            "filename": file.filename,
            "doc_id": doc_id,
            "status": "success",
            "message": f"Ingested. Graph: {kg.node_count} nodes, {kg.edge_count} edges.",
            "graph_nodes": kg.node_count,
            "graph_edges": kg.edge_count,
            "stats": stats,
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
        # 1. Hybrid search
        retriever = HybridRetriever()
        hybrid_results = retriever.retrieve(query=request.query, cross_doc=request.cross_doc)

        # Deduplicate by node_id
        seen: set = set()
        all_results = []
        for n in hybrid_results.get("semantic_results", []) + hybrid_results.get("keyword_results", []):
            nid = n.get("node_id")
            if nid and nid not in seen:
                seen.add(nid)
                all_results.append(n)
        hybrid_results["semantic_results"] = all_results
        hybrid_results["keyword_results"] = []

        # 2. Seed IDs present in graph
        seed_ids = [
            n.get("node_id") for n in all_results
            if n.get("node_id") and n.get("node_id") in kg.graph.nodes
        ]

        # 3. Graph expansion
        pos_result = pos_expander.expand(seed_ids, kg) if seed_ids else {"seed_nodes": [], "evidence": [], "stats": {}}
        neg_result = neg_expander.expand(seed_ids, kg) if seed_ids else {
            "exceptions": [], "contradictions": [], "risks": [],
            "warnings": [], "limitations": [], "overall_risk_level": "None", "stats": {}
        }

        # 4. Evidence fusion
        fusion = fuse_evidence(hybrid_results, pos_result, neg_result)

        # 5. Risk + confidence
        exceptions_and_contradictions = (
            fusion.get("exceptions", []) +
            fusion.get("contradictions", []) +
            fusion.get("risks", [])
        )

        # Score risk only on actual negative evidence nodes
        if not fusion.get("supporting") and not exceptions_and_contradictions:
            # No evidence at all — document not ingested or query out of scope
            overall_risk = "None"
        elif exceptions_and_contradictions:
            risk_result = score_nodes(exceptions_and_contradictions)
            overall_risk = risk_result.get("overall_risk_level", "None")
        else:
            # No negative evidence — scan only the top 5 seed nodes, not all 50+
            top_seeds = all_results[:5]
            risk_result = score_nodes(top_seeds)
            overall_risk = risk_result.get("overall_risk_level", "None")
            # Cap at Medium when coming from supporting nodes only
            if overall_risk == "High":
                overall_risk = "Medium"

        confidence = confidence_from_risk(overall_risk)

        # 6. Prompt + generate
        prompt = build_prompt_from_fusion(
            query=request.query,
            fusion_result={"evidence": fusion},
            risk_result={"overall_risk_level": overall_risk},
            cross_doc=request.cross_doc,
        )
        answer = chat(prompt["user"], system=prompt["system"])

        return {
            "query": request.query,
            "cross_doc": request.cross_doc,
            "answer": answer,
            "confidence_score": confidence,
            "evidence": {
                "supporting":     fusion.get("supporting", []),
                "exceptions":     fusion.get("exceptions", []),
                "contradictions": fusion.get("contradictions", []),
                "risks":          fusion.get("risks", []),
                "warnings":       fusion.get("warnings", []),
                "limitations":    fusion.get("limitations", []),
            },
            "risk_level": overall_risk,
            "documents_used": fusion.get("documents_used", []),
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


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


@app.get("/graph/stats")
async def get_graph_stats():
    return kg.get_stats()


@app.post("/reset")
async def reset_collection():
    """Wipe all Weaviate nodes and reset the in-memory graph. Re-ingest documents after this."""
    try:
        from vectorstore.weaviate_client import DocuMindWeaviateClient
        db = DocuMindWeaviateClient()
        db.clear_collection()
        db.close()
        kg.__init__()  # reset in-memory graph
        return {"status": "reset", "message": "Weaviate collection cleared and graph reset. Please re-ingest your documents."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reindex")
async def reindex_negative_edges():
    """Re-run negative edge detection on the existing in-memory graph without re-ingesting."""
    if kg.node_count == 0:
        raise HTTPException(status_code=400, detail="No graph loaded. Ingest a document first.")
    edges = neg_expander.detect_negative_edges(kg)
    return {
        "status": "reindexed",
        "negative_edges_created": len(edges),
        "graph_nodes": kg.node_count,
        "graph_edges": kg.edge_count,
    }


@app.delete("/document/{filename}")
async def delete_document(filename: str):
    file_path = os.path.join(Config.UPLOADS_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")
    os.remove(file_path)
    return {"filename": filename, "status": "deleted"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
