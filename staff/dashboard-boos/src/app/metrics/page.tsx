import { DashboardShell } from "@/components/layout/dashboard-shell";
import { MetricsChart } from "@/components/dashboard/metrics-chart";
import { services } from "@/lib/services-registry";
import { generateMetricsHistory } from "@/lib/mock-data";
import { Cpu, HardDrive, Gauge, Activity } from "lucide-react";

const history = generateMetricsHistory(24);
const latest = history[history.length - 1];

export default function MetricsPage() {
  return (
    <DashboardShell>
      <div className="mx-auto max-w-7xl space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-white">
            Métricas
          </h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            Métricas agregadas da plataforma (24h)
          </p>
        </div>

        <div className="grid grid-cols-4 gap-4">
          {[
            { icon: Cpu, label: "CPU Médio", val: `${Math.round(latest.cpu)}%`, color: "violet" },
            { icon: HardDrive, label: "RAM Média", val: `${Math.round(latest.memory)}%`, color: "indigo" },
            { icon: Gauge, label: "Latência", val: `${Math.round(latest.latency)}ms`, color: "orange" },
            { icon: Activity, label: "Requests/s", val: Math.round(latest.requests).toLocaleString(), color: "emerald" },
          ].map((m) => (
            <div
              key={m.label}
              className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
            >
              <m.icon size={20} className={`text-${m.color}-500 mb-2`} />
              <div className="text-2xl font-bold text-zinc-900 dark:text-white">{m.val}</div>
              <div className="text-xs text-zinc-500">{m.label}</div>
            </div>
          ))}
        </div>

        <MetricsChart />
      </div>
    </DashboardShell>
  );
}
