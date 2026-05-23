"use client";

import { ScrollText, Info, AlertTriangle, XCircle } from "lucide-react";
import type { LogEntry } from "@/lib/types";

const levelStyle = {
  INFO: {
    icon: Info,
    bg: "bg-emerald-50 dark:bg-emerald-950",
    text: "text-emerald-600 dark:text-emerald-400",
    badge: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300",
  },
  WARN: {
    icon: AlertTriangle,
    bg: "bg-amber-50 dark:bg-amber-950",
    text: "text-amber-600 dark:text-amber-400",
    badge: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
  },
  ERROR: {
    icon: XCircle,
    bg: "bg-red-50 dark:bg-red-950",
    text: "text-red-600 dark:text-red-400",
    badge: "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300",
  },
  DEBUG: {
    icon: Info,
    bg: "bg-zinc-50 dark:bg-zinc-950",
    text: "text-zinc-600 dark:text-zinc-400",
    badge: "bg-zinc-100 text-zinc-700 dark:bg-zinc-900 dark:text-zinc-300",
  },
};

export function LogViewer({ logs }: { logs: LogEntry[] }) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex items-center justify-between border-b border-zinc-200 px-5 py-3 dark:border-zinc-800">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
          Logs Recentes
        </h3>
        <span className="text-xs text-zinc-500">últimos {logs.length} eventos</span>
      </div>
      <div className="divide-y divide-zinc-100 dark:divide-zinc-900">
        {logs.map((log) => {
          const style = levelStyle[log.level];
          const Icon = style.icon;
          return (
            <div
              key={log.id}
              className="flex items-start gap-3 px-5 py-2.5 text-sm"
            >
              <Icon size={16} className={`mt-0.5 shrink-0 ${style.text}`} />
              <div className="flex-1 min-w-0">
                <span className="text-zinc-900 dark:text-zinc-100">
                  {log.message}
                </span>
                <div className="mt-0.5 flex items-center gap-2 text-xs text-zinc-500">
                  <span
                    className={`rounded px-1.5 py-0.5 font-medium ${style.badge}`}
                  >
                    {log.level}
                  </span>
                  <span>{log.serviceId}</span>
                  <span>
                    {new Date(log.timestamp).toLocaleTimeString("pt-BR")}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
