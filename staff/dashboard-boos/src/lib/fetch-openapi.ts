import type { OpenApiSpec } from "./types";

let cache = new Map<string, { data: OpenApiSpec; ts: number }>();
const TTL = 60_000;

export async function fetchOpenApiSpec(url: string): Promise<OpenApiSpec | null> {
  const cached = cache.get(url);
  if (cached && Date.now() - cached.ts < TTL) return cached.data;

  try {
    const res = await fetch(url, { next: { revalidate: 60 } });
    if (!res.ok) return null;
    const data: OpenApiSpec = await res.json();
    cache.set(url, { data, ts: Date.now() });
    return data;
  } catch {
    return null;
  }
}
