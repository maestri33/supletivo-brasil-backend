"use client";

import { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Shield,
  Key,
  Copy,
  Check,
} from "lucide-react";
import type { OpenApiSpec, OpenApiOperation } from "@/lib/types";

const methodColors: Record<string, string> = {
  GET: "bg-emerald-100 text-emerald-700 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-300 dark:border-emerald-800",
  POST: "bg-blue-100 text-blue-700 border-blue-300 dark:bg-blue-950 dark:text-blue-300 dark:border-blue-800",
  PUT: "bg-amber-100 text-amber-700 border-amber-300 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-800",
  PATCH: "bg-orange-100 text-orange-700 border-orange-300 dark:bg-orange-950 dark:text-orange-300 dark:border-orange-800",
  DELETE: "bg-red-100 text-red-700 border-red-300 dark:bg-red-950 dark:text-red-300 dark:border-red-800",
};

function EndpointRow({
  path,
  method,
  operation,
  baseUrl,
}: {
  path: string;
  method: string;
  operation: OpenApiOperation;
  baseUrl: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const fullUrl = `${baseUrl}${path}`;

  function copyUrl() {
    navigator.clipboard.writeText(fullUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const reqSchema = operation.requestBody?.content?.["application/json"]?.schema?.$ref
    ?.split("/")
    .pop();

  return (
    <div className="border-b border-zinc-100 last:border-0 dark:border-zinc-800">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-zinc-50 dark:hover:bg-zinc-900/50 transition-colors"
      >
        {expanded ? (
          <ChevronDown size={14} className="text-zinc-400 shrink-0" />
        ) : (
          <ChevronRight size={14} className="text-zinc-400 shrink-0" />
        )}
        <span
          className={`inline-flex items-center rounded border px-2 py-0.5 text-[10px] font-bold uppercase w-16 justify-center shrink-0 ${methodColors[method] || "bg-zinc-100 text-zinc-600 border-zinc-300"}`}
        >
          {method}
        </span>
        <code className="text-sm font-medium text-zinc-800 dark:text-zinc-200 flex-1 truncate">
          {path}
        </code>
        <span className="text-xs text-zinc-400 hidden sm:block truncate max-w-xs">
          {operation.summary || operation.description}
        </span>
      </button>

      {expanded && (
        <div className="bg-zinc-50 dark:bg-zinc-900/30 px-4 py-3 space-y-3 border-t border-zinc-100 dark:border-zinc-800">
          {/* Description */}
          {operation.description && (
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              {operation.description}
            </p>
          )}

          {/* Full URL + copy */}
          <div className="flex items-center gap-2">
            <code className="flex-1 rounded bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 px-3 py-2 text-xs text-zinc-700 dark:text-zinc-300 break-all font-mono">
              {fullUrl}
            </code>
            <button
              onClick={copyUrl}
              className="rounded-lg border border-zinc-200 p-2 text-zinc-400 hover:text-violet-500 hover:border-violet-200 dark:border-zinc-700 shrink-0"
            >
              {copied ? <Check size={14} className="text-emerald-500" /> : <Copy size={14} />}
            </button>
            <a
              href={fullUrl}
              target="_blank"
              rel="noopener"
              className="rounded-lg border border-zinc-200 p-2 text-zinc-400 hover:text-violet-500 dark:border-zinc-700 shrink-0"
            >
              <ExternalLink size={14} />
            </a>
          </div>

          {/* Parameters */}
          {operation.parameters && operation.parameters.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-zinc-500 mb-1.5">Parameters</p>
              <div className="space-y-1">
                {operation.parameters.map((p) => (
                  <div
                    key={p.name}
                    className="flex items-center gap-2 text-xs"
                  >
                    <span className="rounded bg-zinc-200 dark:bg-zinc-700 px-1 py-0.5 font-mono text-[10px] text-zinc-600 dark:text-zinc-400">
                      {p.in}
                    </span>
                    <code className="font-mono text-zinc-800 dark:text-zinc-200">
                      {p.name}
                    </code>
                    <span className="text-zinc-400">
                      {p.schema?.type || "string"}
                    </span>
                    {p.required && (
                      <span className="text-red-500 text-[10px] font-bold">*</span>
                    )}
                    {p.description && (
                      <span className="text-zinc-400 truncate">{p.description}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Request body */}
          {operation.requestBody && (
            <div>
              <p className="text-xs font-semibold text-zinc-500 mb-1.5">
                Request Body {operation.requestBody.required && <span className="text-red-500">*</span>}
              </p>
              <div className="rounded bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 px-3 py-2">
                <p className="text-xs font-mono text-zinc-600 dark:text-zinc-400">
                  Content-Type: application/json
                </p>
                {reqSchema && (
                  <p className="text-xs text-violet-600 dark:text-violet-400 font-mono mt-1">
                    Schema: {reqSchema}
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Responses */}
          {operation.responses && (
            <div>
              <p className="text-xs font-semibold text-zinc-500 mb-1.5">Responses</p>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(operation.responses).map(([code, r]) => (
                  <span
                    key={code}
                    className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium ${
                      code === "200" || code === "201"
                        ? "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                        : code === "400" || code === "422"
                          ? "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300"
                          : code === "404"
                            ? "border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300"
                            : "border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400"
                    }`}
                  >
                    {code}
                    <span className="opacity-60">{r.description}</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function EndpointExplorer({
  spec,
  baseUrl,
}: {
  spec: OpenApiSpec;
  baseUrl: string;
}) {
  const tagGroups = spec.tags || [];
  const paths = spec.paths;

  // Group paths by first tag
  const groupedByTag: Record<string, [string, Record<string, OpenApiOperation>][]> = {};
  const untagged: [string, Record<string, OpenApiOperation>][] = [];

  Object.entries(paths).forEach(([path, methods]) => {
    const firstTag =
      Object.values(methods)[0]?.tags?.[0] ||
      Object.values(methods)[1]?.tags?.[0] ||
      null;

    if (firstTag) {
      if (!groupedByTag[firstTag]) groupedByTag[firstTag] = [];
      groupedByTag[firstTag].push([path, methods]);
    } else {
      untagged.push([path, methods]);
    }
  });

  if (!spec || Object.keys(paths).length === 0) {
    return (
      <div className="rounded-xl border border-zinc-200 bg-white p-8 text-center dark:border-zinc-800 dark:bg-zinc-950">
        <p className="text-sm text-zinc-500">OpenAPI spec não disponível</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950 overflow-hidden">
      <div className="flex items-center gap-2 border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
        <Shield size={16} className="text-violet-500" />
        <span className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
          {spec.info?.title || "API"} v{spec.info?.version || "?"}
        </span>
        <span className="ml-auto text-xs text-zinc-400">
          {Object.keys(paths).length} endpoints
        </span>
      </div>

      {Object.entries(groupedByTag).map(([tag, entries]) => {
        const tagInfo = tagGroups.find((t) => t.name === tag);
        return (
          <div key={tag}>
            <div className="bg-zinc-50 dark:bg-zinc-900/50 px-4 py-2 border-b border-zinc-100 dark:border-zinc-800">
              <p className="text-xs font-bold uppercase tracking-wider text-zinc-500">
                {tagInfo?.description || tag}
              </p>
            </div>
            {entries.map(([path, methods]) =>
              Object.entries(methods).map(([method, op]) => (
                <EndpointRow
                  key={`${method}-${path}`}
                  path={path}
                  method={method.toUpperCase()}
                  operation={op}
                  baseUrl={baseUrl}
                />
              ))
            )}
          </div>
        );
      })}

      {untagged.length > 0 && (
        <div>
          <div className="bg-zinc-50 dark:bg-zinc-900/50 px-4 py-2 border-b border-zinc-100 dark:border-zinc-800">
            <p className="text-xs font-bold uppercase tracking-wider text-zinc-500">
              Endpoints
            </p>
          </div>
          {untagged.map(([path, methods]) =>
            Object.entries(methods).map(([method, op]) => (
              <EndpointRow
                key={`${method}-${path}`}
                path={path}
                method={method.toUpperCase()}
                operation={op}
                baseUrl={baseUrl}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}
