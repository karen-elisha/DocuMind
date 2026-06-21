"use client";

import { XCircle } from "lucide-react";

interface FigureViewerProps {
  figure: {
    image_data?: string;
    figure_number?: string;
    caption?: string;
    page?: number;
    vision_summary?: string;
    vision_detail?: {
      chart_type?: string;
      title?: string;
      axes?: string;
      observations?: string[];
      conclusion?: string;
    };
  };
  nearbyText?: string;
  onClose?: () => void;
}

export default function FigureViewer({ figure, nearbyText, onClose }: FigureViewerProps) {
  const detail = figure.vision_detail || {};

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-white dark:bg-[#111827] rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 w-full max-w-5xl max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white dark:bg-[#111827] z-10 flex items-center justify-between p-5 border-b border-slate-200 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <span className="bg-emerald-100 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-500 px-3 py-1 rounded-full text-sm font-bold uppercase tracking-wider border border-emerald-200 dark:border-emerald-500/20">
              Figure {figure.figure_number || "?"}
            </span>
            {figure.page && (
              <span className="text-sm text-slate-500 font-medium">Page {figure.page}</span>
            )}
          </div>
          {onClose && (
            <button onClick={onClose} className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors">
              <XCircle className="w-5 h-5 text-slate-400" />
            </button>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-0">
          {/* Image */}
          <div className="p-6 flex items-center justify-center bg-slate-50 dark:bg-[#0B0F14] min-h-[400px]">
            {figure.image_data ? (
              <img
                src={`data:image/jpeg;base64,${figure.image_data}`}
                alt={figure.caption || `Figure ${figure.figure_number}`}
                className="max-w-full max-h-[70vh] object-contain rounded-xl shadow-lg"
              />
            ) : (
              <div className="text-slate-400 text-center p-8">
                <div className="text-5xl mb-3">🖼️</div>
                <p>Image data not available</p>
              </div>
            )}
          </div>

          {/* Details */}
          <div className="p-6 overflow-y-auto max-h-[70vh] space-y-5">
            {figure.caption && (
              <div>
                <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5">Caption</div>
                <p className="text-sm text-slate-700 dark:text-slate-300 italic">{figure.caption}</p>
              </div>
            )}

            {figure.vision_summary && (
              <div>
                <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5">Vision Understanding</div>
                <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed">{figure.vision_summary}</p>
              </div>
            )}

            {detail.chart_type && (
              <div>
                <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5">Chart Type</div>
                <p className="text-sm font-medium text-slate-700 dark:text-slate-300">{detail.chart_type}</p>
              </div>
            )}

            {detail.axes && (
              <div>
                <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5">Axes</div>
                <p className="text-sm text-slate-600 dark:text-slate-400">{detail.axes}</p>
              </div>
            )}

            {detail.observations && detail.observations.length > 0 && (
              <div>
                <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5">Key Observations</div>
                <ul className="space-y-1">
                  {detail.observations.map((obs: string, i: number) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-slate-600 dark:text-slate-400">
                      <span className="text-emerald-500 mt-0.5">•</span>
                      {obs}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {detail.conclusion && (
              <div>
                <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5">Conclusion</div>
                <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed">{detail.conclusion}</p>
              </div>
            )}

            {nearbyText && (
              <div>
                <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5">Nearby Context</div>
                <p className="text-xs text-slate-500 dark:text-slate-500 leading-relaxed line-clamp-4">{nearbyText}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
