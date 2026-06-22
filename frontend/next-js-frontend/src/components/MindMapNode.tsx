"use client";

import { memo, type MouseEvent, type PointerEvent } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import {
  MessageSquare, ExternalLink, FileText, Table2,
  Image as ImageIcon, Layers, ChevronRight, Minus,
} from "lucide-react";

export type MindMapNodeData = {
  label: string;
  preview: string;
  type: string;
  page: number;
  level: number;
  heading_level?: number;
  hasChildren?: boolean;
  isExpanded?: boolean;
  childCount?: number;
  isNew?: boolean;
  onToggleExpand?: () => void;
  onChat?: () => void;
  onViewPdf?: () => void;
};

const TYPE_STYLES: Record<string, { border: string; badge: string; icon: typeof FileText }> = {
  document: {
    border: "border-amber-400/60 dark:border-amber-500/40",
    badge: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
    icon: Layers,
  },
  heading: {
    border: "border-amber-400/50 dark:border-amber-500/35",
    badge: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
    icon: FileText,
  },
  content: {
    border: "border-slate-300/60 dark:border-slate-600/50",
    badge: "bg-slate-500/10 text-slate-600 dark:text-slate-400",
    icon: FileText,
  },
  table: {
    border: "border-violet-400/50 dark:border-violet-500/35",
    badge: "bg-violet-500/15 text-violet-600 dark:text-violet-400",
    icon: Table2,
  },
  figure: {
    border: "border-emerald-400/50 dark:border-emerald-500/35",
    badge: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
    icon: ImageIcon,
  },
};

function MindMapNode({ data }: NodeProps) {
  const d = data as MindMapNodeData;
  const style = TYPE_STYLES[d.type] || TYPE_STYLES.content;
  const Icon = style.icon;
  const typeLabel = d.type === "heading" && d.heading_level
    ? `H${d.heading_level}`
    : d.type.toUpperCase();

  const stopFlow = (e: MouseEvent | PointerEvent) => {
    e.stopPropagation();
    e.preventDefault();
  };

  return (
    <div
      className={`relative w-[272px] rounded-2xl border-2 ${style.border} bg-white/95 dark:bg-[#111827]/95 backdrop-blur-md shadow-xl ${d.isNew ? "mm-node-enter" : ""}`}
      onPointerDown={stopFlow}
    >
      <Handle type="target" position={Position.Left} className="!w-2 !h-2 !bg-amber-400 !border-none pointer-events-none" />

      <div className="p-3.5 space-y-2">
        <div className="flex items-start gap-2">
          <div className={`shrink-0 w-9 h-9 rounded-full flex items-center justify-center ${style.badge}`}>
            <Icon className="w-4 h-4" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <span className={`text-[9px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded ${style.badge}`}>
                {typeLabel}
              </span>
              <span className="text-[9px] font-bold uppercase tracking-widest text-sky-500 bg-sky-500/10 px-1.5 py-0.5 rounded">
                PG {d.page}
              </span>
            </div>
            <h3 className="text-xs font-bold text-slate-800 dark:text-slate-100 leading-snug line-clamp-2">
              {d.label}
            </h3>
          </div>

          {d.hasChildren && (
            <button
              type="button"
              title={d.isExpanded ? "Collapse" : `Expand ${d.childCount} children`}
              onPointerDown={stopFlow}
              onClick={(e) => {
                stopFlow(e);
                d.onToggleExpand?.();
              }}
              className={`nopan nodrag nowheel relative shrink-0 w-8 h-8 rounded-full border-2 border-amber-400 bg-[#0a0e14] text-amber-400 shadow-lg flex items-center justify-center cursor-pointer transition-all duration-200 hover:scale-110 hover:bg-amber-500 hover:text-[#0a0e14] z-50 ${d.isExpanded ? "mm-expand-btn-open" : ""}`}
            >
              {d.isExpanded ? (
                <Minus className="w-3.5 h-3.5 pointer-events-none" />
              ) : (
                <>
                  <ChevronRight className="w-4 h-4 pointer-events-none" />
                  {(d.childCount ?? 0) > 0 && (
                    <span className="absolute -top-1 -right-1 min-w-[14px] h-[14px] px-0.5 rounded-full bg-amber-500 text-[8px] font-bold text-[#0a0e14] flex items-center justify-center pointer-events-none">
                      {d.childCount}
                    </span>
                  )}
                </>
              )}
            </button>
          )}
        </div>

        {d.preview && (
          <p className="text-[10px] text-slate-500 dark:text-slate-400 leading-relaxed line-clamp-3 pl-[46px]">
            {d.preview}
          </p>
        )}

        <div className="flex items-center gap-1.5 pl-[46px] pt-1">
          <button
            type="button"
            onPointerDown={stopFlow}
            onClick={(e) => { stopFlow(e); d.onChat?.(); }}
            className="nopan nodrag nowheel flex items-center gap-1 px-2 py-1 rounded-lg text-[9px] font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/20 transition-colors cursor-pointer"
          >
            <MessageSquare className="w-3 h-3" />
            Chat
          </button>
          <button
            type="button"
            onPointerDown={stopFlow}
            onClick={(e) => { stopFlow(e); d.onViewPdf?.(); }}
            className="nopan nodrag nowheel flex items-center gap-1 px-2 py-1 rounded-lg text-[9px] font-bold uppercase tracking-wider bg-sky-500/10 text-sky-600 dark:text-sky-400 hover:bg-sky-500/20 transition-colors cursor-pointer"
          >
            <ExternalLink className="w-3 h-3" />
            View PDF
          </button>
        </div>
      </div>

      <Handle type="source" position={Position.Right} className="!w-2 !h-2 !bg-amber-400 !border-none pointer-events-none" />
    </div>
  );
}

export default memo(MindMapNode);
