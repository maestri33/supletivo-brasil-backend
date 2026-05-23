"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createCheckout, type CheckoutResponse } from "@/lib/infinitepay-api";
import { EndpointSection } from "./endpoint-section";
import {
  Send,
  CheckCircle2,
  Copy,
  Check,
  ExternalLink,
  Loader2,
} from "lucide-react";

interface FormData {
  external_id: string;
  name: string;
  email: string;
  phone_number: string;
}

const initial: FormData = {
  external_id: "",
  name: "",
  email: "",
  phone_number: "",
};

export function CreateCheckoutForm() {
  const [form, setForm] = useState<FormData>(initial);
  const [result, setResult] = useState<CheckoutResponse | null>(null);
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (data: FormData) =>
      createCheckout({
        external_id: data.external_id,
        customer: {
          name: data.name,
          email: data.email,
          phone_number: data.phone_number,
        },
      }),
    onSuccess: (data) => {
      setResult(data);
      queryClient.invalidateQueries({ queryKey: ["infinitepay", "checkouts"] });
    },
  });

  const errors = validate(form);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (Object.keys(errors).length > 0) return;
    setResult(null);
    mutation.mutate(form);
  }

  function update(field: keyof FormData, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  return (
    <div className="space-y-3">
      <EndpointSection
        method="POST"
        path="/api/v1/checkout/"
        description="Cria um link de pagamento InfinitePay. Campos não informados usam defaults do /config/."
        error={mutation.error?.message || null}
        onRetry={() => mutation.reset()}
      >
        <form onSubmit={handleSubmit} className="space-y-3">
          <InputField
            label="External ID *"
            value={form.external_id}
            onChange={(v) => update("external_id", v)}
            error={errors.external_id}
            placeholder="pedido-123"
          />
          <InputField
            label="Nome do cliente *"
            value={form.name}
            onChange={(v) => update("name", v)}
            error={errors.name}
            placeholder="João Silva"
          />
          <InputField
            label="Email *"
            value={form.email}
            onChange={(v) => update("email", v)}
            error={errors.email}
            placeholder="joao@email.com"
            type="email"
          />
          <InputField
            label="Telefone *"
            value={form.phone_number}
            onChange={(v) => update("phone_number", v)}
            error={errors.phone_number}
            placeholder="+5511999999999"
          />

          <button
            type="submit"
            disabled={mutation.isPending || Object.keys(errors).length > 0}
            className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-violet-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {mutation.isPending ? (
              <>
                <Loader2 size={16} className="animate-spin" /> Criando...
              </>
            ) : (
              <>
                <Send size={14} /> Criar Checkout
              </>
            )}
          </button>
        </form>
      </EndpointSection>

      {/* Success result */}
      {result && (
        <div className="rounded-xl border-2 border-emerald-200 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-950/50 overflow-hidden">
          <div className="flex items-center gap-2 border-b border-emerald-200 px-4 py-2.5 dark:border-emerald-800">
            <CheckCircle2 size={16} className="text-emerald-600 dark:text-emerald-400" />
            <span className="text-sm font-semibold text-emerald-700 dark:text-emerald-300">
              Checkout criado!
            </span>
          </div>
          <div className="p-4 space-y-2">
            <p className="text-xs font-mono text-zinc-700 dark:text-zinc-300">
              {result.external_id}
            </p>
            {result.checkout_url && (
              <CopyUrl label="Checkout URL" url={result.checkout_url} />
            )}
            {result.receipt_url && (
              <CopyUrl label="Receipt URL" url={result.receipt_url} />
            )}
            {!result.checkout_url && !result.receipt_url && (
              <p className="text-xs text-zinc-500">Aguardando processamento...</p>
            )}
            <button
              onClick={() => {
                setResult(null);
                setForm(initial);
                mutation.reset();
              }}
              className="text-xs font-medium text-violet-600 hover:text-violet-700 dark:text-violet-400"
            >
              Criar outro →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function InputField({
  label,
  value,
  onChange,
  error,
  placeholder,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  error?: string;
  placeholder?: string;
  type?: string;
}) {
  return (
    <div>
      <label className="block text-[10px] font-semibold uppercase text-zinc-500 mb-1">
        {label}
      </label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={`w-full rounded-lg border px-3 py-2 text-xs text-zinc-900 placeholder:text-zinc-400 focus:outline-none focus:ring-1 dark:text-zinc-100 dark:bg-zinc-900 ${
          error
            ? "border-red-300 focus:border-red-500 focus:ring-red-500 dark:border-red-800"
            : "border-zinc-200 focus:border-violet-500 focus:ring-violet-500 dark:border-zinc-800"
        }`}
      />
      {error && (
        <p className="mt-1 text-[10px] text-red-500">{error}</p>
      )}
    </div>
  );
}

function CopyUrl({ label, url }: { label: string; url: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[10px] text-zinc-500">{label}:</span>
      <a
        href={url}
        target="_blank"
        rel="noopener"
        className="text-xs text-violet-600 dark:text-violet-400 font-mono truncate hover:underline"
      >
        {url}
      </a>
      <button
        onClick={() => {
          navigator.clipboard.writeText(url);
          setCopied(true);
          setTimeout(() => setCopied(false), 2000);
        }}
        className="text-zinc-400 hover:text-violet-500 shrink-0"
      >
        {copied ? <Check size={11} className="text-emerald-500" /> : <Copy size={11} />}
      </button>
      <a href={url} target="_blank" rel="noopener" className="text-zinc-400 hover:text-violet-500 shrink-0">
        <ExternalLink size={11} />
      </a>
    </div>
  );
}

function validate(d: FormData): Partial<Record<keyof FormData, string>> {
  const e: Partial<Record<keyof FormData, string>> = {};
  if (!d.external_id.trim()) e.external_id = "Obrigatório";
  if (!d.name.trim()) e.name = "Obrigatório";
  if (!d.email.trim()) e.email = "Obrigatório";
  else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(d.email)) e.email = "Email inválido";
  if (!d.phone_number.trim()) e.phone_number = "Obrigatório";
  return e;
}
