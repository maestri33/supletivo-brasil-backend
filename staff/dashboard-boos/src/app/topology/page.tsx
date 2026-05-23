import { DashboardShell } from "@/components/layout/dashboard-shell";
import { ServiceMap } from "@/components/dashboard/service-map";
import { services } from "@/lib/services-registry";

export default function TopologyPage() {
  return (
    <DashboardShell>
      <div className="mx-auto max-w-7xl space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-white">
            Topologia
          </h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            Mapa de dependências entre microserviços
          </p>
        </div>
        <ServiceMap services={services} />
      </div>
    </DashboardShell>
  );
}
