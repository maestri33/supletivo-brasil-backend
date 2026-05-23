"use client";

import { ExternalLink, Gauge, Clock, Cpu, HardDrive } from "lucide-react";
import type { Service } from "@/lib/types";

const statusBadge = {
  healthy:
    "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  degraded:
    "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  down: "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300",
  maintenance:
    "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
};

const statusLabel = {
  healthy: "UP",
  degraded: "DEG",
  down: "DOWN",
  maintenance: "MAN",
};

function StatusDot({ status }: { status: Service["status"] }) {
  const colors = {
    healthy: "bg-emerald-500",
    degraded: "bg-amber-500",
    down: "bg-red-500",
    maintenance: "bg-blue-500",
  };
  const anim = status === "healthy" ? "animate-pulse" : "";
  return <span className={`inline-block h-2 w-2 rounded-full ${colors[status]} ${anim}`} />;
}

export function ServicesTable({ services }: { services: Service[] }) {
  return (
    <div className="overflow-hidden rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex items-center justify-between border-b border-zinc-200 px-5 py-3 dark:border-zinc-800">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
          Microserviços
        </h3>
        <span className="text-xs text-zinc-500">{services.length} serviços</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-100 text-left text-xs font-medium text-zinc-500 dark:border-zinc-800">
              <th className="py-3 pl-5 pr-2">Serviço</th>
              <th className="px-2">Status</th>
              <th className="px-2">
                <Clock size={12} className="inline" /> Uptime
              </th>
              <th className="px-2">
                <Cpu size={12} className="inline" /> CPU
              </th>
              <th className="px-2">
                <HardDrive size={12} className="inline" /> RAM
              </th>
              <th className="px-2">
                <Gauge size={12} className="inline" /> Lat.
              </th>
              <th className="px-2">RPS</th>
              <th className="px-2">Ver.</th>
            </tr>
          </thead>
          <tbody>
            {services.map((s) => (
              <tr
                key={s.id}
                className="border-b border-zinc-50 hover:bg-zinc-50 dark:border-zinc-900 dark:hover:bg-zinc-900/50"
              >
                <td className="py-3 pl-5 pr-2">
                  <div className="font-medium text-zinc-900 dark:text-zinc-100">
                    {s.name}
                  </div>
                  <div className="text-xs text-zinc-500">{s.description}</div>
                </td>
                <td className="px-2">
                  <span
                    className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${statusBadge[s.status]}`}
                  >
                    <StatusDot status={s.status} />
                    {statusLabel[s.status]}
                  </span>
                </td>
                <td className="px-2 text-zinc-600 dark:text-zinc-400">
                  {s.uptime}
                </td>
                <td className="px-2">
                  <div className="flex items-center gap-2">
                    <span className="text-zinc-700 dark:text-zinc-300">
                      {s.cpu}%
                    </span>
                    <div className="h-1.5 w-12 rounded-full bg-zinc-100 dark:bg-zinc-800">
                      <div
                        className="h-full rounded-full bg-violet-500"
                        style={{ width: `${s.cpu}%` }}
                      />
                    </div>
                  </div>
                </td>
                <td className="px-2">
                  <div className="flex items-center gap-2">
                    <span className="text-zinc-700 dark:text-zinc-300">
                      {s.memory}%
                    </span>
                    <div className="h-1.5 w-12 rounded-full bg-zinc-100 dark:bg-zinc-800">
                      <div
                        className="h-full rounded-full bg-indigo-500"
                        style={{ width: `${s.memory}%` }}
                      />
                    </div>
                  </div>
                </td>
                <td className="px-2 text-zinc-600 dark:text-zinc-400">
                  {s.latency > 0 ? `${s.latency}ms` : "—"}
                </td>
                <td className="px-2 text-zinc-600 dark:text-zinc-400">
                  {s.requestsPerSecond > 0 ? s.requestsPerSecond : "—"}
                </td>
                <td className="px-2">
                  <code className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
                    v{s.version}
                  </code>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
