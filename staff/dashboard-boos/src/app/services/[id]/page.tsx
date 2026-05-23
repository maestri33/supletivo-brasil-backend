import Link from "next/link";
import { notFound } from "next/navigation";
import { getServiceById } from "@/lib/services-registry";
import { CATEGORIES } from "@/lib/types";
import { ServiceDetailTabs } from "./tabs";
import { DashboardShell } from "@/components/layout/dashboard-shell";

export default async function ServiceDetailPage(props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  const service = getServiceById(id);

  if (!service) notFound();

  const cat = CATEGORIES[service.category] || CATEGORIES.other;

  const statusConfig = {
    healthy: { label: "UP", dot: "bg-emerald-500", text: "text-emerald-600 dark:text-emerald-400", bg: "bg-emerald-50 dark:bg-emerald-950", border: "border-emerald-200 dark:border-emerald-900" },
    degraded: { label: "DEG", dot: "bg-amber-500", text: "text-amber-600 dark:text-amber-400", bg: "bg-amber-50 dark:bg-amber-950", border: "border-amber-200 dark:border-amber-900" },
    down: { label: "DOWN", dot: "bg-red-500", text: "text-red-600 dark:text-red-400", bg: "bg-red-50 dark:bg-red-950", border: "border-red-200 dark:border-red-900" },
    maintenance: { label: "MAN", dot: "bg-blue-500", text: "text-blue-600 dark:text-blue-400", bg: "bg-blue-50 dark:bg-blue-950", border: "border-blue-200 dark:border-blue-900" },
  };

  const status = statusConfig[service.status];

  return (
    <DashboardShell>
      <div className="mx-auto max-w-7xl space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 text-xs text-zinc-500 mb-1">
              <Link href="/" className="hover:text-violet-500">Home</Link>
              <span>/</span>
              <Link href="/" className="hover:text-violet-500">Serviços</Link>
              <span>/</span>
              <span className="text-zinc-400">{service.id}</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-white">
              {service.name}
            </h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
              {service.description}
            </p>
          </div>
          <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-bold shrink-0 ${status.text} ${status.bg} ${status.border}`}>
            <span className={`h-2 w-2 rounded-full ${status.dot} ${service.status === "healthy" ? "animate-pulse" : ""}`} />
            {status.label}
          </span>
        </div>

        {/* Quick stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
          {[
            { label: "Host", value: service.host },
            { label: "Port", value: String(service.port) },
            { label: "Uptime", value: service.uptime },
            { label: "CPU", value: `${service.cpu}%` },
            { label: "RAM", value: `${service.memory}%` },
            { label: "RPS", value: String(service.requestsPerSecond) },
            { label: "Latência", value: service.latency > 0 ? `${service.latency}ms` : "—" },
            { label: "Versão", value: `v${service.version}` },
            { label: "Categoria", value: cat.label },
            { label: "Base URL", value: service.baseUrl },
            { label: "Dependências", value: service.dependencies.length > 0 ? service.dependencies.join(", ") : "nenhuma" },
            { label: "Tags", value: service.tags.join(", ") },
          ].map((stat) => (
            <div
              key={stat.label}
              className="rounded-lg border border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-950"
            >
              <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400 mb-1">
                {stat.label}
              </p>
              <p className="text-sm font-medium text-zinc-800 dark:text-zinc-200 truncate">
                {stat.value}
              </p>
            </div>
          ))}
        </div>

        {/* Tabs */}
        <ServiceDetailTabs service={service} />
      </div>
    </DashboardShell>
  );
}
