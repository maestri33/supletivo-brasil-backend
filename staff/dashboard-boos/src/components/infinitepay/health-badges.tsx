"use client";

import { useQuery } from "@tanstack/react-query";
import { healthCheck, readyCheck } from "@/lib/infinitepay-api";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";

export function HealthBadges() {
  const health = useQuery({
    queryKey: ["infinitepay", "health"],
    queryFn: healthCheck,
    refetchInterval: 30_000,
  });

  const ready = useQuery({
    queryKey: ["infinitepay", "ready"],
    queryFn: readyCheck,
    refetchInterval: 30_000,
  });

  return (
    <div className="flex items-center gap-3">
      <Badge
        label="Health"
        ok={health.data?.ok}
        loading={health.isLoading}
        error={!!health.error}
      />
      <Badge
        label="Ready"
        ok={ready.data?.ok}
        loading={ready.isLoading}
        error={!!ready.error}
      />
    </div>
  );
}

function Badge({
  label,
  ok,
  loading,
  error,
}: {
  label: string;
  ok?: boolean;
  loading: boolean;
  error: boolean;
}) {
  return (
    <div className="inline-flex items-center gap-1.5 rounded-full border border-zinc-200 bg-white px-3 py-1 text-xs font-semibold dark:border-zinc-800 dark:bg-zinc-950">
      {loading ? (
        <Loader2 size={12} className="animate-spin text-zinc-400" />
      ) : error ? (
        <XCircle size={12} className="text-red-500" />
      ) : ok ? (
        <CheckCircle2 size={12} className="text-emerald-500" />
      ) : (
        <XCircle size={12} className="text-amber-500" />
      )}
      <span className="text-zinc-700 dark:text-zinc-300">{label}</span>
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          loading
            ? "bg-zinc-300 animate-pulse"
            : error
              ? "bg-red-500"
              : ok
                ? "bg-emerald-500 animate-pulse"
                : "bg-amber-500"
        }`}
      />
    </div>
  );
}
