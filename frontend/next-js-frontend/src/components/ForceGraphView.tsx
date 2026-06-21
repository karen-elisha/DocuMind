"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { getGraphData } from "@/lib/api";
import { useTheme } from "next-themes";

interface ForceGraphViewProps {
  onNodeClick: (node: any) => void;
  graphData?: { nodes: any[], edges: any[] };
}

export default function ForceGraphView({ onNodeClick, graphData }: ForceGraphViewProps) {
  const [data, setData] = useState({ nodes: [], edges: [] });
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [hoverNode, setHoverNode] = useState<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  
  // Track dark mode implicitly by reading document class, or defaulting to dark
  const isDark = typeof document !== 'undefined' && document.documentElement.classList.contains('dark');

  useEffect(() => {
    if (graphData) {
      const nodeIds = new Set(graphData.nodes.map((n: any) => n.id));
      const links = graphData.edges
        .filter((e: any) => {
          const srcId = typeof e.source === 'object' ? e.source.id : e.source;
          const tgtId = typeof e.target === 'object' ? e.target.id : e.target;
          return nodeIds.has(srcId) && nodeIds.has(tgtId);
        })
        .map((e: any) => ({
          ...e,
          source: typeof e.source === 'object' ? e.source.id : e.source,
          target: typeof e.target === 'object' ? e.target.id : e.target,
        }));
      setData({ nodes: graphData.nodes as never[], edges: links as never[] });
      return;
    }
    
    // Fetch Graph Data
    getGraphData().then((graph) => {
      // Data format expected by react-force-graph: { nodes, links }
      // The API returns { nodes, edges }
      const nodeIds = new Set(graph.nodes.map((n: any) => n.id));
      const links = graph.edges
        .filter((e: any) => {
          const srcId = typeof e.source === 'object' ? e.source.id : e.source;
          const tgtId = typeof e.target === 'object' ? e.target.id : e.target;
          return nodeIds.has(srcId) && nodeIds.has(tgtId);
        })
        .map((e: any) => ({
          ...e,
          source: typeof e.source === 'object' ? e.source.id : e.source,
          target: typeof e.target === 'object' ? e.target.id : e.target,
        }));
      setData({ nodes: graph.nodes, edges: links });
    }).catch(console.error);
  }, [graphData]);

  useEffect(() => {
    // Resize observer to make graph responsive
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      if (entries[0]) {
        setDimensions({
          width: entries[0].contentRect.width,
          height: entries[0].contentRect.height,
        });
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  const getNodeColor = (node: any) => {
    switch (node.type) {
      case "heading": return "#3b82f6"; // blue-500
      case "paragraph": return "#8b5cf6"; // violet-500
      case "table": return "#f59e0b"; // amber-500
      case "image":
      case "figure": return "#10b981"; // emerald-500
      case "footnote": return "#6366f1"; // indigo-500
      default: return "#94a3b8"; // slate-400
    }
  };

  const getLinkColor = (link: any) => {
    if (link.polarity === "negative") return "rgba(239, 68, 68, 0.6)"; // red-500 with opacity
    return isDark ? "rgba(148, 163, 184, 0.2)" : "rgba(100, 116, 139, 0.2)";
  };

  return (
    <div ref={containerRef} className="w-full h-full relative cursor-crosshair">
      <ForceGraph2D
        width={dimensions.width}
        height={dimensions.height}
        graphData={{ nodes: data.nodes, links: data.edges }}
        nodeId="id"
        nodeColor={getNodeColor}
        nodeRelSize={4}
        linkColor={getLinkColor}
        linkWidth={1}
        linkDirectionalArrowLength={2.5}
        linkDirectionalArrowRelPos={1}
        backgroundColor={isDark ? "#0B0F14" : "#ffffff"}
        onNodeHover={(node) => setHoverNode(node)}
        onNodeClick={(node) => onNodeClick(node)}
        // Paint node label on canvas
        nodeCanvasObject={(node: any, ctx, globalScale) => {
          const isHovered = node === hoverNode;
          let label = node.type?.toUpperCase() || "";
          
          if (isHovered && node.content) {
            label = node.content.length > 50 ? node.content.substring(0, 50) + "..." : node.content;
          } else if (!isHovered && node.content) {
            // Optional: show a very short snippet even when not hovered instead of "PARAGRAPH"
            label = node.content.length > 15 ? node.content.substring(0, 15) + "..." : node.content;
          }

          const fontSize = isHovered ? 14 / globalScale : 10 / globalScale;
          ctx.font = isHovered ? `bold ${fontSize}px Sans-Serif` : `${fontSize}px Sans-Serif`;

          ctx.fillStyle = getNodeColor(node);
          ctx.beginPath();
          ctx.arc(node.x, node.y, isHovered ? 6 : 4, 0, 2 * Math.PI, false);
          ctx.fill();

          if (globalScale > 1.5 || isHovered) {
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            
            if (isHovered) {
              const textWidth = ctx.measureText(label).width;
              ctx.fillStyle = isDark ? "rgba(11, 15, 20, 0.9)" : "rgba(255, 255, 255, 0.9)";
              ctx.fillRect(node.x - textWidth / 2 - 4, node.y + 8 - fontSize / 2 - 2, textWidth + 8, fontSize + 4);
              ctx.fillStyle = isDark ? "#ffffff" : "#000000";
              ctx.fillText(label, node.x, node.y + 8);
            } else {
              ctx.fillStyle = isDark ? "rgba(255, 255, 255, 0.5)" : "rgba(0, 0, 0, 0.5)";
              ctx.fillText(label, node.x, node.y + 8);
            }
          }
        }}
      />
      
      {/* Legend overlays */}
      <div className="absolute bottom-4 left-4 bg-white/80 dark:bg-[#111827]/80 backdrop-blur-sm p-3 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm text-[10px] font-bold uppercase tracking-widest text-slate-500">
        <div className="flex items-center gap-2 mb-1.5"><div className="w-2.5 h-2.5 rounded-full bg-blue-500" /> Heading</div>
        <div className="flex items-center gap-2 mb-1.5"><div className="w-2.5 h-2.5 rounded-full bg-violet-500" /> Paragraph</div>
        <div className="flex items-center gap-2 mb-1.5"><div className="w-2.5 h-2.5 rounded-full bg-emerald-500" /> Image/Figure</div>
        <div className="flex items-center gap-2 mb-1.5"><div className="w-2.5 h-2.5 rounded-full bg-amber-500" /> Table</div>
        <div className="flex items-center gap-2 mb-3"><div className="w-2.5 h-2.5 rounded-full bg-indigo-500" /> Footnote</div>
        
        <div className="h-px bg-slate-200 dark:bg-slate-700 my-2" />
        
        <div className="flex items-center gap-2 mb-1.5"><div className="w-4 h-0.5 bg-slate-300 dark:bg-slate-600" /> Positive Edge</div>
        <div className="flex items-center gap-2"><div className="w-4 h-0.5 bg-red-500" /> Negative Edge</div>
      </div>
    </div>
  );
}
