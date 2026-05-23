"use client";

import {
  Server,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Wrench,
} from "lucide-react";
import type { Service } from "@/lib/types";

const statusConfig = {
  healthy: {
    icon: CheckCircle2,
    label: "UP",
    bg: "bg-emerald-50 dark:bg-emerald-950",
    text: "text-emerald-700 dark:text-emerald-300",
    dot: "bg-emerald-500",
  },
  degraded: {
    icon: AlertTriangle,
    label: "DEG",
    bg: "bg-amber-50 dark:bg-amber-950",
    text: "text-amber-700 dark:text-amber-300",
    dot: "bg-amber-500",
  },
  down: {
    icon: XCircle,
    label: "DOWN",
    bg: "bg-red-50 dark:bg-red-950",
    text: "text-red-700 dark:text-red-300",
    dot: "bg-red-500",
  },
  maintenance: {
    icon: Wrench,
    label: "MAINT",
    bg: "bg-blue-50 dark:bg-blue-950",
    text: "text-blue-700 dark:text-blue-300",
    dot: "bg-blue-500",
  },
};

export function HealthCards({ services }: { services: Service[] }) {
  const counts = {
    healthy: services.filter((s) => s.status === "healthy").length,
    degraded: services.filter((s) => s.status === "degraded").length,
    down: services.filter((s) => s.status === "down").length,
    maintenance: services.filter((s) => s.status === "maintenance").length,
  };

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      {(Object.keys(statusConfig) as Array<keyof typeof statusConfig>).map(
        (status) => {
          const config = statusConfig[status];
          const Icon = config.icon;
          return (
            <div
              key={status}
              className={`flex items-center gap-4 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800 ${config.bg}`}
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-white/60 dark:bg-black/20">
                <Icon size={22} className={config.text} />
              </div>
              <div>
                <div className={`text-2xl font-bold ${config.text}`}>
                  {counts[status]}
                </div>
                <div className={`text-xs font-medium ${config.text}`}>
                  {config.label}
                </div>
              </div>
            </div>
          );
        }
      )}
    </div>
  );
}
