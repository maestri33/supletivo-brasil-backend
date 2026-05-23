import { DashboardShell } from "@/components/layout/dashboard-shell";
import { ServiceGrid } from "@/components/dashboard/service-grid";
import { HealthCards } from "@/components/dashboard/health-cards";
import { services } from "@/lib/services-registry";

export default function Home() {
  return (
    <DashboardShell>
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex items-end justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-white">
              Boos Platform
            </h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              {services.length} serviços · {services.filter((s) => s.status === "healthy").length} healthy
            </p>
          </div>
          <span className="flex items-center gap-2 text-xs text-zinc-400">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
            goat-gila.ts.net
          </span>
        </div>

        <HealthCards services={services} />
        <ServiceGrid />
      </div>
    </DashboardShell>
  );
}
