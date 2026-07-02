from __future__ import annotations

import os
import re
import time
import uuid
import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from langchain.embeddings.base import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings

from config import Config
from vectorstore.weaviate_client import DocuMindWeaviateClient
from ingestion.fact_extractor import detect_section_from_text, extract_fact_sentences, is_toc_noise


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

SUPPORTED_NODE_TYPES = {
    "heading", "paragraph", "table", "table_row", "image", "caption",
    "footnote", "list_item", "formula", "fact",
}

MERGEABLE_TYPES = {"paragraph", "list_item"}
MIN_CONTENT_LEN = 80  # merge fragments shorter than this into the next sibling


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


def _stable_chunk_id(doc_id: str, page: int, chunk_type: str, content: str) -> str:
    key = f"{doc_id}:{page}:{chunk_type}:{content[:400]}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _resolve_section(metadata: Dict[str, Any], current_heading: str) -> str:
    meta_sec = str(metadata.get("section") or "").strip()
    inline = detect_section_from_text(str(metadata.get("raw_content") or metadata.get("content") or ""))
    if inline:
        return inline
    if meta_sec and re.search(r"\bItem\s+\d", meta_sec, re.IGNORECASE) and not is_toc_noise(meta_sec):
        return meta_sec
    if current_heading and not re.search(
        r"table of contents|item 15|item 16|signatures|exhibits|available information",
        current_heading,
        re.IGNORECASE,
    ):
        return current_heading
    return meta_sec or current_heading


def _enrich_chunk_content(content: str, metadata: Dict[str, Any], document_name: str = "") -> str:
    """Prepend section/document context so embeddings and BM25 hit declarative facts."""
    section = _resolve_section(metadata, metadata.get("parent_heading") or "")
    if not section or re.search(r"SECURITIES AND EXCHANGE COMMISSION", section, re.IGNORECASE):
        inline = re.match(r"^(Item\s+\d+[A-Z]?\.?\s[^\n.]{0,80})", content.strip(), re.IGNORECASE)
        if inline:
            section = inline.group(1).strip()
        elif re.search(r"\bresearch and development\b", content, re.IGNORECASE):
            section = "Research and Development"
        elif re.search(r"\bBusiness Segments\b", content):
            section = "Business Segments"
        elif re.search(r"\bSelected Financial Data\b", content, re.IGNORECASE):
            section = "Selected Financial Data"
    parts: List[str] = []
    if document_name:
        parts.append(f"[Document: {document_name}]")
    if section:
        parts.append(f"[Section: {section}]")
    college = metadata.get("college_context", "")
    if college:
        parts.append(f"[College: {college}]")
    col_headers = metadata.get("col_headers", "")
    if col_headers:
        parts.append(f"[Columns: {col_headers}]")
    if not parts:
        return content
    return " ".join(parts) + "\n" + content


def _make_chunk(
    *,
    doc_id: str,
    document_name: str,
    page: int,
    chunk_type: str,
    content: str,
    metadata: Dict[str, Any],
    source_node_id: str,
) -> Dict[str, Any]:
    section = _resolve_section(metadata, metadata.get("parent_heading") or "")
    enriched = _enrich_chunk_content(content, {**metadata, "parent_heading": section}, document_name)
    chunk_id = _stable_chunk_id(doc_id, page, chunk_type, content)
    return {
        "chunk_id": chunk_id,
        "node_id": chunk_id,
        "doc_id": doc_id,
        "page": page,
        "type": chunk_type,
        "section": section,
        "content": enriched,
        "metadata": {**metadata, "raw_content": content, "section": section},
    }


def _safe_int(x: Any, default: int = 1) -> int:
    try:
        return int(x)
    except Exception:
        return default


def _merge_short_nodes(nodes: List[Node]) -> List[Node]:
    """
    Merge consecutive short fragments on the same page into a single node.
    For cutoff-sheet docs: merges split course name paragraphs + their rank footnote
    into one node: 'COMPUTER SCIENCE AND ENGINEERING | 514 -- 1088 985 ...'
    """
    if not nodes:
        return nodes

    merged: List[Node] = []
    i = 0
    while i < len(nodes):
        node = nodes[i]

        if node.type not in MERGEABLE_TYPES or len(node.content) >= MIN_CONTENT_LEN:
            merged.append(node)
            i += 1
            continue

        # Accumulate consecutive short siblings on the same page (any mergeable type)
        parts = [node.content]
        j = i + 1
        while j < len(nodes):
            nxt = nodes[j]
            same_page = nxt.page == node.page and nxt.doc_id == node.doc_id
            if not same_page:
                break
            # Pull in more short paragraphs
            if nxt.type in MERGEABLE_TYPES and len(" ".join(parts)) < MIN_CONTENT_LEN:
                parts.append(nxt.content)
                j += 1
            # Pull in the immediately following footnote (rank numbers)
            elif nxt.type == "footnote" and len(" ".join(parts)) < MIN_CONTENT_LEN * 3:
                parts.append(nxt.content)
                j += 1
                break  # one footnote per course row
            else:
                break

        combined = " | ".join(p.strip() for p in parts if p.strip())
        merged.append(Node(
            node_id=node.node_id,
            doc_id=node.doc_id,
            page=node.page,
            type=node.type,
            content=combined,
            metadata=node.metadata,
            section=node.section,
        ))
        i = j

    return merged


# ---- Singleton embeddings ----

_embeddings_instance = None


def _get_embeddings(model_name: str) -> HuggingFaceEmbeddings | None:
    global _embeddings_instance
    if _embeddings_instance is None:
        print(f"[Embeddings] Loading model: {model_name}")
        t0 = time.perf_counter()
        try:
            _embeddings_instance = HuggingFaceEmbeddings(model_name=model_name)
            print(f"[Embeddings] Model loaded in {time.perf_counter()-t0:.2f}s")
        except Exception as exc:
            print(f"[Embeddings] FAILED to load model: {exc}")
            print("[Embeddings] Continuing without local embeddings. Weaviate will use its own vectorizer or keyword search.")
            _embeddings_instance = None  # sentinel so we don't retry
    return _embeddings_instance


# ---- Node building ----

def build_nodes(
    parse_result: Dict[str, Any],
    vision_results: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
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

    # Detect college-context documents (e.g. KCET cutoff sheets)
    # Pattern: paragraph starting with "College: EXXX <name>"
    _COLLEGE_RE = re.compile(r'^College\s*:\s*(\S+\s+.{5,})', re.IGNORECASE)
    _HEADER_RE = re.compile(r'^Course\s*Name\s+(1G|GM|SCG)', re.IGNORECASE)
    current_college: str = ""
    current_col_headers: str = ""

    for el in elements:
        el_type = el.get("type")
        if el_type not in SUPPORTED_NODE_TYPES:
            continue
        page = _safe_int(el.get("page"), 1)
        content = el.get("content") or ""
        metadata = dict(el.get("metadata") or {})

        if el_type != "image" and not content.strip():
            continue

        # Track current college context
        if el_type == "paragraph":
            m = _COLLEGE_RE.match(content.strip())
            if m:
                current_college = content.strip()
                current_col_headers = ""  # reset headers for new college
            elif _HEADER_RE.match(content.strip()):
                current_col_headers = content.strip()

        if current_college:
            metadata["college_context"] = current_college
        if current_col_headers:
            metadata["col_headers"] = current_col_headers

        node = Node(
            node_id=el.get("element_id") or _node_id(el_type),
            doc_id=doc_id,
            page=page,
            type=el_type,
            content=content.strip(),
            metadata=metadata,
            section=str(metadata.get("section") or ""),
        )

        if el_type == "image":
            summary = ""
            fig_num = metadata.get("figure_number", "")
            fig_cap = metadata.get("figure_caption", "") or metadata.get("caption", "")
            for v in vision_results.values():
                if int(v.get("page") or 1) == page and v.get("vision_summary"):
                    summary = v["vision_summary"]
                    break
            # Build content: prefix with [Figure N] for keyword search, then vision or caption
            prefix = f"[Figure {fig_num}] " if fig_num else ""
            if summary.strip():
                node.content = f"{prefix}{summary.strip()}"
            elif fig_cap:
                node.content = f"{prefix}{fig_cap}"
            else:
                node.content = f"{prefix}image on page {page}".strip() if prefix else f"image on page {page}"
            node.metadata["image_vision_available"] = bool(summary)
            node.metadata["figure_number"] = fig_num
            node.metadata["figure_caption"] = fig_cap

        if el_type == "caption":
            node.metadata.setdefault("links_to_image", True)

        nodes.append(node)

    # Merge short inline fragments (e.g. 'Timeline:' + '24 hours |' + 'Team:' + '4 members')
    nodes = _merge_short_nodes(nodes)

    # Drop anything still too short after merging (except images)
    nodes = [n for n in nodes if n.type == "image" or len(n.content) >= 15]

    for idx, img in enumerate(images or []):
        img_path = img.get("image_path")
        page = _safe_int(img.get("page"), 1)
        summary = image_summaries_by_path.get(img_path, "")
        fig_num = img.get("figure_number", "")
        fig_cap = img.get("caption", "")
        if not any(n.type == "image" and n.page == page and (n.metadata.get("image_path") == img_path) for n in nodes):
            prefix = f"[Figure {fig_num}] " if fig_num else ""
            if summary.strip():
                content = f"{prefix}{summary.strip()}"
            elif fig_cap:
                content = f"{prefix}{fig_cap}"
            else:
                content = f"{prefix}image on page {page}".strip() if prefix else f"image on page {page}"
            nodes.append(
                Node(
                    node_id=_node_id("image"),
                    doc_id=doc_id,
                    page=page,
                    type="image",
                    content=content,
                    metadata={
                        "image_path": img_path,
                        "source": "docling_export_to_images",
                        "vision_summary_available": bool(summary),
                        "figure_number": fig_num,
                        "figure_caption": fig_cap,
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
            "section": n.section or n.metadata.get("section", ""),
        }
        for n in nodes
    ]

    return {
        "doc_id": doc_id,
        "document_name": document_name,
        "node_count": len(nodes),
        "nodes": node_payloads,
    }


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

    nodes = node_build.get("nodes", [])
    document_name = str(node_build.get("document_name") or node_build.get("doc_id") or "")
    doc_id = str(node_build.get("doc_id") or "")
    chunks: List[Dict[str, Any]] = []

    current_heading = ""
    buffer_content = []
    buffer_len = 0
    buffer_nodes = []

    def flush_buffer():
        nonlocal buffer_content, buffer_len, buffer_nodes
        if not buffer_content:
            return
        combined_content = "\n\n".join(buffer_content)
        first_node = buffer_nodes[0]
        first_meta = dict(first_node.get("metadata") or {})
        resolved = _resolve_section(first_meta, current_heading)
        base_metadata = dict(first_meta)
        base_metadata.update({
            "node_id": first_node.get("node_id"),
            "node_type": "text_chunk",
            "doc_id": first_node.get("doc_id"),
            "page": first_node.get("page"),
            "parent_heading": resolved,
            "section": resolved,
        })
        
        # If the combined content is extremely large, use text splitter. Otherwise keep together.
        if len(combined_content) > chunk_size * 1.5:
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size, 
                chunk_overlap=chunk_overlap,
                separators=["\n\n", "\n", ". ", " ", ""]
            )
            docs = splitter.create_documents([combined_content], metadatas=[base_metadata])
            for doc in docs:
                chunks.append(_make_chunk(
                    doc_id=doc_id,
                    document_name=document_name,
                    page=int(first_node.get("page") or 1),
                    chunk_type="text_chunk",
                    content=doc.page_content,
                    metadata=doc.metadata,
                    source_node_id=str(first_node.get("node_id") or ""),
                ))
        else:
            chunks.append(_make_chunk(
                doc_id=doc_id,
                document_name=document_name,
                page=int(first_node.get("page") or 1),
                chunk_type="text_chunk",
                content=combined_content,
                metadata=base_metadata,
                source_node_id=str(first_node.get("node_id") or ""),
            ))
        
        buffer_content = []
        buffer_len = 0
        buffer_nodes = []

    for node in nodes:
        ntype = node.get("type")
        content = node.get("content") or ""
        content = content.strip()

        if not content:
            continue

        base_metadata = dict(node.get("metadata") or {})
        resolved = _resolve_section(base_metadata, current_heading)
        base_metadata.update(
            {
                "node_id": node.get("node_id"),
                "node_type": ntype,
                "doc_id": node.get("doc_id"),
                "page": node.get("page"),
                "parent_heading": resolved,
                "section": resolved,
            }
        )

        if ntype == "heading":
            flush_buffer()
            current_heading = content
            chunks.append(_make_chunk(
                doc_id=doc_id,
                document_name=document_name,
                page=int(node.get("page") or 1),
                chunk_type=ntype,
                content=content,
                metadata=base_metadata,
                source_node_id=str(node.get("node_id") or ""),
            ))
        elif ntype in ("table", "table_row", "image", "formula", "caption", "fact"):
            flush_buffer()
            # Tag table/table_row chunks with row headers and table title
            # so cross-table segment linking works (e.g. "Industrial" across Note 3 + Item 7)
            if ntype in ("table", "table_row"):
                raw_content = content
                headers = base_metadata.get("table_headers") or []
                rows = base_metadata.get("table_rows") or []
                table_title = base_metadata.get("table_caption") or base_metadata.get("table_title") or ""
                table_number = base_metadata.get("table_number") or ""

                # Extract row header labels (first cell of each row)
                row_headers = [str(r[0]).strip() for r in rows if r and str(r[0]).strip()] if rows else []
                # Also pull from header row itself
                if headers:
                    row_headers = list(dict.fromkeys(headers[:1] + row_headers))  # dedupe, preserve order

                # Prepend table title + row headers into content so BM25 + vector both hit segment names
                prefix_parts = []
                if table_title:
                    prefix_parts.append(f"[Table: {table_title}]")
                if table_number:
                    prefix_parts.append(f"[Table Number: {table_number}]")
                if row_headers:
                    prefix_parts.append(f"[Row Headers: {', '.join(row_headers[:20])}]")
                if prefix_parts:
                    content = " ".join(prefix_parts) + "\n" + raw_content

                base_metadata["row_headers"] = row_headers
                base_metadata["table_title"] = table_title

            chunks.append(_make_chunk(
                doc_id=doc_id,
                document_name=document_name,
                page=int(node.get("page") or 1),
                chunk_type=ntype,
                content=content,
                metadata=base_metadata,
                source_node_id=str(node.get("node_id") or ""),
            ))
        else:
            # For college-context docs (KCET cutoff sheets), each course row is its own chunk
            if node.get("metadata", {}).get("college_context") and "|" in content:
                flush_buffer()
                chunks.append(_make_chunk(
                    doc_id=doc_id,
                    document_name=document_name,
                    page=int(node.get("page") or 1),
                    chunk_type="text_chunk",
                    content=content,
                    metadata=base_metadata,
                    source_node_id=str(node.get("node_id") or ""),
                ))
            else:
                if buffer_len + len(content) > chunk_size and buffer_len > 0:
                    flush_buffer()
                buffer_content.append(content)
                buffer_len += len(content)
                buffer_nodes.append(node)

    flush_buffer()

    # Extract atomic fact sentences from paragraph/text chunks for precise retrieval
    fact_chunks: List[Dict[str, Any]] = []
    for chunk in chunks:
        if chunk.get("type") not in ("text_chunk", "paragraph", "table"):
            continue
        raw = chunk.get("metadata", {}).get("raw_content") or chunk.get("content", "")
        # Strip enrichment prefix for fact extraction
        if "[Section:" in raw:
            raw = raw.split("\n", 1)[-1] if "\n" in raw else raw
        facts = extract_fact_sentences(
            raw,
            page=int(chunk.get("page") or 1),
            section=str(chunk.get("section") or ""),
            doc_id=doc_id,
            source_node_id=str(chunk.get("node_id") or ""),
        )
        for fact in facts:
            fact_meta = dict(fact.get("metadata") or {})
            fact_chunks.append(_make_chunk(
                doc_id=doc_id,
                document_name=document_name,
                page=int(fact.get("page") or 1),
                chunk_type="fact",
                content=fact["content"],
                metadata=fact_meta,
                source_node_id=str(chunk.get("node_id") or ""),
            ))

    # Deduplicate facts against existing chunks by content hash
    existing_content = {c.get("metadata", {}).get("raw_content", c.get("content", ""))[:200] for c in chunks}
    for fc in fact_chunks:
        raw = fc.get("metadata", {}).get("raw_content", "")
        if raw[:200] not in existing_content:
            chunks.append(fc)
            existing_content.add(raw[:200])

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

    if embeddings is None:
        print("[Embeddings] Skipping embedding generation (model unavailable)")
        return {**chunked, "embedded": False}

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
    doc_id = chunked_embedded.get("doc_id")
    if doc_id:
        deleted = weaviate.delete_by_doc_id(str(doc_id))
        if deleted:
            print(f"[Weaviate] Removed {deleted} existing chunks for doc_id={doc_id}")
    weaviate.upsert_nodes(chunks)
    weaviate.close()
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
    print(f"  {'-' * 35}")
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
        try:
            with Timer("Embeddings") as t:
                embedded = embed_chunks(chunked)
            timings["embeddings"] = t.elapsed
        except Exception as exc:
            print(f"[Pipeline] Embeddings failed with exception: {exc}")
            embedded = {**chunked, "embedded": False}
            timings["embeddings"] = 0.0
    else:
        embedded = chunked
        timings["embeddings"] = 0.0

    if enable_weaviate:
        try:
            with Timer("Weaviate Storage") as t:
                stored = store_chunks_weaviate(embedded, collection_name=weaviate_collection)
            timings["weaviate"] = t.elapsed
        except Exception as exc:
            print(f"[Pipeline] Weaviate storage failed with exception: {exc}")
            timings["weaviate"] = 0.0
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
