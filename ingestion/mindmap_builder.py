"""Build a hierarchical mind-map tree from parsed document elements."""

from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

_MAX_NODES = 96
_MAX_CONTENT_PER_SECTION = 4
_CONTENT_PREVIEW = 220

_NUMBERED_HEADING = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+)")


def _nid(prefix: str = "mm") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _preview(text: str, limit: int = _CONTENT_PREVIEW) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _numbered_level(text: str) -> Optional[int]:
    m = _NUMBERED_HEADING.match(text.strip())
    if not m:
        return None
    return m.group(1).count(".") + 1


def _infer_heading_levels(elements: List[Dict[str, Any]]) -> Dict[str, int]:
    """Map element_id -> heading level using metadata or font-size tiers."""
    heading_sizes: List[float] = []
    heading_ids: List[str] = []
    for el in elements:
        if el.get("type") != "heading":
            continue
        md = el.get("metadata") or {}
        if md.get("heading_level"):
            continue
        fs = md.get("font_size")
        if fs:
            heading_sizes.append(float(fs))
            heading_ids.append(el.get("element_id", ""))

    size_levels: Dict[float, int] = {}
    if heading_sizes:
        unique = sorted(set(heading_sizes), reverse=True)
        for idx, size in enumerate(unique[:6]):
            size_levels[size] = idx + 1

    levels: Dict[str, int] = {}
    for el in elements:
        if el.get("type") != "heading":
            continue
        eid = el.get("element_id", "")
        content = el.get("content", "")
        md = el.get("metadata") or {}
        if md.get("heading_level"):
            levels[eid] = int(md["heading_level"])
            continue
        num_lvl = _numbered_level(content)
        if num_lvl:
            levels[eid] = num_lvl
            continue
        fs = md.get("font_size")
        if fs and float(fs) in size_levels:
            levels[eid] = size_levels[float(fs)]
        else:
            levels[eid] = 2
    return levels


def _node_payload(
    *,
    node_id: str,
    node_type: str,
    label: str,
    content: str,
    page: int,
    level: int,
    parent_id: Optional[str],
    element_id: Optional[str] = None,
    bbox: Optional[List[float]] = None,
    page_height: Optional[float] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "id": node_id,
        "type": node_type,
        "label": label,
        "content": content,
        "preview": _preview(content),
        "page": page,
        "level": level,
        "parent_id": parent_id,
    }
    if element_id:
        payload["element_id"] = element_id
    if bbox:
        payload["bbox"] = bbox
    if page_height:
        payload["page_height"] = page_height
    if extra:
        payload.update(extra)
    return payload


def build_mindmap(
    doc_id: str,
    document_name: str,
    elements: List[Dict[str, Any]],
    images: Optional[List[Dict[str, Any]]] = None,
    page_count: int = 0,
) -> Dict[str, Any]:
    """
    Produce a hierarchical mind-map:
    document root -> headings (nested) -> content / tables / figures.
    """
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, str]] = []
    heading_levels = _infer_heading_levels(elements)

    root_id = _nid("root")
    root_label = document_name or doc_id
    nodes.append(
        _node_payload(
            node_id=root_id,
            node_type="document",
            label=root_label,
            content=f"Overview of {root_label} ({page_count or '?'} pages)",
            page=1,
            level=0,
            parent_id=None,
        )
    )

    # heading stack: (level, node_id)
    stack: List[Tuple[int, str]] = [(0, root_id)]
    section_content: Dict[str, List[str]] = {}
    section_meta: Dict[str, Dict[str, Any]] = {}
    child_counts: Dict[str, int] = {}

    def parent_for_level(level: int) -> str:
        while len(stack) > 1 and stack[-1][0] >= level:
            stack.pop()
        return stack[-1][1]

    def add_edge(source: str, target: str) -> None:
        edges.append({"source": source, "target": target})

    def can_add_child(parent: str) -> bool:
        return child_counts.get(parent, 0) < _MAX_CONTENT_PER_SECTION and len(nodes) < _MAX_NODES

    def flush_paragraphs(parent_id: str) -> None:
        if parent_id not in section_content or not section_content[parent_id]:
            return
        if not can_add_child(parent_id):
            section_content[parent_id] = []
            return
        combined = "\n\n".join(section_content[parent_id])
        section_content[parent_id] = []
        meta = section_meta.get(parent_id, {})
        cid = _nid("content")
        nodes.append(
            _node_payload(
                node_id=cid,
                node_type="content",
                label="Section content",
                content=combined,
                page=meta.get("page", 1),
                level=meta.get("level", 1) + 1,
                parent_id=parent_id,
                bbox=meta.get("bbox"),
                page_height=meta.get("page_height"),
            )
        )
        add_edge(parent_id, cid)
        child_counts[parent_id] = child_counts.get(parent_id, 0) + 1

    images = images or []
    images_by_page: Dict[int, List[Dict]] = {}
    for img in images:
        images_by_page.setdefault(int(img.get("page", 1)), []).append(img)

    for el in elements:
        if len(nodes) >= _MAX_NODES:
            break

        etype = el.get("type", "paragraph")
        content = (el.get("content") or "").strip()
        if not content and etype not in ("image",):
            continue

        page = int(el.get("page", 1))
        md = el.get("metadata") or {}
        bbox = md.get("bbox")
        page_height = md.get("page_height")
        eid = el.get("element_id")

        if etype == "heading":
            flush_paragraphs(stack[-1][1])
            level = heading_levels.get(eid or "", md.get("heading_level", 2))
            try:
                level = int(level)
            except (TypeError, ValueError):
                level = 2
            level = max(1, min(level, 5))

            parent_id = parent_for_level(level)
            hid = _nid("h")
            label = content.split("\n")[0][:120]
            nodes.append(
                _node_payload(
                    node_id=hid,
                    node_type="heading",
                    label=label,
                    content=content,
                    page=page,
                    level=level,
                    parent_id=parent_id,
                    element_id=eid,
                    bbox=bbox,
                    page_height=page_height,
                    extra={"heading_level": level},
                )
            )
            add_edge(parent_id, hid)
            child_counts[parent_id] = child_counts.get(parent_id, 0) + 1
            stack.append((level, hid))
            section_content[hid] = []
            section_meta[hid] = {"page": page, "level": level, "bbox": bbox, "page_height": page_height}
            continue

        parent_id = stack[-1][1]
        if not can_add_child(parent_id):
            continue

        if etype == "table":
            flush_paragraphs(parent_id)
            tid = _nid("table")
            caption = md.get("table_caption") or md.get("table_number") or "Table"
            nodes.append(
                _node_payload(
                    node_id=tid,
                    node_type="table",
                    label=str(caption)[:80],
                    content=content,
                    page=page,
                    level=stack[-1][0] + 1,
                    parent_id=parent_id,
                    element_id=eid,
                    bbox=bbox,
                    page_height=page_height,
                )
            )
            add_edge(parent_id, tid)
            child_counts[parent_id] = child_counts.get(parent_id, 0) + 1
        elif etype in ("caption",):
            section_content.setdefault(parent_id, []).append(content)
            if parent_id in section_meta:
                section_meta[parent_id]["page"] = page
        elif etype == "paragraph":
            section_content.setdefault(parent_id, []).append(content)
            if parent_id in section_meta and not section_meta[parent_id].get("bbox"):
                section_meta[parent_id]["bbox"] = bbox
                section_meta[parent_id]["page_height"] = page_height
                section_meta[parent_id]["page"] = page
        elif etype == "footnote":
            if len(section_content.get(parent_id, [])) < 8:
                section_content.setdefault(parent_id, []).append(content)

    # Flush trailing content for all sections on stack
    for _, pid in stack:
        flush_paragraphs(pid)

    # Attach a few figure nodes under nearest heading by page
    for page, page_images in sorted(images_by_page.items()):
        if len(nodes) >= _MAX_NODES:
            break
        parent_id = root_id
        for n in reversed(nodes):
            if n["type"] == "heading" and n.get("page", 0) <= page:
                parent_id = n["id"]
                break
        if not can_add_child(parent_id):
            continue
        for img in page_images[:2]:
            if len(nodes) >= _MAX_NODES:
                break
            fig_num = img.get("figure_number") or "Figure"
            summary = img.get("caption") or img.get("vision_summary") or f"Image on page {page}"
            fid = _nid("fig")
            nodes.append(
                _node_payload(
                    node_id=fid,
                    node_type="figure",
                    label=str(fig_num)[:80],
                    content=str(summary),
                    page=page,
                    level=nodes[-1]["level"] + 1 if nodes else 1,
                    parent_id=parent_id,
                    element_id=img.get("image_id"),
                )
            )
            add_edge(parent_id, fid)
            child_counts[parent_id] = child_counts.get(parent_id, 0) + 1

    return {
        "doc_id": doc_id,
        "root_id": root_id,
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "total_nodes": len(nodes),
            "headings": sum(1 for n in nodes if n["type"] == "heading"),
            "content_nodes": sum(1 for n in nodes if n["type"] in ("content", "table", "figure")),
        },
    }
