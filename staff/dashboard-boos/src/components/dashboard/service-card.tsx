"use client";

import Link from "next/link";
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Wrench,
  ArrowUpRight,
  Router,
  Zap,
  Database,
  MessageSquare,
  HardDrive,
  Eye,
  Webhook,
  Shield,
  Brain,
  CreditCard,
  Box,
  ExternalLink,
} from "lucide-react";
import type { Service } from "@/lib/types";

const statusConfig = {
  healthy: { icon: CheckCircle2, label: "UP", dot: "bg-emerald-500", text: "text-emerald-600 dark:text-emerald-400", bg: "bg-emerald-50 dark:bg-emerald-950/50", border: "border-emerald-200 dark:border-emerald-900" },
  degraded: { icon: AlertTriangle, label: "DEG", dot: "bg-amber-500", text: "text-amber-600 dark:text-amber-400", bg: "bg-amber-50 dark:bg-amber-950/50", border: "border-amber-200 dark:border-amber-900" },
  down: { icon: XCircle, label: "DOWN", dot: "bg-red-500", text: "text-red-600 dark:text-red-400", bg: "bg-red-50 dark:bg-red-950/50", border: "border-red-200 dark:border-red-900" },
  maintenance: { icon: Wrench, label: "MAN", dot: "bg-blue-500", text: "text-blue-600 dark:text-blue-400", bg: "bg-blue-50 dark:bg-blue-950/50", border: "border-blue-200 dark:border-blue-900" },
};

const categoryIcons: Record<string, React.ElementType> = {
  gateway: Router,
  core: Zap,
  database: Database,
  messaging: MessageSquare,
  storage: HardDrive,
  monitoring: Eye,
  integration: Webhook,
  security: Shield,
  ai: Brain,
  payment: CreditCard,
  other: Box,
};

export function ServiceCard({ service }: { service: Service }) {
  const status = statusConfig[service.status] || statusConfig.healthy;
  const StatusIcon = status.icon;
  const CategoryIcon = categoryIcons[service.category] || Box;

  return (
    <Link
      href={`/services/${service.id}`}
      className={`group relative flex flex-col rounded-xl border-2 p-5 transition-all duration-200 hover:shadow-lg hover:-translate-y-0.5 ${status.bg} ${status.border}`}
    >
      {/* Status badge */}
      <div className="absolute top-3 right-3">
        <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-bold ${status.text}`}>
          <span className={`h-2 w-2 rounded-full ${status.dot} ${service.status === "healthy" ? "animate-pulse" : ""}`} />
          {status.label}
        </span>
      </div>

      {/* Category icon */}
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-white/80 dark:bg-black/30">
        <CategoryIcon size={24} className={status.text} />
      </div>

      {/* Info */}
      <h3 className="text-base font-bold text-zinc-900 dark:text-white group-hover:text-violet-600 dark:group-hover:text-violet-400 transition-colors">
        {service.name}
      </h3>
      <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400 line-clamp-2">
        {service.description}
      </p>

      {/* Meta bar */}
      <div className="mt-4 flex items-center gap-3 text-xs text-zinc-400">
        <span>{service.host}:{service.port}</span>
        {service.latency > 0 && (
          <span>{service.latency}ms</span>
        )}
        <span className="ml-auto opacity-0 group-hover:opacity-100 transition-opacity">
          <ArrowUpRight size={14} />
        </span>
      </div>

      {/* Tags */}
      {service.tags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1">
          {service.tags.slice(0, 3).map((t) => (
            <span key={t} className="rounded-md bg-white/50 dark:bg-black/20 px-1.5 py-0.5 text-[10px] font-medium text-zinc-500 dark:text-zinc-500">
              {t}
            </span>
          ))}
        </div>
      )}

      {/* Hover gradient border effect */}
      <div className="absolute inset-0 rounded-xl border-2 border-transparent group-hover:border-violet-400 dark:group-hover:border-violet-500 pointer-events-none transition-colors" />
    </Link>
  );
}
