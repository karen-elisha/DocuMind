from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from langchain.embeddings.base import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings

from config import Config
from vectorstore.weaviate_client import DocuMindWeaviateClient


# ---- Timer ----

class Timer:
    """Simple context manager for timing code blocks."""
    def __init__(self, name: str):
        self.name = name
        self.elapsed = 0.0

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.elapsed = time.perf_counter() - self.start
        print(f"[Timer] {self.name}: {self.elapsed:.2f}s")


# ---- Node/chunk data model ----

SUPPORTED_NODE_TYPES = {"heading", "paragraph", "table", "image", "caption", "footnote", "list_item", "formula"}


@dataclass
class Node:
    node_id: str
    doc_id: str
    page: int
    type: str
    content: str
    metadata: Dict[str, Any]
    section: str = ""
    embedding: Sequence[float] = ()


def _node_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _safe_int(x: Any, default: int = 1) -> int:
    try:
        return int(x)
    except Exception:
        return default


# ---- Singleton embeddings ----

_embeddings_instance = None


def _get_embeddings(model_name: str) -> HuggingFaceEmbeddings:
    global _embeddings_instance
    if _embeddings_instance is None:
        print(f"[Embeddings] Loading model: {model_name}")
        t0 = time.perf_counter()
        _embeddings_instance = HuggingFaceEmbeddings(model_name=model_name)
        print(f"[Embeddings] Model loaded in {time.perf_counter()-t0:.2f}s")
    return _embeddings_instance


# ---- Node building ----

def build_nodes(
    parse_result: Dict[str, Any],
    vision_results: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Convert extracted elements into normalized nodes.

    Image nodes contain Groq-generated summaries (vision_results).
    """
    doc_id = parse_result.get("doc_id")
    document_name = parse_result.get("document_name")
    elements = parse_result.get("elements", [])
    images = parse_result.get("images", [])

    vision_results = vision_results or {}

    nodes: List[Node] = []

    image_summaries_by_path: Dict[str, str] = {}
    for k, v in vision_results.items():
        if isinstance(v, dict) and v.get("image_path"):
            image_summaries_by_path[v["image_path"]] = v.get("vision_summary", "")

    for el in elements:
        el_type = el.get("type")
        if el_type not in SUPPORTED_NODE_TYPES:
            continue
        page = _safe_int(el.get("page"), 1)
        content = el.get("content") or ""
        metadata = dict(el.get("metadata") or {})

        node = Node(
            node_id=_node_id(el_type),
            doc_id=doc_id,
            page=page,
            type=el_type,
            content=content.strip(),
            metadata=metadata,
        )

        if el_type == "image":
            summary = ""
            for v in vision_results.values():
                if int(v.get("page") or 1) == page and v.get("vision_summary"):
                    summary = v["vision_summary"]
                    break
            node.content = summary.strip() if summary else ""
            node.metadata["image_vision_available"] = bool(summary)

        if el_type == "caption":
            node.metadata.setdefault("links_to_image", True)

        nodes.append(node)

    for idx, img in enumerate(images or []):
        img_path = img.get("image_path")
        page = _safe_int(img.get("page"), 1)
        summary = image_summaries_by_path.get(img_path, "")
        if not any(n.type == "image" and n.page == page and (n.metadata.get("image_path") == img_path) for n in nodes):
            nodes.append(
                Node(
                    node_id=_node_id("image"),
                    doc_id=doc_id,
                    page=page,
                    type="image",
                    content=(summary or "").strip(),
                    metadata={
                        "image_path": img_path,
                        "source": "docling_export_to_images",
                        "vision_summary_available": bool(summary),
                    },
                )
            )

    node_payloads = [
        {
            "node_id": n.node_id,
            "doc_id": n.doc_id,
            "page": n.page,
            "type": n.type,
            "content": n.content,
            "metadata": n.metadata,
        }
        for n in nodes
    ]

    return {
        "doc_id": doc_id,
        "document_name": document_name,
        "node_count": len(nodes),
        "nodes": node_payloads,
    }


# ---- Chunking ----

def chunk_nodes(
    node_build: Dict[str, Any],
    *,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> Dict[str, Any]:
    if chunk_size is None:
        chunk_size = int(getattr(Config, "CHUNK_SIZE", 1200))
    if chunk_overlap is None:
        chunk_overlap = int(getattr(Config, "CHUNK_OVERLAP", 150))

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""],
    )

    nodes = node_build.get("nodes", [])
    chunks: List[Dict[str, Any]] = []

    for node in nodes:
        ntype = node.get("type")
        content = node.get("content") or ""
        content = content.strip()

        if not content:
            continue

        base_metadata = dict(node.get("metadata") or {})
        base_metadata.update(
            {
                "node_id": node.get("node_id"),
                "node_type": ntype,
                "doc_id": node.get("doc_id"),
                "page": node.get("page"),
            }
        )

        if ntype == "table":
            if len(content) <= (chunk_size + chunk_overlap):
                chunks.append(
                    {
                        "chunk_id": _node_id("chunk"),
                        "node_id": node.get("node_id"),
                        "doc_id": node.get("doc_id"),
                        "page": node.get("page"),
                        "type": ntype,
                        "content": content,
                        "metadata": base_metadata,
                    }
                )
            else:
                lines = content.splitlines()
                buf = []
                for line in lines:
                    if sum(len(x) for x in buf) > chunk_size:
                        chunk_content = "\n".join(buf).strip()
                        if chunk_content:
                            chunks.append(
                                {
                                    "chunk_id": _node_id("chunk"),
                                    "node_id": node.get("node_id"),
                                    "doc_id": node.get("doc_id"),
                                    "page": node.get("page"),
                                    "type": ntype,
                                    "content": chunk_content,
                                    "metadata": base_metadata,
                                }
                            )
                        buf = [line]
                    else:
                        buf.append(line)
                if buf:
                    chunk_content = "\n".join(buf).strip()
                    if chunk_content:
                        chunks.append(
                            {
                                "chunk_id": _node_id("chunk"),
                                "node_id": node.get("node_id"),
                                "doc_id": node.get("doc_id"),
                                "page": node.get("page"),
                                "type": ntype,
                                "content": chunk_content,
                                "metadata": base_metadata,
                            }
                        )
            continue

        split_docs = splitter.create_documents([content], metadatas=[base_metadata])
        for doc in split_docs:
            chunks.append(
                {
                    "chunk_id": _node_id("chunk"),
                    "node_id": node.get("node_id"),
                    "doc_id": node.get("doc_id"),
                    "page": node.get("page"),
                    "type": ntype,
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                }
            )

    return {
        "doc_id": node_build.get("doc_id"),
        "document_name": node_build.get("document_name"),
        "node_count": node_build.get("node_count", 0),
        "chunks": chunks,
        "chunks_created": len(chunks),
    }


# ---- Embeddings (batched) ----

def embed_chunks(
    chunked: Dict[str, Any],
    *,
    embedding_model_name: Optional[str] = None,
) -> Dict[str, Any]:
    if embedding_model_name is None:
        embedding_model_name = getattr(
            Config, "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
    chunks = chunked.get("chunks", [])
    if not chunks:
        return {**chunked, "embedded": True}

    embeddings = _get_embeddings(embedding_model_name)

    texts = [c["content"] for c in chunks]
    vectors = embeddings.embed_documents(texts)

    for i, c in enumerate(chunks):
        c["embedding"] = vectors[i] if i < len(vectors) else []

    return {
        **chunked,
        "embedded": True,
    }


# ---- Weaviate storage ----

def store_chunks_weaviate(
    chunked_embedded: Dict[str, Any],
    *,
    collection_name: Optional[str] = None,
) -> Dict[str, Any]:
    if collection_name is None:
        collection_name = getattr(Config, "WEAVIATE_COLLECTION", "DocuMindNode")
    chunks = chunked_embedded.get("chunks", [])
    weaviate = DocuMindWeaviateClient(collection_name=collection_name)
    weaviate.upsert_nodes(chunks)
    return {"stored": True, "count": len(chunks)}


# ---- Performance summary ----

def _print_summary(
    timings: Dict[str, float],
    stats: Dict[str, int],
) -> None:
    total = sum(timings.values())
    print()
    print("=" * 50)
    print("  PERFORMANCE SUMMARY")
    print("=" * 50)
    for name, sec in timings.items():
        pct = (sec / total * 100) if total > 0 else 0
        print(f"  {name:22s}  {sec:.2f}s  ({pct:5.1f}%)")
    print(f"  {'─' * 35}")
    print(f"  {'Total':22s}  {total:.2f}s  (100%)")
    print()
    parts = [f"{k}={v}" for k, v in stats.items() if v is not None]
    print(f"  {' | '.join(parts)}")
    print("=" * 50)
    print()


# ---- Pipeline orchestrator ----

def run_ingestion_pipeline(
    parse_result: Dict[str, Any],
    vision_results: Optional[Dict[str, Dict[str, Any]]],
    *,
    weaviate_collection: Optional[str] = None,
    enable_vision: Optional[bool] = None,
    enable_embeddings: Optional[bool] = None,
    enable_weaviate: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Pipeline: Node building → chunking → embeddings → Weaviate storage.

    Respects feature flags from Config or explicit keyword overrides.
    """
    if enable_vision is None:
        enable_vision = getattr(Config, "ENABLE_VISION", False)
    if enable_embeddings is None:
        enable_embeddings = getattr(Config, "ENABLE_EMBEDDINGS", False)
    if enable_weaviate is None:
        enable_weaviate = getattr(Config, "ENABLE_WEAVIATE", False)
    if weaviate_collection is None:
        weaviate_collection = getattr(Config, "WEAVIATE_COLLECTION", "DocuMindNode")

    if not enable_vision:
        vision_results = {}

    timings: Dict[str, float] = {}

    with Timer("Node Building") as t:
        node_build = build_nodes(parse_result=parse_result, vision_results=vision_results)
    timings["node_building"] = t.elapsed

    with Timer("Chunking") as t:
        chunked = chunk_nodes(node_build)
    timings["chunking"] = t.elapsed

    stored = {"stored": False, "count": 0}
    if enable_embeddings:
        with Timer("Embeddings") as t:
            embedded = embed_chunks(chunked)
        timings["embeddings"] = t.elapsed
    else:
        embedded = chunked
        timings["embeddings"] = 0.0

    if enable_weaviate:
        with Timer("Weaviate Storage") as t:
            stored = store_chunks_weaviate(embedded, collection_name=weaviate_collection)
        timings["weaviate"] = t.elapsed
    else:
        timings["weaviate"] = 0.0

    stats = {
        "Pages": parse_result.get("pages_processed"),
        "Elements": len(parse_result.get("elements", [])),
        "Nodes": node_build.get("node_count"),
        "Chunks": chunked.get("chunks_created"),
        "Embeddings": len(embedded.get("chunks", [])) if enable_embeddings else 0,
        "Stored": stored["count"],
    }

    _print_summary(timings, stats)

    return {
        "document_name": parse_result.get("document_name"),
        "pages_processed": parse_result.get("pages_processed"),
        "node_count": node_build.get("node_count"),
        "image_count": len(parse_result.get("images", []) or []),
        "chunks_created": chunked.get("chunks_created"),
        "weaviate_stored": stored,
    }
