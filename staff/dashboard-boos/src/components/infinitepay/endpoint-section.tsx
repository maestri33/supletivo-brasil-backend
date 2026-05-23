import { AlertCircle, Loader2 } from "lucide-react";

const methodBadge: Record<string, string> = {
  GET: "bg-emerald-100 text-emerald-700 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-300 dark:border-emerald-800",
  POST: "bg-blue-100 text-blue-700 border-blue-300 dark:bg-blue-950 dark:text-blue-300 dark:border-blue-800",
  PATCH: "bg-amber-100 text-amber-700 border-amber-300 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-800",
  PUT: "bg-orange-100 text-orange-700 border-orange-300 dark:bg-orange-950 dark:text-orange-300 dark:border-orange-800",
  DELETE: "bg-red-100 text-red-700 border-red-300 dark:bg-red-950 dark:text-red-300 dark:border-red-800",
};

interface Props {
  method: string;
  path: string;
  description: string;
  isLoading?: boolean;
  error?: string | null;
  isEmpty?: boolean;
  emptyMessage?: string;
  onRetry?: () => void;
  children: React.ReactNode;
}

export function EndpointSection({
  method,
  path,
  description,
  isLoading,
  error,
  isEmpty,
  emptyMessage = "Nenhum dado disponível",
  onRetry,
  children,
}: Props) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-zinc-100 px-4 py-2.5 dark:border-zinc-800">
        <span
          className={`inline-flex items-center rounded border px-2 py-0.5 text-[10px] font-bold uppercase w-14 justify-center ${
            methodBadge[method] || "bg-zinc-100 text-zinc-600 border-zinc-300"
          }`}
        >
          {method}
        </span>
        <code className="text-xs font-medium text-zinc-700 dark:text-zinc-300 truncate">
          {path}
        </code>
      </div>

      {/* Description */}
      <div className="px-4 py-2 border-b border-zinc-50 dark:border-zinc-900/50">
        <p className="text-xs text-zinc-500">{description}</p>
      </div>

      {/* Content */}
      <div className="p-4">
        {isLoading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 size={20} className="animate-spin text-violet-500" />
          </div>
        )}

        {!isLoading && error && (
          <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 dark:border-red-900 dark:bg-red-950/50">
            <AlertCircle size={14} className="text-red-500 shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-red-700 dark:text-red-400">
                {error}
              </p>
            </div>
            {onRetry && (
              <button
                onClick={onRetry}
                className="text-xs font-medium text-red-600 hover:text-red-800 dark:text-red-400 shrink-0"
              >
                Retry
              </button>
            )}
          </div>
        )}

        {!isLoading && !error && isEmpty && (
          <div className="flex flex-col items-center py-6 text-zinc-400">
            <p className="text-xs">{emptyMessage}</p>
          </div>
        )}

        {!isLoading && !error && !isEmpty && children}
      </div>
    </div>
  );
}
