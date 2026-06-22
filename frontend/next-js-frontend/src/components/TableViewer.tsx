"use client";

import { useMemo } from "react";
import { XCircle } from "lucide-react";

interface TableViewerProps {
  table: {
    markdown?: string;
    table_number?: string;
    caption?: string;
    page?: number;
    summary?: string;
    headers?: string[];
    rows?: string[][];
  };
  onClose?: () => void;
}

function parseMarkdownTable(md: string): { headers: string[]; rows: string[][] } | null {
  const lines = md.split("\n").map(l => l.trim()).filter(Boolean);
  if (lines.length < 2) return null;

  const dataLines = lines.filter(l => !/^[\|\-:\s]+$/.test(l));
  if (dataLines.length < 2) return null;

  const headers = dataLines[0].split("|").map(c => c.trim()).filter(Boolean);
  const rows = dataLines.slice(1).map(line =>
    line.split("|").map(c => c.trim()).filter(Boolean)
  );

  if (!headers.length) return null;

  const padded = rows.map(row => {
    const r = [...row];
    while (r.length < headers.length) r.push("");
    return r.slice(0, headers.length);
  });

  return { headers, rows: padded };
}

export default function TableViewer({ table, onClose }: TableViewerProps) {
  // Use structured data if available, fall back to markdown parsing
  const parsed = useMemo(() => {
    if (table.headers && table.headers.length > 0 && table.rows) {
      return { headers: table.headers, rows: table.rows };
    }
    if (table.markdown) {
      return parseMarkdownTable(table.markdown);
    }
    return null;
  }, [table.headers, table.rows, table.markdown]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-white dark:bg-[#111827] rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 w-full max-w-5xl max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white dark:bg-[#111827] z-10 flex items-center justify-between p-5 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <span className="bg-amber-100 dark:bg-amber-500/10 text-amber-600 dark:text-amber-500 px-3 py-1 rounded-full text-sm font-bold uppercase tracking-wider border border-amber-200 dark:border-amber-500/20">
              TABLE {table.table_number || "?"}
            </span>
            {table.page && (
              <span className="text-sm text-slate-500 font-medium">Page {table.page}</span>
            )}
          </div>
          {onClose && (
            <button onClick={onClose} className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors">
              <XCircle className="w-5 h-5 text-slate-400" />
            </button>
          )}
        </div>

        <div className="p-6 space-y-5">
          {table.caption && (
            <div>
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5">Caption</div>
              <p className="text-sm text-slate-700 dark:text-slate-300 italic font-medium">{table.caption}</p>
            </div>
          )}

          {parsed ? (
            <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="bg-slate-100 dark:bg-slate-800">
                    {parsed.headers.map((h, i) => (
                      <th key={i} className="px-4 py-3 text-left font-bold text-slate-700 dark:text-slate-200 text-xs uppercase tracking-wider border-b-2 border-slate-300 dark:border-slate-600">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {parsed.rows.map((row, ri) => (
                    <tr key={ri} className="border-b border-slate-100 dark:border-slate-800/50 last:border-0 hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors">
                      {row.map((cell, ci) => (
                        <td key={ci} className="px-4 py-3 text-slate-600 dark:text-slate-300">
                          {cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : table.markdown ? (
            <pre className="text-sm text-slate-600 dark:text-slate-400 bg-slate-50 dark:bg-[#0B0F14] p-4 rounded-xl overflow-x-auto border border-slate-200 dark:border-slate-800 font-mono">
              {table.markdown}
            </pre>
          ) : (
            <div className="text-slate-400 text-center p-8">
              <div className="text-5xl mb-3">📊</div>
              <p>Table data not available</p>
            </div>
          )}

          {table.summary && (
            <div>
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5">Preview</div>
              <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed">{table.summary}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
