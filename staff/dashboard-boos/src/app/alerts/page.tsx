import { DashboardShell } from "@/components/layout/dashboard-shell";
import { Bell, BellOff } from "lucide-react";

const alerts: Array<{ id: string; service: string; level: "critical" | "warning"; message: string; time: string }> = [
  { id: "1", service: "User Service", level: "critical", message: "Latência acima de 300ms há 15 minutos", time: "5 min atrás" },
  { id: "2", service: "Catalog Service", level: "critical", message: "Serviço DOWN — Elasticsearch inacessível", time: "10 min atrás" },
  { id: "3", service: "API Gateway", level: "warning", message: "Rate limit atingido para IP 10.0.1.45", time: "30 min atrás" },
  { id: "4", service: "Auth Service", level: "warning", message: "Múltiplas falhas de login detectadas", time: "45 min atrás" },
];

const levelStyle = {
  critical: "border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950/50",
  warning: "border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/50",
};

export default function AlertsPage() {
  return (
    <DashboardShell>
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-white">
              Alertas
            </h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              {alerts.length} alertas ativos
            </p>
          </div>
          <button className="inline-flex items-center gap-2 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700">
            <BellOff size={16} /> Silenciar Todos
          </button>
        </div>

        <div className="space-y-3">
          {alerts.map((a) => (
            <div
              key={a.id}
              className={`rounded-xl border p-4 ${levelStyle[a.level]}`}
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <Bell size={14} className={a.level === "critical" ? "text-red-500" : "text-amber-500"} />
                    <span className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                      {a.service}
                    </span>
                    <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${
                      a.level === "critical"
                        ? "bg-red-200 text-red-800 dark:bg-red-900 dark:text-red-300"
                        : "bg-amber-200 text-amber-800 dark:bg-amber-900 dark:text-amber-300"
                    }`}>
                      {a.level.toUpperCase()}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
                    {a.message}
                  </p>
                </div>
                <span className="text-xs text-zinc-500">{a.time}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </DashboardShell>
  );
}
