"use client";

import { useEffect, useRef, useState } from "react";
import * as pdfjs from "pdfjs-dist";
import { Loader2, ExternalLink } from "lucide-react";

const API_URL = "http://localhost:8000";

export type PdfSectionHighlight = {
  docId: string;
  page: number;
  bbox?: number[];
  pageHeight?: number;
  searchText?: string;
  label?: string;
};

type Props = {
  highlight: PdfSectionHighlight;
};

function configureWorker() {
  if (typeof window === "undefined") return;
  pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
}

function buildIframeUrl(highlight: PdfSectionHighlight) {
  const search = highlight.searchText || highlight.label || "";
  const clean = search.replace(/[\r\n]+/g, " ").trim().slice(0, 80);
  const searchQuery = clean ? `&search=${encodeURIComponent(`"${clean}"`)}` : "";
  return `${API_URL}/document/file/${encodeURIComponent(highlight.docId)}.pdf#page=${highlight.page}${searchQuery}`;
}

export default function PdfSectionViewer({ highlight }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [useFallback, setUseFallback] = useState(false);
  const [scale, setScale] = useState(1);

  useEffect(() => {
    configureWorker();
  }, []);

  useEffect(() => {
    if (useFallback) return;

    let cancelled = false;

    async function render() {
      setLoading(true);
      setError(null);
      try {
        const url = `${API_URL}/document/file/${encodeURIComponent(highlight.docId)}.pdf`;
        const pdf = await pdfjs.getDocument({ url, withCredentials: false }).promise;
        const pageNum = Math.min(Math.max(highlight.page, 1), pdf.numPages);
        const page = await pdf.getPage(pageNum);

        const containerWidth = wrapRef.current?.clientWidth || 640;
        const baseViewport = page.getViewport({ scale: 1 });
        const fitScale = (containerWidth - 32) / baseViewport.width;
        const viewport = page.getViewport({ scale: fitScale * scale });

        const canvas = canvasRef.current;
        if (!canvas || cancelled) return;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        canvas.width = viewport.width;
        canvas.height = viewport.height;

        await page.render({ canvasContext: ctx, viewport, canvas }).promise;

        if (highlight.bbox && highlight.bbox.length === 4) {
          const [x0, y0, x1, y1] = highlight.bbox;
          const sx = viewport.width / baseViewport.width;
          const sy = viewport.height / baseViewport.height;
          ctx.save();
          ctx.fillStyle = "rgba(250, 204, 21, 0.38)";
          ctx.strokeStyle = "rgba(245, 158, 11, 0.9)";
          ctx.lineWidth = 2;
          const rx = x0 * sx;
          const ry = y0 * sy;
          const rw = (x1 - x0) * sx;
          const rh = (y1 - y0) * sy;
          ctx.fillRect(rx, ry, rw, rh);
          ctx.strokeRect(rx, ry, rw, rh);
          ctx.restore();
        }
      } catch (err) {
        if (!cancelled) {
          console.warn("PDF.js render failed, using iframe fallback:", err);
          setUseFallback(true);
          setError(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    render();
    return () => { cancelled = true; };
  }, [highlight, scale, useFallback]);

  const iframeUrl = buildIframeUrl(highlight);

  if (useFallback) {
    return (
      <div className="flex-1 flex flex-col min-h-0 bg-slate-100 dark:bg-[#0B0F14]">
        <div className="px-4 py-2 flex items-center justify-between border-b border-slate-200 dark:border-slate-800 flex-shrink-0">
          <div>
            <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
              Page {highlight.page}{highlight.label ? ` · ${highlight.label}` : ""}
            </div>
            <div className="text-[10px] text-slate-500">Browser PDF viewer (search highlight)</div>
          </div>
          <a
            href={iframeUrl}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1 text-[10px] font-bold text-sky-500 uppercase"
          >
            <ExternalLink className="w-3 h-3" /> Open
          </a>
        </div>
        <iframe src={iframeUrl} className="flex-1 w-full border-none" title="PDF viewer" />
      </div>
    );
  }

  return (
    <div ref={wrapRef} className="flex-1 overflow-auto p-4 flex flex-col items-center gap-3 bg-slate-100 dark:bg-[#0B0F14]">
      <div className="w-full flex items-center justify-between gap-2 flex-shrink-0">
        <div className="min-w-0">
          <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
            Page {highlight.page}
            {highlight.label ? ` · ${highlight.label}` : ""}
          </div>
          {highlight.bbox ? (
            <div className="text-[10px] text-amber-600 dark:text-amber-400 font-medium">
              Section highlighted
            </div>
          ) : null}
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          <button
            type="button"
            onClick={() => setScale((s) => Math.max(0.5, s - 0.15))}
            className="px-2 py-1 text-xs font-bold rounded-lg border border-slate-300 dark:border-slate-600 hover:bg-white dark:hover:bg-slate-800"
          >
            −
          </button>
          <span className="text-[10px] font-mono text-slate-500 w-10 text-center">
            {Math.round(scale * 100)}%
          </span>
          <button
            type="button"
            onClick={() => setScale((s) => Math.min(2.5, s + 0.15))}
            className="px-2 py-1 text-xs font-bold rounded-lg border border-slate-300 dark:border-slate-600 hover:bg-white dark:hover:bg-slate-800"
          >
            +
          </button>
        </div>
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-slate-500 py-12">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span className="text-sm">Loading PDF page...</span>
        </div>
      )}

      {error && (
        <div className="text-sm text-red-500 py-8">{error}</div>
      )}

      <canvas
        ref={canvasRef}
        className={`shadow-xl rounded-lg border border-slate-200 dark:border-slate-700 max-w-full ${loading ? "hidden" : ""}`}
      />
    </div>
  );
}
