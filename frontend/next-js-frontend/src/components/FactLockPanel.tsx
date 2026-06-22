"use client";

import { ShieldCheck, ShieldAlert, ShieldQuestion } from "lucide-react";

export type FactLockData = {
  status: "verified" | "partial" | "unverified" | "narrative";
  score: number;
  total_claims: number;
  verified_count: number;
  verified: Array<{
    value: string;
    type: string;
    verified: boolean;
    page?: number | string;
    snippet?: string;
  }>;
  unverified: Array<{
    value: string;
    type: string;
    verified: boolean;
  }>;
};

type Props = {
  factLock?: FactLockData | null;
  onViewPage?: (page: number | string) => void;
};

export default function FactLockPanel({ factLock, onViewPage }: Props) {
  if (!factLock) return null;

  const { status, score, total_claims, verified_count, verified, unverified } = factLock;

  if (status === "narrative" && total_claims === 0) {
    return (
      <div className="mt-4 flex items-center gap-2 px-3 py-2 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700">
        <ShieldQuestion className="w-4 h-4 text-slate-400 shrink-0" />
        <span className="text-xs text-slate-500 dark:text-slate-400">
          Fact Lock — narrative answer (no numeric claims to verify)
        </span>
      </div>
    );
  }

  const allVerified = status === "verified";
  const partial = status === "partial";

  return (
    <div className={`mt-4 rounded-xl border overflow-hidden ${
      allVerified
        ? "border-emerald-200 dark:border-emerald-500/30 bg-emerald-50/50 dark:bg-emerald-500/5"
        : partial
          ? "border-amber-200 dark:border-amber-500/30 bg-amber-50/50 dark:bg-amber-500/5"
          : "border-red-200 dark:border-red-500/30 bg-red-50/50 dark:bg-red-500/5"
    }`}>
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-inherit">
        <div className="flex items-center gap-2">
          {allVerified ? (
            <ShieldCheck className="w-4 h-4 text-emerald-500" />
          ) : (
            <ShieldAlert className={`w-4 h-4 ${partial ? "text-amber-500" : "text-red-500"}`} />
          )}
          <span className="text-[10px] font-bold uppercase tracking-widest text-slate-600 dark:text-slate-300">
            Fact Lock
          </span>
        </div>
        <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${
          allVerified
            ? "bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400"
            : partial
              ? "bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-400"
              : "bg-red-100 dark:bg-red-500/20 text-red-700 dark:text-red-400"
        }`}>
          {verified_count}/{total_claims} verified · {Math.round(score * 100)}%
        </span>
      </div>

      <div className="p-3 flex flex-wrap gap-2">
        {verified.map((f, i) => (
          <button
            key={`v-${i}`}
            type="button"
            onClick={() => f.page && onViewPage?.(f.page)}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold
              bg-emerald-100 dark:bg-emerald-500/15 text-emerald-800 dark:text-emerald-300
              border border-emerald-200 dark:border-emerald-500/25 hover:bg-emerald-200/80 dark:hover:bg-emerald-500/25 transition-colors"
            title={f.snippet || undefined}
          >
            <ShieldCheck className="w-3 h-3 shrink-0" />
            <span>{f.value}</span>
            {f.page != null && (
              <span className="text-[10px] font-normal opacity-70">p.{f.page}</span>
            )}
          </button>
        ))}
        {unverified.map((f, i) => (
          <span
            key={`u-${i}`}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold
              bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400
              border border-slate-200 dark:border-slate-700"
          >
            <ShieldAlert className="w-3 h-3 shrink-0 opacity-60" />
            {f.value}
            <span className="text-[10px] font-normal opacity-60">unverified</span>
          </span>
        ))}
      </div>
    </div>
  );
}
