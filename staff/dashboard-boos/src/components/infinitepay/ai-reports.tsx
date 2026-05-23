"use client";

import { useState, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { generateReport, type ReportResponse } from "@/lib/infinitepay-api";
import { EndpointSection } from "./endpoint-section";
import {
  FileText,
  CalendarDays,
  CalendarRange,
  Calendar,
  Loader2,
  Clock,
  Cpu,
  Download,
} from "lucide-react";

const kinds = [
  {
    id: "daily" as const,
    label: "Diário",
    icon: Calendar,
    desc: "Resumo de hoje",
    color: "bg-emerald-600 hover:bg-emerald-700",
  },
  {
    id: "weekly" as const,
    label: "Semanal",
    icon: CalendarDays,
    desc: "Últimos 7 dias",
    color: "bg-violet-600 hover:bg-violet-700",
  },
  {
    id: "full" as const,
    label: "Completo",
    icon: CalendarRange,
    desc: "Todo o histórico",
    color: "bg-indigo-600 hover:bg-indigo-700",
  },
];

export function AiReports() {
  const [result, setResult] = useState<ReportResponse | null>(null);
  const [elapsed, setElapsed] = useState(0);

  const mutation = useMutation({
    mutationFn: generateReport,
    onSuccess: (data) => setResult(data),
  });

  useEffect(() => {
    let timer: ReturnType<typeof setInterval>;
    if (mutation.isPending) {
      setElapsed(0);
      timer = setInterval(() => setElapsed((p) => p + 100), 100);
    }
    return () => clearInterval(timer);
  }, [mutation.isPending]);

  return (
    <EndpointSection
      method="POST"
      path="/api/v1/report/"
      description="Gera relatório executivo com IA avançada. Daily = hoje, Weekly = 7 dias, Full = histórico completo."
      error={mutation.error?.message || null}
      onRetry={() => mutation.reset()}
    >
      <div className="space-y-3">
        {/* Kind buttons */}
        <div className="grid grid-cols-3 gap-2">
          {kinds.map((k) => {
            const Icon = k.icon;
            const active = mutation.variables === k.id && mutation.isPending;
            return (
              <button
                key={k.id}
                onClick={() => {
                  setResult(null);
                  mutation.mutate(k.id);
                }}
                disabled={mutation.isPending}
                className={`flex flex-col items-center gap-1 rounded-xl px-3 py-3 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
                  active ? "ring-2 ring-offset-1 ring-violet-400 " + k.color : k.color
                }`}
              >
                {active ? (
                  <Loader2 size={20} className="animate-spin" />
                ) : (
                  <Icon size={20} />
                )}
                <span className="text-xs font-bold">{k.label}</span>
                <span className="text-[9px] opacity-70">{k.desc}</span>
              </button>
            );
          })}
        </div>

        {/* Loading state */}
        {mutation.isPending && (
          <div className="flex items-center justify-center gap-3 py-4 text-sm text-zinc-500">
            <Loader2 size={16} className="animate-spin text-violet-500" />
            Gerando relatório... {(elapsed / 1000).toFixed(1)}s
          </div>
        )}

        {/* Report result */}
        {result && (
          <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 overflow-hidden">
            <div className="flex items-center justify-between border-b border-zinc-100 px-4 py-2.5 dark:border-zinc-800">
              <div className="flex items-center gap-2">
                <FileText size={14} className="text-violet-500" />
                <span className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">
                  Relatório {result.kind || ""}
                </span>
              </div>
              <div className="flex items-center gap-3 text-[10px] text-zinc-400">
                {result.model && (
                  <span className="flex items-center gap-1">
                    <Cpu size={10} /> {result.model}
                  </span>
                )}
                {result.elapsed_ms && (
                  <span className="flex items-center gap-1">
                    <Clock size={10} /> {result.elapsed_ms}ms
                  </span>
                )}
              </div>
            </div>
            <div className="p-4 max-h-96 overflow-y-auto">
              <pre className="text-xs text-zinc-700 dark:text-zinc-300 whitespace-pre-wrap font-sans leading-relaxed">
                {result.report}
              </pre>
            </div>
          </div>
        )}
      </div>
    </EndpointSection>
  );
}
