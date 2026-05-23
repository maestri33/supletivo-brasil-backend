import { DashboardShell } from "@/components/layout/dashboard-shell";

export default function SettingsPage() {
  return (
    <DashboardShell>
      <div className="mx-auto max-w-7xl space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-white">
            Configurações
          </h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            Configurações do dashboard e monitoramento
          </p>
        </div>

        <div className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950">
          <div className="space-y-4">
            {[
              { label: "Intervalo de polling", value: "5s" },
              { label: "Retenção de logs", value: "7 dias" },
              { label: "Limite de alertas", value: "50" },
              { label: "Tema padrão", value: "Sistema" },
              { label: "Endpoint da API", value: "http://api.boos.local" },
            ].map((s) => (
              <div
                key={s.label}
                className="flex items-center justify-between border-b border-zinc-100 pb-3 last:border-0 dark:border-zinc-900"
              >
                <span className="text-sm text-zinc-600 dark:text-zinc-400">
                  {s.label}
                </span>
                <span className="text-sm font-medium text-zinc-900 dark:text-zinc-200">
                  {s.value}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
