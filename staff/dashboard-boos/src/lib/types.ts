export type ServiceStatus = "healthy" | "degraded" | "down" | "maintenance";

export interface Service {
  id: string;
  name: string;
  description: string;
  status: ServiceStatus;
  category: string;
  host: string;
  port: number;
  baseUrl: string;
  openApiUrl?: string;
  uptime: string;
  cpu: number;
  memory: number;
  latency: number;
  requestsPerSecond: number;
  version: string;
  dependencies: string[];
  tags: string[];
}

export interface OpenApiSpec {
  openapi: string;
  info: {
    title: string;
    version: string;
    summary?: string;
    description?: string;
    contact?: { name?: string; email?: string };
  };
  paths: Record<string, Record<string, OpenApiOperation>>;
  components?: {
    schemas?: Record<string, OpenApiSchema>;
  };
  tags?: { name: string; description?: string }[];
}

export interface OpenApiOperation {
  summary?: string;
  description?: string;
  operationId?: string;
  tags?: string[];
  parameters?: {
    name: string;
    in: "query" | "path" | "header";
    required: boolean;
    schema: { type: string; title?: string; description?: string; default?: unknown };
    description?: string;
  }[];
  requestBody?: {
    required: boolean;
    content: Record<string, { schema: { $ref?: string } }>;
  };
  responses: Record<string, {
    description: string;
    content?: Record<string, { schema: { $ref?: string; items?: { $ref?: string } } }>;
  }>;
}

export interface OpenApiSchema {
  type?: string;
  title?: string;
  properties?: Record<string, { type?: string; title?: string; $ref?: string; anyOf?: unknown[]; items?: unknown; default?: unknown; description?: string }>;
  required?: string[];
  description?: string;
}

export interface LogEntry {
  id: string;
  serviceId: string;
  level: "INFO" | "WARN" | "ERROR" | "DEBUG";
  message: string;
  timestamp: string;
  source?: string;
}

export interface MetricsSnapshot {
  timestamp: string;
  cpu: number;
  memory: number;
  requests: number;
  latency: number;
  errors: number;
}

export const CATEGORIES: Record<string, { id: string; label: string; icon: string }> = {
  gateway: { id: "gateway", label: "Gateway", icon: "Router" },
  core: { id: "core", label: "Core", icon: "Zap" },
  database: { id: "database", label: "Databases", icon: "Database" },
  messaging: { id: "messaging", label: "Messaging", icon: "MessageSquare" },
  storage: { id: "storage", label: "Storage", icon: "HardDrive" },
  monitoring: { id: "monitoring", label: "Monitoring", icon: "Eye" },
  integration: { id: "integration", label: "Integration", icon: "Webhook" },
  security: { id: "security", label: "Security", icon: "Shield" },
  ai: { id: "ai", label: "AI/ML", icon: "Brain" },
  payment: { id: "payment", label: "Payments", icon: "CreditCard" },
  other: { id: "other", label: "Other", icon: "Box" },
};
