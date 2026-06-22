"use client";

import { useState } from "react";
import {
  FileText, Image, Table2, BarChart3, Heading, AlignLeft,
  ChevronDown, ChevronUp, ExternalLink
} from "lucide-react";

interface InsightsData {
  document_name: string;
  document_id: string;
  upload_time: string;
  parser?: string;
  parser_warning?: string;
  stats: {
    pages: number;
    headings: number;
    paragraphs: number;
    tables: number;
    images: number;
    captions: number;
    footnotes: number;
    charts: number;
  };
  images: Array<{
    image_id?: string;
    image_data?: string;
    page?: number;
    caption?: string;
    figure_number?: string;
    vision_summary?: string;
    vision_detail?: Record<string, unknown>;
    is_chart?: boolean;
  }>;
  tables: Array<{
    page?: number;
    markdown?: string;
    table_number?: string;
    caption?: string;
    summary?: string;
    headers?: string[];
    rows?: string[][];
  }>;
  headings: Array<{
    page?: number;
    content?: string;
    level?: number;
  }>;
  extracted_text: Record<string, {
    headings: string[];
    caption: string[];
    paragraphs: string[];
  }>;
}

interface DocumentInsightsProps {
  data: InsightsData;
  onClose?: () => void;
  onShowFigure?: (figure: any) => void;
  onShowTable?: (table: any) => void;
}

function CollapsibleSection({ title, count, icon: Icon, children, defaultOpen = false }: {
  title: string; count?: number; icon: any; children: React.ReactNode; defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-4 bg-slate-50 dark:bg-[#0B0F14] hover:bg-slate-100 dark:hover:bg-slate-800/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 text-slate-400" />
          <span className="text-sm font-semibold text-slate-700 dark:text-slate-300">{title}</span>
          {count !== undefined && (
            <span className="bg-slate-200 dark:bg-slate-700 text-slate-500 dark:text-slate-400 px-1.5 py-0.5 rounded text-[10px] font-bold">{count}</span>
          )}
        </div>
        {open ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
      </button>
      {open && <div className="p-4 border-t border-slate-200 dark:border-slate-700">{children}</div>}
    </div>
  );
}

function ImageGallery({ images, onShowFigure }: { images: InsightsData["images"]; onShowFigure?: (fig: any) => void }) {
  if (images.length === 0) {
    return <div className="text-center text-slate-400 py-8 text-sm">No images found.</div>;
  }
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {images.map((img, i) => (
        <div
          key={i}
          className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden hover:shadow-md transition-all cursor-pointer group"
          onClick={() => onShowFigure?.(img)}
        >
          {img.image_data ? (
            <div className="aspect-[4/3] bg-slate-100 dark:bg-slate-900 flex items-center justify-center p-2">
              <img
                src={`data:image/jpeg;base64,${img.image_data}`}
                alt={img.caption || `Image ${img.figure_number}`}
                className="max-w-full max-h-full object-contain group-hover:scale-105 transition-transform duration-300"
              />
            </div>
          ) : (
            <div className="aspect-[4/3] bg-slate-100 dark:bg-slate-900 flex items-center justify-center text-slate-400">
              <Image className="w-10 h-10" />
            </div>
          )}
          <div className="p-3 space-y-1">
            <div className="flex items-center gap-2">
              {img.figure_number && (
                <span className="text-[10px] font-bold text-emerald-500 uppercase tracking-wider bg-emerald-50 dark:bg-emerald-500/10 px-1.5 py-0.5 rounded">
                  Fig. {img.figure_number}
                </span>
              )}
              <span className="text-[10px] text-slate-400">p.{img.page}</span>
            </div>
            {img.caption && (
              <p className="text-xs text-slate-600 dark:text-slate-400 line-clamp-2 leading-relaxed">{img.caption}</p>
            )}
            {img.vision_summary && (
              <p className="text-[11px] text-slate-500 italic line-clamp-2">{img.vision_summary}</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function TablesView({ tables, onShowTable }: { tables: InsightsData["tables"]; onShowTable?: (tbl: any) => void }) {
  if (tables.length === 0) {
    return <div className="text-center text-slate-400 py-8 text-sm">No tables found.</div>;
  }
  return (
    <div className="space-y-3">
      {tables.map((tbl, i) => (
        <div
          key={i}
          className="bg-white dark:bg-[#111827] border border-slate-200 dark:border-slate-700 rounded-xl p-4 hover:shadow-md transition-all cursor-pointer"
          onClick={() => onShowTable?.(tbl)}
        >
          <div className="flex items-center gap-2 mb-2">
            {tbl.table_number && (
              <span className="text-[10px] font-bold text-amber-600 dark:text-amber-400 uppercase tracking-wider bg-amber-50 dark:bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-200 dark:border-amber-500/20">
                Table {tbl.table_number}
              </span>
            )}
            <span className="text-[10px] text-slate-400">p.{tbl.page}</span>
          </div>
          {tbl.caption && <p className="text-xs text-slate-600 dark:text-slate-400 mb-2 italic">{tbl.caption}</p>}

          {/* Mini table preview with structured data */}
          {tbl.headers && tbl.headers.length > 0 && tbl.rows && tbl.rows.length > 0 ? (
            <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700">
              <table className="w-full text-[11px] border-collapse">
                <thead>
                  <tr className="bg-slate-50 dark:bg-slate-800/50">
                    {tbl.headers.slice(0, 4).map((h, ci) => (
                      <th key={ci} className="px-2 py-1.5 text-left font-bold text-slate-500 uppercase tracking-wider border-b border-slate-200 dark:border-slate-700">
                        {h}
                      </th>
                    ))}
                    {tbl.headers.length > 4 && (
                      <th className="px-2 py-1.5 text-slate-400">+{tbl.headers.length - 4}</th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {tbl.rows.slice(0, 3).map((row, ri) => (
                    <tr key={ri} className="border-b border-slate-100 dark:border-slate-800/50 last:border-0">
                      {row.slice(0, 4).map((cell, ci) => (
                        <td key={ci} className="px-2 py-1.5 text-slate-600 dark:text-slate-400 truncate max-w-[120px]">{cell}</td>
                      ))}
                      {row.length > 4 && <td className="px-2 py-1.5 text-slate-400">...</td>}
                    </tr>
                  ))}
                  {tbl.rows.length > 3 && (
                    <tr><td colSpan={Math.min(tbl.headers.length, 4) + (tbl.headers.length > 4 ? 1 : 0)} className="px-2 py-1.5 text-[10px] text-slate-400 text-center italic">+{tbl.rows.length - 3} more rows</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          ) : tbl.markdown ? (
            <pre className="text-xs text-slate-500 dark:text-slate-500 line-clamp-4 bg-slate-50 dark:bg-[#0B0F14] p-3 rounded-lg overflow-x-auto font-mono">
              {tbl.markdown.slice(0, 300)}
            </pre>
          ) : null}

          <div className="mt-2 flex items-center gap-1 text-[10px] text-emerald-500 font-semibold opacity-0 group-hover:opacity-100 transition-opacity">
            <ExternalLink className="w-3 h-3" /> Click to view full table
          </div>
        </div>
      ))}
    </div>
  );
}

export default function DocumentInsights({ data, onClose, onShowFigure, onShowTable }: DocumentInsightsProps) {
  const stats = data.stats;
  const charts = data.images.filter(img => img.is_chart);
  const regularImages = data.images.filter(img => !img.is_chart);

  return (
    <div className="bg-white dark:bg-[#111827] border-l border-slate-200 dark:border-slate-800 h-full overflow-y-auto">
      {/* Header */}
      <div className="sticky top-0 z-10 bg-white dark:bg-[#111827] border-b border-slate-200 dark:border-slate-800 p-4 flex items-center justify-between">
        <div className="min-w-0 flex-1">
          <h2 className="font-bold text-sm text-slate-800 dark:text-slate-100 truncate">{data.document_name}</h2>
          <p className="text-[10px] text-slate-500 truncate mt-0.5">ID: {data.document_id}</p>
        </div>
        {onClose && (
          <button onClick={onClose} className="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors flex-shrink-0 ml-2">
            <FileText className="w-4 h-4 text-slate-400" />
          </button>
        )}
      </div>

      {/* Parser info */}
      <div className="px-4 py-2 border-b border-slate-200 dark:border-slate-800 flex items-center gap-2">
        {data.parser === "docling" ? (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-600 dark:text-emerald-400">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            Docling
          </span>
        ) : data.parser === "pymupdf" ? (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold text-amber-600 dark:text-amber-400">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
            PyMuPDF Fallback
          </span>
        ) : null}
        {data.parser_warning && (
          <span className="text-[10px] text-amber-500 ml-1">{data.parser_warning}</span>
        )}
      </div>

      {/* Stats strip */}
      <div className="grid grid-cols-4 gap-2 p-4 bg-slate-50 dark:bg-[#0B0F14] border-b border-slate-200 dark:border-slate-800">
        {[
          { label: "Pages", value: stats.pages, color: "text-blue-500" },
          { label: "Images", value: stats.images, color: "text-emerald-500" },
          { label: "Tables", value: stats.tables, color: "text-amber-500" },
          { label: "Charts", value: stats.charts, color: "text-purple-500" },
          { label: "Headings", value: stats.headings, color: "text-sky-500" },
          { label: "Paragraphs", value: stats.paragraphs, color: "text-slate-500" },
          { label: "Captions", value: stats.captions, color: "text-teal-500" },
          { label: "Footnotes", value: stats.footnotes, color: "text-rose-500" },
        ].map((s, i) => (
          <div key={i} className="text-center bg-white dark:bg-[#111827] rounded-lg p-2 border border-slate-200 dark:border-slate-700">
            <div className={`text-lg font-bold ${s.color}`}>{s.value}</div>
            <div className="text-[8px] font-bold text-slate-400 uppercase tracking-widest mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Collapsible sections */}
      <div className="p-4 space-y-3">
        <CollapsibleSection title="Images / Figures" count={regularImages.length} icon={Image} defaultOpen={regularImages.length > 0}>
          <ImageGallery images={regularImages} onShowFigure={onShowFigure} />
        </CollapsibleSection>

        <CollapsibleSection title="Charts / Graphs" count={charts.length} icon={BarChart3} defaultOpen={charts.length > 0}>
          <ImageGallery images={charts} onShowFigure={onShowFigure} />
        </CollapsibleSection>

        <CollapsibleSection title="Tables" count={data.tables.length} icon={Table2} defaultOpen={data.tables.length > 0}>
          <TablesView tables={data.tables} onShowTable={onShowTable} />
        </CollapsibleSection>

        <CollapsibleSection title="Headings" count={data.headings.length} icon={Heading}>
          {data.headings.length === 0 ? (
            <div className="text-center text-slate-400 py-4 text-sm">No headings found.</div>
          ) : (
            <div className="space-y-1">
              {data.headings.map((h, i) => (
                <div key={i} className="flex items-center gap-2 p-2 bg-slate-50 dark:bg-[#0B0F14] rounded-lg border border-slate-200 dark:border-slate-800">
                  <span className="text-[10px] font-bold text-slate-400 w-10 flex-shrink-0">p.{h.page}</span>
                  <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">{h.content}</span>
                </div>
              ))}
            </div>
          )}
        </CollapsibleSection>

        <CollapsibleSection title="Raw Extracted Text" icon={AlignLeft}>
          {Object.keys(data.extracted_text).length === 0 ? (
            <div className="text-center text-slate-400 py-4 text-sm">No text extracted.</div>
          ) : (
            <div className="space-y-4 max-h-[400px] overflow-y-auto">
              {Object.entries(data.extracted_text)
                .sort(([a], [b]) => parseInt(a) - parseInt(b))
                .map(([page, content]) => (
                  <div key={page} className="bg-slate-50 dark:bg-[#0B0F14] rounded-lg p-3 border border-slate-200 dark:border-slate-800">
                    <div className="text-[9px] font-bold text-slate-400 uppercase tracking-widest mb-2">Page {page}</div>
                    {content.headings.map((h, i) => (
                      <div key={`h-${i}`} className="text-xs font-bold text-slate-700 dark:text-slate-300 mt-1">{h}</div>
                    ))}
                    {content.paragraphs.map((p, i) => (
                      <p key={`p-${i}`} className="text-xs text-slate-600 dark:text-slate-400 mb-1.5 leading-relaxed">{p}</p>
                    ))}
                    {content.caption.length > 0 && (
                      <div className="mt-1 text-[11px] italic text-slate-500">
                        {content.caption.map((c, i) => <div key={`c-${i}`}>{c}</div>)}
                      </div>
                    )}
                  </div>
                ))}
            </div>
          )}
        </CollapsibleSection>
      </div>
    </div>
  );
}
