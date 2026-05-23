"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchCheckouts, type CheckoutResponse } from "@/lib/infinitepay-api";
import { EndpointSection } from "./endpoint-section";
import { CheckoutDetail } from "./checkout-detail";
import {
  Search,
  RefreshCw,
  CheckCircle2,
  Clock,
  ChevronRight,
} from "lucide-react";

export function CheckoutTable() {
  const [search, setSearch] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const q = useQuery({
    queryKey: ["infinitepay", "checkouts"],
    queryFn: fetchCheckouts,
    refetchInterval: autoRefresh ? 15_000 : false,
  });

  const items = q.data?.items || [];
  const filtered = search
    ? items.filter((c) =>
        c.external_id.toLowerCase().includes(search.toLowerCase())
      )
    : items;

  const selected = items.find((c) => c.external_id === selectedId) || null;

  return (
    <div className="space-y-3">
      {/* Toolbar */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search
            size={14}
            className="absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-400"
          />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filtrar por external_id..."
            className="w-full rounded-lg border border-zinc-200 bg-white py-1.5 pl-8 pr-3 text-xs text-zinc-900 placeholder:text-zinc-400 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100"
          />
        </div>
        <button
          onClick={() => setAutoRefresh(!autoRefresh)}
          className={`inline-flex items-center gap-1 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors ${
            autoRefresh
              ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
              : "border-zinc-200 bg-white text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400"
          }`}
        >
          <RefreshCw size={12} className={autoRefresh ? "animate-spin" : ""} />
          {autoRefresh ? "Auto" : "Pausado"}
        </button>
        <span className="text-[10px] text-zinc-400">
          {items.length} total
        </span>
      </div>

      <EndpointSection
        method="GET"
        path="/api/v1/checkout/"
        description="Lista todos os checkouts, do mais recente ao mais antigo"
        isLoading={q.isLoading}
        error={q.error?.message || null}
        isEmpty={!q.isLoading && !q.error && filtered.length === 0}
        emptyMessage="Nenhum checkout encontrado. Crie um no formulário ao lado."
        onRetry={() => q.refetch()}
      >
        <div className="space-y-1 max-h-80 overflow-y-auto">
          {filtered.map((c) => (
            <button
              key={c.external_id}
              onClick={() =>
                setSelectedId(selectedId === c.external_id ? null : c.external_id)
              }
              className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors ${
                selectedId === c.external_id
                  ? "bg-violet-50 dark:bg-violet-950/40"
                  : "hover:bg-zinc-50 dark:hover:bg-zinc-900/50"
              }`}
            >
              <span className="shrink-0">
                {c.is_paid ? (
                  <CheckCircle2 size={15} className="text-emerald-500" />
                ) : (
                  <Clock size={15} className="text-amber-500" />
                )}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-mono font-medium text-zinc-800 dark:text-zinc-200 truncate">
                  {c.external_id}
                </p>
                {c.created_at && (
                  <p className="text-[10px] text-zinc-400">
                    {new Date(c.created_at).toLocaleString("pt-BR")}
                  </p>
                )}
              </div>
              <span
                className={`rounded-full px-2 py-0.5 text-[10px] font-semibold shrink-0 ${
                  c.is_paid
                    ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                    : "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300"
                }`}
              >
                {c.is_paid ? "PAGO" : "PENDENTE"}
              </span>
              {c.installments && (
                <span className="text-[10px] text-zinc-400">
                  {c.installments}x
                </span>
              )}
              <ChevronRight size={12} className="text-zinc-300" />
            </button>
          ))}
        </div>
      </EndpointSection>

      {/* Selected detail */}
      {selected && (
        <CheckoutDetail checkout={selected} onClose={() => setSelectedId(null)} />
      )}
    </div>
  );
}
