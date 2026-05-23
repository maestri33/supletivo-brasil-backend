import { DashboardShell } from "@/components/layout/dashboard-shell";
import { ServicesTable } from "@/components/dashboard/services-table";
import { HealthCards } from "@/components/dashboard/health-cards";
import { services } from "@/lib/services-registry";

export default function ServicesPage() {
  return (
    <DashboardShell>
      <div className="mx-auto max-w-7xl space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-white">
            Serviços
          </h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            Status e métricas de cada microserviço
          </p>
        </div>
        <HealthCards services={services} />
        <ServicesTable services={services} />
      </div>
    </DashboardShell>
  );
}
