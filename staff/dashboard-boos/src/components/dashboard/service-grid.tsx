"use client";

import { useState } from "react";
import { ServiceCard } from "./service-card";
import { Search, Filter } from "lucide-react";
import { services } from "@/lib/services-registry";
import { CATEGORIES, type Service } from "@/lib/types";

export function ServiceGrid() {
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);

  const filtered = services.filter((s) => {
    if (search) {
      const q = search.toLowerCase();
      if (
        !s.name.toLowerCase().includes(q) &&
        !s.description.toLowerCase().includes(q) &&
        !s.tags.some((t) => t.toLowerCase().includes(q)) &&
        !s.host.includes(q)
      )
        return false;
    }
    if (categoryFilter && s.category !== categoryFilter) return false;
    if (statusFilter && s.status !== statusFilter) return false;
    return true;
  });

  const grouped = filtered.reduce(
    (acc, s) => {
      const cat = s.category || "other";
      if (!acc[cat]) acc[cat] = [];
      acc[cat].push(s);
      return acc;
    },
    {} as Record<string, Service[]>
  );

  return (
    <div className="space-y-6">
      {/* Filters bar */}
      <div className="sticky top-0 z-10 -mx-6 px-6 py-3 bg-zinc-50/80 dark:bg-black/80 backdrop-blur border-b border-zinc-200 dark:border-zinc-800">
        <div className="flex items-center gap-3">
          <div className="relative flex-1 max-w-sm">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar serviço..."
              className="w-full rounded-lg border border-zinc-200 bg-white py-2 pl-9 pr-3 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100"
            />
          </div>

          {/* Status filter */}
          <div className="flex gap-1">
            {[
              { key: null, label: "Todos" },
              { key: "healthy", label: "UP", color: "text-emerald-600 bg-emerald-50 border-emerald-200 dark:text-emerald-400 dark:bg-emerald-950 dark:border-emerald-900" },
              { key: "degraded", label: "DEG", color: "text-amber-600 bg-amber-50 border-amber-200 dark:text-amber-400 dark:bg-amber-950 dark:border-amber-900" },
              { key: "down", label: "DOWN", color: "text-red-600 bg-red-50 border-red-200 dark:text-red-400 dark:bg-red-950 dark:border-red-900" },
              { key: "maintenance", label: "MAN", color: "text-blue-600 bg-blue-50 border-blue-200 dark:text-blue-400 dark:bg-blue-950 dark:border-blue-900" },
            ].map((f) => (
              <button
                key={f.label}
                onClick={() => setStatusFilter(f.key)}
                className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors ${
                  statusFilter === f.key
                    ? f.color || "bg-violet-100 text-violet-700 border-violet-300 dark:bg-violet-950 dark:text-violet-300 dark:border-violet-800"
                    : "border-zinc-200 bg-white text-zinc-500 hover:bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          {/* Category filter */}
          <div className="flex gap-1">
            {Object.values(CATEGORIES).map((cat) => (
              <button
                key={cat.id}
                onClick={() => setCategoryFilter(categoryFilter === cat.id ? null : cat.id)}
                className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                  categoryFilter === cat.id
                    ? "bg-violet-100 text-violet-700 border-violet-300 dark:bg-violet-950 dark:text-violet-300 dark:border-violet-800"
                    : "border-zinc-200 bg-white text-zinc-500 hover:bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800"
                }`}
              >
                {cat.label}
              </button>
            ))}
          </div>

          <span className="ml-auto text-xs text-zinc-400">
            {filtered.length} de {services.length}
          </span>
        </div>
      </div>

      {/* Grid grouped by category */}
      {Object.entries(grouped).map(([catKey, svcs]) => {
        const cat = CATEGORIES[catKey] || CATEGORIES.other;
        return (
          <div key={catKey}>
            <h2 className="mb-3 text-xs font-bold uppercase tracking-wider text-zinc-400">
              {cat.label}
            </h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {svcs.map((s) => (
                <ServiceCard key={s.id} service={s} />
              ))}
            </div>
          </div>
        );
      })}

      {filtered.length === 0 && (
        <div className="flex flex-col items-center py-16 text-zinc-400">
          <Filter size={32} className="mb-2" />
          <p className="text-sm">Nenhum serviço encontrado</p>
          <p className="text-xs">Tente ajustar os filtros</p>
        </div>
      )}
    </div>
  );
}
