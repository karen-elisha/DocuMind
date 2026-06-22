"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { AlertTriangle, Radio } from "lucide-react";

export type RiskRadarData = {
  active: boolean;
  overall_risk_level: string;
  nodes: Array<{
    id: string;
    type?: string;
    role: string;
    page?: number;
    label?: string;
    risk_level?: string;
    edge_type?: string;
  }>;
  edges: Array<{
    source: string;
    target: string;
    edge_type?: string;
    risk_level?: string;
    polarity?: string;
    depth?: number;
  }>;
  stats?: Record<string, number>;
  trigger_keywords?: string[];
};

type Props = {
  data: RiskRadarData | null | undefined;
};

const ROLE_COLORS: Record<string, string> = {
  seed: "#10b981",
  bridge: "#3b82f6",
  risk: "#ef4444",
  exception: "#f97316",
  qualification: "#f59e0b",
  warning: "#eab308",
  contradiction: "#dc2626",
};

export default function RiskRadar({ data }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 400, height: 220 });
  const [pulse, setPulse] = useState(0);
  const isDark = typeof document !== "undefined" && document.documentElement.classList.contains("dark");

  useEffect(() => {
    if (!data?.active) return;
    const id = setInterval(() => setPulse((p) => (p + 1) % 100), 50);
    return () => clearInterval(id);
  }, [data?.active]);

  useEffect(() => {
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

  if (!data?.active || !data.nodes?.length) return null;

  const graphNodes = data.nodes.map((n) => ({ ...n }));
  const nodeIds = new Set(graphNodes.map((n) => n.id));
  const graphLinks = data.edges
    .filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target))
    .map((e) => ({ ...e }));

  const getNodeColor = useCallback((node: { role?: string }) => {
    return ROLE_COLORS[node.role || "risk"] || "#94a3b8";
  }, []);

  const pulseScale = 1 + 0.15 * Math.sin((pulse / 100) * Math.PI * 2);

  return (
    <div className="mb-5">
      <div className="flex items-center justify-between mb-2.5">
        <div className="text-[10px] font-bold text-red-500 dark:text-red-400 uppercase tracking-widest flex items-center gap-1.5">
          <Radio className="w-3.5 h-3.5 animate-pulse" />
          Risk Radar
        </div>
        <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${
          data.overall_risk_level === "High"
            ? "bg-red-100 dark:bg-red-500/15 text-red-600 dark:text-red-400 border-red-200 dark:border-red-500/30"
            : data.overall_risk_level === "Medium"
              ? "bg-amber-100 dark:bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-200 dark:border-amber-500/30"
              : "bg-yellow-100 dark:bg-yellow-500/15 text-yellow-700 dark:text-yellow-400 border-yellow-200 dark:border-yellow-500/30"
        }`}>
          {data.overall_risk_level} Risk
        </span>
      </div>

      {data.trigger_keywords && data.trigger_keywords.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {data.trigger_keywords.map((kw) => (
            <span
              key={kw}
              className="text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md
                bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-500/20"
            >
              &quot;{kw}&quot;
            </span>
          ))}
        </div>
      )}

      <div
        ref={containerRef}
        className="h-[220px] rounded-xl overflow-hidden border border-red-200/60 dark:border-red-500/20 relative bg-white dark:bg-[#0B0F14]"
      >
        <ForceGraph2D
          width={dimensions.width}
          height={dimensions.height}
          graphData={{ nodes: graphNodes, links: graphLinks }}
          nodeId="id"
          nodeRelSize={5}
          linkColor={() => "rgba(239, 68, 68, 0.75)"}
          linkWidth={2}
          linkDirectionalArrowLength={4}
          linkDirectionalArrowRelPos={1}
          cooldownTicks={80}
          backgroundColor={isDark ? "#0B0F14" : "#ffffff"}
          enableNodeDrag={false}
          nodeCanvasObject={(node: { role?: string; x?: number; y?: number }, ctx, globalScale) => {
            if (node.x == null || node.y == null) return;
            const isRisk = node.role !== "seed";
            const baseR = isRisk ? 5 * pulseScale : 4;
            const r = baseR / globalScale;

            ctx.fillStyle = getNodeColor(node);
            ctx.beginPath();
            ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
            ctx.fill();

            if (isRisk) {
              ctx.strokeStyle = `rgba(239, 68, 68, ${0.3 + 0.3 * Math.sin((pulse / 100) * Math.PI * 2)})`;
              ctx.lineWidth = 2 / globalScale;
              ctx.beginPath();
              ctx.arc(node.x, node.y, r + 3 / globalScale, 0, 2 * Math.PI);
              ctx.stroke();
            }
          }}
        />

        <div className="absolute bottom-2 left-2 flex items-center gap-3 text-[9px] font-bold uppercase tracking-wider text-slate-400">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-emerald-500" /> Seed
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" /> Risk
          </span>
        </div>
      </div>

      {data.stats && (data.stats.total_risk_nodes ?? 0) > 0 && (
        <div className="mt-2 flex items-center gap-1.5 text-[10px] text-slate-500 dark:text-slate-400">
          <AlertTriangle className="w-3 h-3 text-amber-500" />
          {data.stats.total_risk_nodes} risk node{data.stats.total_risk_nodes !== 1 ? "s" : ""} traversed via negative edges
        </div>
      )}
    </div>
  );
}
