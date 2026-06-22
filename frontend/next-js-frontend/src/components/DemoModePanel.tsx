"use client";

import { useEffect, useState } from "react";
import {
  Zap, AlertTriangle, FileText, BarChart3, HelpCircle, Loader2,
} from "lucide-react";
import { getDemoQuestions } from "@/lib/api";

type DemoQuestion = {
  id: string;
  label: string;
  description: string;
  query: string;
  doc_id: string;
  category: "factual" | "risk";
  expects_risk_radar?: boolean;
};

type Props = {
  targetDoc: string;
  loading: boolean;
  refreshKey?: number;
  onSelect: (query: string, docId: string) => void;
};

function QuestionIcon({ q }: { q: DemoQuestion }) {
  if (q.category === "risk") return <AlertTriangle className="w-3.5 h-3.5" />;
  if (/table|figure|chart/i.test(q.label + q.query)) return <BarChart3 className="w-3.5 h-3.5" />;
  if (/summar|overview/i.test(q.label + q.query)) return <FileText className="w-3.5 h-3.5" />;
  return <HelpCircle className="w-3.5 h-3.5" />;
}

export default function DemoModePanel({ targetDoc, loading, refreshKey = 0, onSelect }: Props) {
  const [questions, setQuestions] = useState<DemoQuestion[]>([]);
  const [fetching, setFetching] = useState(false);

  const docId = targetDoc ? targetDoc.replace(/\.(pdf|docx)$/i, "") : null;

  useEffect(() => {
    if (!docId) {
      setQuestions([]);
      setFetching(false);
      return;
    }

    let cancelled = false;
    let attempts = 0;
    const maxAttempts = 40;

    const poll = async () => {
      if (cancelled) return;
      try {
        const res = await getDemoQuestions(docId);
        if (cancelled) return;
        if (res.questions?.length) {
          setQuestions(res.questions);
          setFetching(false);
          return;
        }
        if (res.status === "failed") {
          setQuestions([]);
          setFetching(false);
          return;
        }
      } catch {
        if (!cancelled) setFetching(false);
        return;
      }
      attempts += 1;
      if (attempts < maxAttempts && !cancelled) {
        setTimeout(poll, 2500);
      } else if (!cancelled) {
        setFetching(false);
      }
    };

    setFetching(true);
    setQuestions([]);
    poll();
    return () => { cancelled = true; };
  }, [docId, refreshKey]);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Zap className="w-4 h-4 text-amber-500" />
        <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
          Demo Mode
        </h4>
      </div>

      {!docId ? (
        <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
          Upload a PDF — we&apos;ll auto-generate tailored one-click questions for that document.
        </p>
      ) : fetching ? (
        <div className="flex items-center gap-2 text-[11px] text-slate-500 py-2">
          <Loader2 className="w-3.5 h-3.5 animate-spin text-amber-500" />
          Generating questions for this document...
        </div>
      ) : questions.length === 0 ? (
        <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
          No demo questions yet. Re-upload the document or wait for ingestion to finish.
        </p>
      ) : (
        <>
          <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
            {questions.length} tailored questions for{" "}
            <span className="font-semibold text-slate-600 dark:text-slate-300">{targetDoc}</span>
          </p>
          <div className="space-y-2">
            {questions.map((q) => (
              <button
                key={q.id}
                type="button"
                disabled={loading}
                onClick={() => onSelect(q.query, q.doc_id)}
                className={`w-full text-left p-3 rounded-xl border transition-all group disabled:opacity-50 ${
                  q.category === "risk"
                    ? "border-red-200/60 dark:border-red-500/20 bg-red-50/30 dark:bg-red-500/5 hover:border-red-400 dark:hover:border-red-500/40 hover:bg-red-50 dark:hover:bg-red-500/10"
                    : "border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-[#0B0F14] hover:border-emerald-400 dark:hover:border-emerald-500/40 hover:bg-emerald-50/50 dark:hover:bg-emerald-500/5"
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className={q.category === "risk" ? "text-red-500" : "text-emerald-500"}>
                    <QuestionIcon q={q} />
                  </span>
                  <span className="text-xs font-bold text-slate-700 dark:text-slate-200 group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors line-clamp-1">
                    {q.label}
                  </span>
                  {q.expects_risk_radar && (
                    <span className="ml-auto shrink-0 text-[8px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-red-100 dark:bg-red-500/15 text-red-600 dark:text-red-400">
                      Risk
                    </span>
                  )}
                </div>
                <p className="text-[10px] text-slate-500 dark:text-slate-400 pl-5 line-clamp-2">
                  {q.description}
                </p>
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
