"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  ReactFlowProvider,
  useReactFlow,
  type Node,
  type Edge,
  MarkerType,
} from "@xyflow/react";
import dagre from "dagre";
import "@xyflow/react/dist/style.css";
import { Loader2, XCircle } from "lucide-react";
import MindMapNode, { type MindMapNodeData } from "./MindMapNode";
import { getDocumentMindmap } from "@/lib/api";

export type MindMapNodePayload = {
  id: string;
  type: string;
  label: string;
  content: string;
  preview: string;
  page: number;
  level: number;
  bbox?: number[];
  page_height?: number;
  heading_level?: number;
};

type MindMapResponse = {
  doc_id: string;
  root_id: string;
  nodes: MindMapNodePayload[];
  edges: Array<{ source: string; target: string }>;
};

type Props = {
  docId: string;
  onClose: () => void;
  onChat: (node: MindMapNodePayload) => void;
  onViewPdf: (node: MindMapNodePayload) => void;
};

const nodeTypes = { mindmap: MindMapNode };
const NODE_W = 280;
const NODE_H = 130;

function buildChildrenMap(edges: Array<{ source: string; target: string }>) {
  const map = new Map<string, string[]>();
  for (const e of edges) {
    const list = map.get(e.source) || [];
    list.push(e.target);
    map.set(e.source, list);
  }
  return map;
}

function computeVisibleIds(
  rootId: string,
  expanded: Set<string>,
  childrenMap: Map<string, string[]>,
) {
  const visible = new Set<string>([rootId]);
  const queue = [rootId];
  while (queue.length) {
    const id = queue.shift()!;
    if (!expanded.has(id)) continue;
    for (const child of childrenMap.get(id) || []) {
      visible.add(child);
      queue.push(child);
    }
  }
  return visible;
}

function layoutMindMap(nodes: Node[], edges: Edge[]) {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "LR", nodesep: 56, ranksep: 110, marginx: 48, marginy: 48 });

  nodes.forEach((n) => g.setNode(n.id, { width: NODE_W, height: NODE_H }));
  edges.forEach((e) => g.setEdge(e.source, e.target));
  dagre.layout(g);

  return nodes.map((n) => {
    const pos = g.node(n.id);
    return {
      ...n,
      position: { x: pos.x - NODE_W / 2, y: pos.y - NODE_H / 2 },
    };
  });
}

function MindMapCanvas({
  docId,
  onClose,
  onChat,
  onViewPdf,
}: Props) {
  const { fitView } = useReactFlow();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [raw, setRaw] = useState<MindMapResponse | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const prevVisibleRef = useRef<Set<string>>(new Set());
  const nodeByIdRef = useRef<Map<string, MindMapNodePayload>>(new Map());
  const childrenMapRef = useRef<Map<string, string[]>>(new Map());
  const initialFitDone = useRef(false);

  const toggleExpand = useCallback((nodeId: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) next.delete(nodeId);
      else next.add(nodeId);
      return next;
    });
  }, []);

  const applyVisibility = useCallback(
    (data: MindMapResponse, expandedIds: Set<string>, isInitial = false) => {
      const childrenMap = childrenMapRef.current;
      const visible = computeVisibleIds(data.root_id, expandedIds, childrenMap);
      const prevVisible = prevVisibleRef.current;
      const newlyVisible = [...visible].filter((id) => !prevVisible.has(id));

      const payloadById = nodeByIdRef.current;
      const flowNodes: Node[] = [];
      for (const id of visible) {
        const n = payloadById.get(id);
        if (!n) continue;
        const childIds = childrenMap.get(id) || [];
        const hasChildren = childIds.length > 0;
        const isExpanded = expandedIds.has(id);
        flowNodes.push({
          id: n.id,
          type: "mindmap",
          data: {
            label: n.label,
            preview: n.preview,
            type: n.type,
            page: n.page,
            level: n.level,
            heading_level: n.heading_level,
            hasChildren,
            isExpanded,
            childCount: childIds.length,
            isNew: !isInitial && newlyVisible.includes(n.id),
            onToggleExpand: hasChildren ? () => toggleExpand(n.id) : undefined,
            onChat: () => onChat(n),
            onViewPdf: () => onViewPdf(n),
          } satisfies MindMapNodeData,
          position: { x: 0, y: 0 },
        });
      }

      const flowEdges: Edge[] = data.edges
        .filter((e) => visible.has(e.source) && visible.has(e.target))
        .map((e, i) => ({
          id: `e-${e.source}-${e.target}-${i}`,
          source: e.source,
          target: e.target,
          type: "smoothstep",
          animated: newlyVisible.includes(e.target),
          style: { stroke: "#f59e0b", strokeWidth: 2 },
          markerEnd: { type: MarkerType.ArrowClosed, color: "#f59e0b", width: 16, height: 16 },
        }));

      const laidOut = layoutMindMap(flowNodes, flowEdges);
      setNodes(laidOut);
      setEdges(flowEdges);
      prevVisibleRef.current = visible;

      requestAnimationFrame(() => {
        if (!initialFitDone.current || isInitial) {
          fitView({ padding: 0.35, duration: 400 });
          initialFitDone.current = true;
        } else if (newlyVisible.length) {
          fitView({ nodes: newlyVisible.map((id) => ({ id })), padding: 0.4, duration: 350 });
        }
      });
    },
    [fitView, onChat, onViewPdf, toggleExpand],
  );

  const rawRef = useRef<MindMapResponse | null>(null);
  rawRef.current = raw;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setExpanded(new Set());
    prevVisibleRef.current = new Set();
    initialFitDone.current = false;
    setRaw(null);

    getDocumentMindmap(docId)
      .then((data: MindMapResponse) => {
        if (cancelled) return;
        nodeByIdRef.current = new Map(data.nodes.map((n) => [n.id, n]));
        childrenMapRef.current = buildChildrenMap(data.edges);
        setRaw(data);
        rawRef.current = data;
        applyVisibility(data, new Set(), true);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err?.message || "Failed to load mind map");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [docId]);

  useEffect(() => {
    const data = rawRef.current;
    if (!data) return;
    applyVisibility(data, expanded, false);
  }, [expanded, applyVisibility]);

  const stats = useMemo(() => {
    if (!raw) return { total: 0, visible: 0 };
    const visible = computeVisibleIds(raw.root_id, expanded, childrenMapRef.current);
    return { total: raw.nodes.length, visible: visible.size };
  }, [raw, expanded]);

  return (
    <div className="relative w-full h-full bg-[#0a0e14] overflow-hidden">
      <div
        className="absolute inset-0 opacity-30"
        style={{
          backgroundImage:
            "radial-gradient(circle at 1px 1px, rgba(148,163,184,0.15) 1px, transparent 0)",
          backgroundSize: "24px 24px",
        }}
      />

      {loading && (
        <div className="absolute inset-0 flex items-center justify-center z-10 bg-[#0a0e14]/80">
          <div className="flex items-center gap-3 text-slate-400">
            <Loader2 className="w-6 h-6 animate-spin text-amber-500" />
            <span className="text-sm font-medium">Building mind map...</span>
          </div>
        </div>
      )}

      {error && !loading && (
        <div className="absolute inset-0 flex items-center justify-center z-10">
          <div className="text-center text-slate-400 space-y-2 max-w-sm px-6">
            <p className="text-sm">{error}</p>
            <p className="text-xs">Re-upload the document to regenerate the mind map.</p>
          </div>
        </div>
      )}

      {!loading && !error && nodes.length > 0 && (
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          panOnDrag={[1, 2]}
          selectionOnDrag={false}
          zoomOnScroll
          minZoom={0.12}
          maxZoom={1.8}
          proOptions={{ hideAttribution: true }}
          className="bg-transparent"
        >
          <Background color="#334155" gap={24} size={1} />
          <Controls
            showInteractive={false}
            className="!bg-white/90 dark:!bg-[#111827]/90 !border-slate-200 dark:!border-slate-700 !shadow-lg !rounded-xl"
          />
          <MiniMap
            nodeColor={(n) => {
              const t = (n.data as MindMapNodeData)?.type;
              if (t === "table") return "#8b5cf6";
              if (t === "figure") return "#10b981";
              if (t === "document") return "#f59e0b";
              return "#64748b";
            }}
            className="!bg-[#111827]/90 !border-slate-700"
          />
        </ReactFlow>
      )}

      <div className="absolute top-4 left-4 z-20 bg-white/90 dark:bg-[#111827]/90 backdrop-blur-md border border-slate-200 dark:border-slate-700 rounded-xl px-4 py-2 shadow-lg">
        <div className="text-[10px] font-bold text-amber-500 uppercase tracking-widest">Mind Map</div>
        <div className="text-xs font-semibold text-slate-700 dark:text-slate-200 truncate max-w-[200px]">
          {docId}
        </div>
        <div className="text-[10px] text-slate-500 mt-0.5">
          {stats.visible} shown · {stats.total} total
        </div>
        <div className="text-[9px] text-slate-500 mt-1">Click ▶ on a node to expand</div>
      </div>

      <button
        type="button"
        onClick={onClose}
        className="absolute top-4 right-4 z-20 bg-white/90 dark:bg-slate-800/90 shadow-lg border border-slate-200 dark:border-slate-700 px-4 py-2 rounded-full text-sm font-semibold flex items-center gap-2 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors backdrop-blur-sm"
      >
        <XCircle className="w-4 h-4" /> Close Mindmap
      </button>
    </div>
  );
}

export default function MindMapView(props: Props) {
  return (
    <ReactFlowProvider>
      <MindMapCanvas {...props} />
    </ReactFlowProvider>
  );
}
