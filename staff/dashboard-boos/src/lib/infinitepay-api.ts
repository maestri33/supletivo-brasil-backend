const BASE = "http://10.10.10.120";

class ApiError extends Error {
  code: number;
  detail: string;
  constructor(code: number, detail: string) {
    super(detail);
    this.code = code;
    this.detail = detail;
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  const data = await res.json();
  if (!res.ok) {
    throw new ApiError(res.status, data.detail || `HTTP ${res.status}`);
  }
  return data as T;
}

// ─── Types ───

export interface HealthResponse {
  ok: boolean;
}

export interface CustomerIn {
  name: string;
  email: string;
  phone_number: string;
}

export interface CheckoutCreate {
  external_id: string;
  customer: CustomerIn;
}

export interface CheckoutResponse {
  external_id: string;
  is_paid: boolean;
  checkout_url: string | null;
  receipt_url: string | null;
  invoice_slug: string | null;
  transaction_nsu: string | null;
  capture_method: string | null;
  installments: number | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface CheckoutListResponse {
  items: CheckoutResponse[];
}

export interface ConfigResponse {
  handle: string | null;
  price: number | null;
  quantity: number;
  description: string | null;
  redirect_url: string | null;
  backend_webhook: string | null;
  public_api_url: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ConfigUpdate {
  handle?: string | null;
  price?: number | null;
  quantity?: number | null;
  description?: string | null;
  redirect_url?: string | null;
  backend_webhook?: string | null;
  public_api_url?: string | null;
}

export interface WebhookResponse {
  ok: boolean;
  paid: boolean;
  duplicate: boolean;
}

export interface AskRequest {
  question: string;
  deep?: boolean;
}

export interface AskResponse {
  answer: string;
  enabled: boolean;
  model: string | null;
  elapsed_ms: number | null;
  tools_called: Record<string, unknown>[] | null;
  usage: Record<string, unknown> | null;
}

export interface ReportResponse {
  report: string;
  enabled: boolean;
  kind: string | null;
  model: string | null;
  elapsed_ms: number | null;
  tools_called: Record<string, unknown>[] | null;
  usage: Record<string, unknown> | null;
}

export interface ErrorResponse {
  detail: string;
}

// ─── API functions ───

export function healthCheck(): Promise<HealthResponse> {
  return request("/health");
}

export function readyCheck(): Promise<HealthResponse> {
  return request("/ready");
}

export function fetchCheckouts(): Promise<CheckoutListResponse> {
  return request("/api/v1/checkout/");
}

export function createCheckout(body: CheckoutCreate): Promise<CheckoutResponse> {
  return request("/api/v1/checkout/", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function fetchCheckout(externalId: string): Promise<CheckoutResponse> {
  return request(`/api/v1/checkout/${encodeURIComponent(externalId)}/`);
}

export function fetchConfig(): Promise<ConfigResponse> {
  return request("/api/v1/config/");
}

export function patchConfig(body: ConfigUpdate): Promise<ConfigResponse> {
  return request("/api/v1/config/", {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function postWebhook(externalId: string, payload: unknown): Promise<WebhookResponse> {
  return request(`/api/v1/webhook/?external_id=${encodeURIComponent(externalId)}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchCheckoutByNsu(orderNsu: string): Promise<CheckoutResponse> {
  return request(`/api/v1/webhook/?order_nsu=${encodeURIComponent(orderNsu)}`);
}

export function askAI(question: string, deep = false): Promise<AskResponse> {
  return request("/api/v1/ask/", {
    method: "POST",
    body: JSON.stringify({ question, deep }),
  });
}

export function generateReport(kind: "daily" | "weekly" | "full"): Promise<ReportResponse> {
  return request(`/api/v1/report/?kind=${kind}`, {
    method: "POST",
  });
}
