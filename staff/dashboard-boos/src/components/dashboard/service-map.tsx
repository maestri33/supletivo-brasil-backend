"use client";

import { Boxes } from "lucide-react";
import type { Service } from "@/lib/types";

export function ServiceMap({ services }: { services: Service[] }) {
  const activeServices = services.filter((s) => s.status !== "maintenance");
  const cols = Math.ceil(Math.sqrt(activeServices.length));

  const colorMap: Record<string, string> = {};
  const palette = [
    "border-violet-400 bg-violet-50 dark:bg-violet-950/50",
    "border-indigo-400 bg-indigo-50 dark:bg-indigo-950/50",
    "border-emerald-400 bg-emerald-50 dark:bg-emerald-950/50",
    "border-amber-400 bg-amber-50 dark:bg-amber-950/50",
    "border-rose-400 bg-rose-50 dark:bg-rose-950/50",
    "border-cyan-400 bg-cyan-50 dark:bg-cyan-950/50",
  ];
  activeServices.forEach((s, i) => {
    colorMap[s.id] = palette[i % palette.length];
  });

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950">
      <h3 className="mb-4 text-sm font-semibold text-zinc-900 dark:text-zinc-100">
        Mapa de Dependências
      </h3>
      <div
        className="grid gap-3"
        style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}
      >
        {activeServices.map((s) => (
          <div
            key={s.id}
            className={`rounded-lg border-2 p-3 transition-colors ${colorMap[s.id] || palette[0]}`}
          >
            <div className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">
              {s.name}
            </div>
            <div className="mt-1 text-xs text-zinc-500">
              {s.dependencies.length > 0
                ? `→ ${s.dependencies.join(", ")}`
                : "sem dependências externas"}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
