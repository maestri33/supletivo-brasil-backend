"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { postWebhook, type WebhookResponse } from "@/lib/infinitepay-api";
import { EndpointSection } from "./endpoint-section";
import { Send, Loader2, CheckCircle2, XCircle, Copy } from "lucide-react";

const samplePayload = JSON.stringify(
  {
    event: "payment.succeeded",
    order_nsu: "joao-silva-001",
    status: "paid",
    amount: 10000,
  },
  null,
  2
);

export function WebhookTester() {
  const [externalId, setExternalId] = useState("");
  const [payload, setPayload] = useState(samplePayload);
  const [result, setResult] = useState<WebhookResponse | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => {
      let parsed: unknown;
      try {
        parsed = JSON.parse(payload);
        setParseError(null);
      } catch {
        setParseError("JSON inválido");
        throw new Error("JSON inválido");
      }
      return postWebhook(externalId, parsed);
    },
    onSuccess: (data) => setResult(data),
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setResult(null);
    mutation.mutate();
  }

  return (
    <div className="space-y-3">
      <EndpointSection
        method="POST"
        path="/api/v1/webhook/"
        description="Simula um webhook da InfinitePay. Envia payload JSON com external_id como query param."
        error={mutation.error?.message || null}
        onRetry={() => mutation.reset()}
      >
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-[10px] font-semibold uppercase text-zinc-500 mb-1">
              External ID *
            </label>
            <input
              type="text"
              value={externalId}
              onChange={(e) => setExternalId(e.target.value)}
              placeholder="pedido-123"
              className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs text-zinc-900 placeholder:text-zinc-400 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100 font-mono"
              required
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-[10px] font-semibold uppercase text-zinc-500">
                Payload JSON *
              </label>
              <button
                type="button"
                onClick={() => setPayload(samplePayload)}
                className="text-[10px] text-violet-500 hover:text-violet-600 font-medium"
              >
                <Copy size={10} className="inline mr-0.5" />
                Reset exemplo
              </button>
            </div>
            <textarea
              value={payload}
              onChange={(e) => {
                setPayload(e.target.value);
                setParseError(null);
              }}
              rows={8}
              className={`w-full rounded-lg border px-3 py-2 text-xs font-mono text-zinc-900 placeholder:text-zinc-400 focus:outline-none focus:ring-1 dark:text-zinc-100 dark:bg-zinc-900 resize-y ${
                parseError
                  ? "border-red-300 focus:border-red-500 focus:ring-red-500 dark:border-red-800"
                  : "border-zinc-200 focus:border-violet-500 focus:ring-violet-500 dark:border-zinc-800"
              }`}
            />
            {parseError && (
              <p className="mt-1 text-[10px] text-red-500">{parseError}</p>
            )}
          </div>

          <button
            type="submit"
            disabled={mutation.isPending || !externalId.trim() || !payload.trim()}
            className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-violet-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {mutation.isPending ? (
              <>
                <Loader2 size={16} className="animate-spin" /> Enviando...
              </>
            ) : (
              <>
                <Send size={14} /> Enviar Webhook
              </>
            )}
          </button>
        </form>
      </EndpointSection>

      {/* Result */}
      {result && (
        <div className="rounded-xl border-2 border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950 overflow-hidden">
          <div className="flex items-center gap-2 border-b border-zinc-100 px-4 py-2.5 dark:border-zinc-800">
            <span className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">
              Resposta
            </span>
          </div>
          <div className="p-4 flex items-center gap-6">
            <ResultBadge label="OK" value={result.ok} />
            <ResultBadge label="Pago" value={result.paid} />
            <ResultBadge label="Duplicado" value={result.duplicate} warn />
          </div>
        </div>
      )}
    </div>
  );
}

function ResultBadge({
  label,
  value,
  warn,
}: {
  label: string;
  value: boolean;
  warn?: boolean;
}) {
  return (
    <div className="flex items-center gap-2">
      {value ? (
        warn ? (
          <XCircle size={18} className="text-amber-500" />
        ) : (
          <CheckCircle2 size={18} className="text-emerald-500" />
        )
      ) : (
        <XCircle size={18} className="text-zinc-300 dark:text-zinc-600" />
      )}
      <div>
        <p className="text-xs font-semibold text-zinc-700 dark:text-zinc-300">
          {label}
        </p>
        <p className="text-[10px] text-zinc-400">{value ? "true" : "false"}</p>
      </div>
    </div>
  );
}
