import type { LogEntry, MetricsSnapshot } from "./types";

export const logs: LogEntry[] = [
  { id: "1", serviceId: "users", level: "ERROR", message: "Connection pool exhausted after 5000ms timeout", timestamp: "2026-05-05T21:45:00Z" },
  { id: "2", serviceId: "api-gateway", level: "WARN", message: "Rate limit threshold reached for IP 10.0.1.45", timestamp: "2026-05-05T21:44:30Z" },
  { id: "3", serviceId: "catalog", level: "ERROR", message: "Elasticsearch cluster unreachable: connection refused", timestamp: "2026-05-05T21:44:00Z" },
  { id: "4", serviceId: "payments", level: "INFO", message: "Batch settlement completed: 342 transactions processed", timestamp: "2026-05-05T21:43:15Z" },
  { id: "5", serviceId: "auth", level: "WARN", message: "Failed login attempts threshold crossed for user admin@boos.com", timestamp: "2026-05-05T21:42:10Z" },
  { id: "6", serviceId: "notifications", level: "INFO", message: "Push notification batch sent: 1500 devices", timestamp: "2026-05-05T21:41:00Z" },
  { id: "7", serviceId: "users", level: "ERROR", message: "NullPointerException at UserRepository.findById (line 127)", timestamp: "2026-05-05T21:40:45Z" },
  { id: "8", serviceId: "api-gateway", level: "INFO", message: "TLS certificate renewed: valid until 2026-08-05", timestamp: "2026-05-05T21:39:30Z" },
];

export function generateMetricsHistory(hours: number = 24): MetricsSnapshot[] {
  const snapshots: MetricsSnapshot[] = [];
  const now = new Date();
  for (let i = hours * 12; i >= 0; i--) {
    const t = new Date(now.getTime() - i * 5 * 60 * 1000);
    snapshots.push({
      timestamp: t.toISOString(),
      cpu: 20 + Math.random() * 60,
      memory: 30 + Math.random() * 55,
      requests: 500 + Math.random() * 2000,
      latency: 30 + Math.random() * 250,
      errors: Math.floor(Math.random() * 20),
    });
  }
  return snapshots;
}
