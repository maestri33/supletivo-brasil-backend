"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchConfig, patchConfig, type ConfigResponse } from "@/lib/infinitepay-api";
import { EndpointSection } from "./endpoint-section";
import { Save, Loader2, CheckCircle2 } from "lucide-react";

export function ConfigEditor() {
  const queryClient = useQueryClient();
  const [saved, setSaved] = useState(false);

  const q = useQuery({
    queryKey: ["infinitepay", "config"],
    queryFn: fetchConfig,
  });

  const [form, setForm] = useState<Record<string, string>>({});

  useEffect(() => {
    if (q.data) {
      setForm({
        handle: q.data.handle || "",
        price: q.data.price?.toString() || "",
        quantity: q.data.quantity?.toString() || "1",
        description: q.data.description || "",
        redirect_url: q.data.redirect_url || "",
        backend_webhook: q.data.backend_webhook || "",
        public_api_url: q.data.public_api_url || "",
      });
    }
  }, [q.data]);

  const mutation = useMutation({
    mutationFn: () => {
      const body: Record<string, unknown> = {};
      if (form.handle !== (q.data?.handle || "")) body.handle = form.handle || null;
      if (form.price !== (q.data?.price?.toString() || ""))
        body.price = form.price ? Number(form.price) : null;
      if (form.quantity !== (q.data?.quantity?.toString() || "1"))
        body.quantity = form.quantity ? Number(form.quantity) : null;
      if (form.description !== (q.data?.description || ""))
        body.description = form.description || null;
      if (form.redirect_url !== (q.data?.redirect_url || ""))
        body.redirect_url = form.redirect_url || null;
      if (form.backend_webhook !== (q.data?.backend_webhook || ""))
        body.backend_webhook = form.backend_webhook || null;
      if (form.public_api_url !== (q.data?.public_api_url || ""))
        body.public_api_url = form.public_api_url || null;
      return patchConfig(body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["infinitepay", "config"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    },
  });

  const fields = [
    { key: "handle", label: "Handle", placeholder: "minha-loja" },
    { key: "price", label: "Preço padrão (centavos)", placeholder: "10000", type: "number" },
    { key: "quantity", label: "Quantidade padrão", placeholder: "1", type: "number" },
    { key: "description", label: "Descrição", placeholder: "Produto XYZ" },
    { key: "redirect_url", label: "URL de redirect", placeholder: "https://..." },
    { key: "backend_webhook", label: "URL do webhook backend", placeholder: "https://..." },
    { key: "public_api_url", label: "URL pública da API", placeholder: "https://..." },
  ];

  const changed =
    q.data &&
    fields.some(
      (f) => form[f.key] !== (q.data[f.key as keyof ConfigResponse]?.toString() || "")
    );

  return (
    <EndpointSection
      method="GET/PATCH"
      path="/api/v1/config/"
      description="Configuração global: defaults para checkouts e URLs de webhook"
      isLoading={q.isLoading}
      error={q.error?.message || mutation.error?.message || null}
      onRetry={() => { q.refetch(); mutation.reset(); }}
      isEmpty={false}
    >
      <div className="space-y-3">
        {fields.map((f) => (
          <div key={f.key}>
            <label className="block text-[10px] font-semibold uppercase text-zinc-500 mb-1">
              {f.label}
            </label>
            <input
              type={f.type || "text"}
              value={form[f.key] || ""}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, [f.key]: e.target.value }))
              }
              placeholder={f.placeholder}
              className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs text-zinc-900 placeholder:text-zinc-400 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100"
            />
          </div>
        ))}

        <button
          onClick={() => mutation.mutate()}
          disabled={!changed || mutation.isPending}
          className={`inline-flex w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold transition-colors ${
            saved
              ? "bg-emerald-600 text-white"
              : "bg-violet-600 text-white hover:bg-violet-700"
          } disabled:opacity-50 disabled:cursor-not-allowed`}
        >
          {mutation.isPending ? (
            <>
              <Loader2 size={16} className="animate-spin" /> Salvando...
            </>
          ) : saved ? (
            <>
              <CheckCircle2 size={16} /> Salvo!
            </>
          ) : (
            <>
              <Save size={14} /> Salvar alterações
            </>
          )}
        </button>

        {q.data?.updated_at && (
          <p className="text-[10px] text-zinc-400 text-center">
            Última atualização: {new Date(q.data.updated_at).toLocaleString("pt-BR")}
          </p>
        )}
      </div>
    </EndpointSection>
  );
}
