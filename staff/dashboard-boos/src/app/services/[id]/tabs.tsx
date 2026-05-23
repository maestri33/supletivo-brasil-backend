"use client";

import { useState, useEffect } from "react";
import {
  FileText,
  Activity,
  Eye,
  Clock,
  BarChart3,
  ExternalLink,
} from "lucide-react";
import { EndpointExplorer } from "@/components/dashboard/endpoint-explorer";
import { InfinitePayEndpoints } from "@/components/infinitepay/infinitepay-endpoints";
import type { Service, OpenApiSpec } from "@/lib/types";
import { fetchOpenApiSpec } from "@/lib/fetch-openapi";

const tabs = [
  { id: "overview", label: "Overview", icon: Eye },
  { id: "endpoints", label: "Endpoints", icon: FileText },
  { id: "metrics", label: "Métricas", icon: BarChart3 },
  { id: "logs", label: "Logs", icon: Clock },
];

export function ServiceDetailTabs({ service }: { service: Service }) {
  const [activeTab, setActiveTab] = useState("endpoints");
  const [spec, setSpec] = useState<OpenApiSpec | null>(null);
  const [loadingSpec, setLoadingSpec] = useState(false);

  useEffect(() => {
    if (service.openApiUrl) {
      setLoadingSpec(true);
      fetchOpenApiSpec(service.openApiUrl).then((data) => {
        setSpec(data);
        setLoadingSpec(false);
      });
    }
  }, [service.openApiUrl]);

  return (
    <div className="space-y-4">
      {/* Tab bar */}
      <div className="flex gap-1 border-b border-zinc-200 dark:border-zinc-800">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const active = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`inline-flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${
                active
                  ? "border-violet-500 text-violet-700 dark:text-violet-300"
                  : "border-transparent text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
              }`}
            >
              <Icon size={16} />
              {tab.label}
            </button>
          );
        })}

        {/* Open external */}
        <a
          href={service.baseUrl}
          target="_blank"
          rel="noopener"
          className="ml-auto inline-flex items-center gap-1.5 rounded-lg border border-zinc-200 px-3 py-2 text-xs font-medium text-zinc-500 hover:text-violet-600 hover:border-violet-200 dark:border-zinc-800 dark:hover:border-violet-800 transition-colors"
        >
          <ExternalLink size={12} />
          Abrir {service.name}
        </a>
      </div>

      {/* Tab content */}
      {activeTab === "overview" && (
        <div className="grid gap-4 lg:grid-cols-2">
          {/* Dependencies */}
          <div className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950">
            <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 mb-3">
              Dependências
            </h3>
            {service.dependencies.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {service.dependencies.map((dep) => (
                  <a
                    key={dep}
                    href={`/services/${dep}`}
                    className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-1.5 text-sm font-medium text-zinc-700 hover:border-violet-300 hover:text-violet-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:border-violet-700 dark:hover:text-violet-400"
                  >
                    {dep}
                  </a>
                ))}
              </div>
            ) : (
              <p className="text-sm text-zinc-400">Sem dependências externas</p>
            )}
          </div>

          {/* Info */}
          <div className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950">
            <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 mb-3">
              Informações
            </h3>
            <dl className="space-y-2 text-sm">
              {[
                ["Categoria", service.category],
                ["Host", service.host],
                ["Porta", String(service.port)],
                ["Base URL", service.baseUrl],
                ["OpenAPI", service.openApiUrl || "—"],
                ["Versão", `v${service.version}`],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between">
                  <dt className="text-zinc-500">{k}</dt>
                  <dd className="font-mono text-xs text-zinc-800 dark:text-zinc-200 truncate max-w-[300px]">
                    {v}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      )}

      {activeTab === "endpoints" && service.id === "infinitepay" && (
        <InfinitePayEndpoints />
      )}

      {activeTab === "endpoints" && service.id !== "infinitepay" && (
        <div>
          {loadingSpec && (
            <div className="flex items-center gap-2 rounded-xl border border-zinc-200 bg-white p-8 dark:border-zinc-800 dark:bg-zinc-950 text-sm text-zinc-500">
              <Activity size={16} className="animate-spin" />
              Carregando OpenAPI spec...
            </div>
          )}
          {!loadingSpec && spec && (
            <EndpointExplorer spec={spec} baseUrl={service.baseUrl} />
          )}
          {!loadingSpec && !spec && service.openApiUrl && (
            <div className="rounded-xl border border-zinc-200 bg-white p-8 text-center dark:border-zinc-800 dark:bg-zinc-950">
              <Eye size={32} className="mx-auto mb-2 text-zinc-300" />
              <p className="text-sm text-zinc-500">Falha ao carregar OpenAPI spec</p>
              <code className="text-xs text-zinc-400 mt-1 block">{service.openApiUrl}</code>
            </div>
          )}
          {!service.openApiUrl && (
            <div className="rounded-xl border border-zinc-200 bg-white p-8 text-center dark:border-zinc-800 dark:bg-zinc-950">
              <FileText size={32} className="mx-auto mb-2 text-zinc-300" />
              <p className="text-sm text-zinc-500">Serviço sem OpenAPI spec</p>
              <p className="text-xs text-zinc-400 mt-1">
                Adicione openApiUrl no registro do serviço
              </p>
            </div>
          )}
        </div>
      )}

      {activeTab === "metrics" && (
        <div className="rounded-xl border border-zinc-200 bg-white p-8 text-center dark:border-zinc-800 dark:bg-zinc-950">
          <BarChart3 size={32} className="mx-auto mb-2 text-zinc-300" />
          <p className="text-sm text-zinc-500">Métricas serão puxadas via Prometheus</p>
          <p className="text-xs text-zinc-400 mt-1">
            {service.host}:{service.port}/metrics
          </p>
        </div>
      )}

      {activeTab === "logs" && (
        <div className="rounded-xl border border-zinc-200 bg-white p-8 text-center dark:border-zinc-800 dark:bg-zinc-950">
          <Clock size={32} className="mx-auto mb-2 text-zinc-300" />
          <p className="text-sm text-zinc-500">Logs agregados via Loki/Elasticsearch</p>
          <p className="text-xs text-zinc-400 mt-1">
            Filtro: {`{service="${service.id}"}`}
          </p>
        </div>
      )}
    </div>
  );
}
