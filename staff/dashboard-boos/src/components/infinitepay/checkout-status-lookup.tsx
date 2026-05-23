"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  fetchCheckoutByNsu,
  type CheckoutResponse,
} from "@/lib/infinitepay-api";
import { EndpointSection } from "./endpoint-section";
import { CheckoutDetail } from "./checkout-detail";
import { Search, Loader2 } from "lucide-react";

export function CheckoutStatusLookup() {
  const [orderNsu, setOrderNsu] = useState("");

  const mutation = useMutation({
    mutationFn: (nsu: string) => fetchCheckoutByNsu(nsu),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!orderNsu.trim()) return;
    mutation.mutate(orderNsu.trim());
  }

  return (
    <div className="space-y-3">
      <EndpointSection
        method="GET"
        path="/api/v1/webhook/"
        description="Consulta status de um checkout pelo order_nsu (não altera nada)."
        error={mutation.error?.message || null}
        onRetry={() => mutation.reset()}
      >
        <form onSubmit={handleSubmit} className="flex items-end gap-2">
          <div className="flex-1">
            <label className="block text-[10px] font-semibold uppercase text-zinc-500 mb-1">
              Order NSU *
            </label>
            <input
              type="text"
              value={orderNsu}
              onChange={(e) => setOrderNsu(e.target.value)}
              placeholder="joao-silva-001"
              className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs text-zinc-900 placeholder:text-zinc-400 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100 font-mono"
            />
          </div>
          <button
            type="submit"
            disabled={mutation.isPending || !orderNsu.trim()}
            className="inline-flex items-center gap-1.5 rounded-lg bg-violet-600 px-3 py-2 text-xs font-semibold text-white hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
          >
            {mutation.isPending ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Search size={14} />
            )}
            Buscar
          </button>
        </form>
      </EndpointSection>

      {mutation.data && (
        <CheckoutDetail checkout={mutation.data} />
      )}
    </div>
  );
}
