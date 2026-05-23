"use client";

import { useState } from "react";
import {
  Copy,
  Check,
  ExternalLink,
  X,
  CreditCard,
  Hash,
  Calendar,
  Link2,
  Receipt,
  Tag,
} from "lucide-react";
import type { CheckoutResponse } from "@/lib/infinitepay-api";

export function CheckoutDetail({
  checkout: c,
  onClose,
}: {
  checkout: CheckoutResponse;
  onClose?: () => void;
}) {
  return (
    <div className="rounded-xl border-2 border-violet-200 bg-white dark:border-violet-800 dark:bg-zinc-950 overflow-hidden">
      <div className="flex items-center justify-between border-b border-violet-100 px-4 py-2.5 dark:border-violet-900/50">
        <div className="flex items-center gap-2">
          <Hash size={14} className="text-violet-500" />
          <span className="text-sm font-mono font-bold text-zinc-800 dark:text-zinc-200">
            {c.external_id}
          </span>
          <span
            className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
              c.is_paid
                ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                : "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300"
            }`}
          >
            {c.is_paid ? "PAGO" : "PENDENTE"}
          </span>
        </div>
        {onClose && (
          <button onClick={onClose} className="text-zinc-400 hover:text-zinc-600">
            <X size={16} />
          </button>
        )}
      </div>

      <div className="p-4 grid grid-cols-2 gap-3">
        {c.checkout_url && (
          <UrlField icon={Link2} label="Checkout URL" url={c.checkout_url} />
        )}
        {c.receipt_url && (
          <UrlField icon={Receipt} label="Receipt URL" url={c.receipt_url} />
        )}
        {c.invoice_slug && (
          <Field icon={Tag} label="Invoice Slug" value={c.invoice_slug} />
        )}
        {c.transaction_nsu && (
          <Field icon={Hash} label="NSU" value={c.transaction_nsu} mono />
        )}
        {c.capture_method && (
          <Field icon={CreditCard} label="Captura" value={c.capture_method} />
        )}
        {c.installments && (
          <Field icon={CreditCard} label="Parcelas" value={`${c.installments}x`} />
        )}
        {c.created_at && (
          <Field
            icon={Calendar}
            label="Criado em"
            value={new Date(c.created_at).toLocaleString("pt-BR")}
          />
        )}
        {c.updated_at && (
          <Field
            icon={Calendar}
            label="Atualizado em"
            value={new Date(c.updated_at).toLocaleString("pt-BR")}
          />
        )}
      </div>
    </div>
  );
}

function Field({
  icon: Icon,
  label,
  value,
  mono,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-start gap-2">
      <Icon size={14} className="text-zinc-400 shrink-0 mt-0.5" />
      <div className="min-w-0">
        <p className="text-[10px] font-semibold uppercase text-zinc-400">
          {label}
        </p>
        <p
          className={`text-xs text-zinc-700 dark:text-zinc-300 truncate ${
            mono ? "font-mono" : ""
          }`}
        >
          {value}
        </p>
      </div>
    </div>
  );
}

function UrlField({
  icon: Icon,
  label,
  url,
}: {
  icon: React.ElementType;
  label: string;
  url: string;
}) {
  const [copied, setCopied] = useState(false);

  function copy() {
    navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="col-span-2 flex items-start gap-2">
      <Icon size={14} className="text-zinc-400 shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <p className="text-[10px] font-semibold uppercase text-zinc-400">
          {label}
        </p>
        <div className="flex items-center gap-1 mt-0.5">
          <a
            href={url}
            target="_blank"
            rel="noopener"
            className="text-xs text-violet-600 dark:text-violet-400 hover:underline truncate font-mono"
          >
            {url}
          </a>
          <button onClick={copy} className="text-zinc-400 hover:text-violet-500 shrink-0">
            {copied ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
          </button>
          <a href={url} target="_blank" rel="noopener" className="text-zinc-400 hover:text-violet-500 shrink-0">
            <ExternalLink size={12} />
          </a>
        </div>
      </div>
    </div>
  );
}
