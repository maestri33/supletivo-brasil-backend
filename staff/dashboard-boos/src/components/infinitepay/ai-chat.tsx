"use client";

import { useState, useRef, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { askAI, type AskResponse } from "@/lib/infinitepay-api";
import { EndpointSection } from "./endpoint-section";
import { Send, Loader2, Brain, Clock, Cpu, User, Sparkles } from "lucide-react";

interface Message {
  role: "user" | "assistant";
  content: string;
  meta?: {
    model?: string | null;
    elapsed_ms?: number | null;
    usage?: Record<string, unknown> | null;
    tools_called?: Record<string, unknown>[] | null;
  };
}

export function AiChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [deep, setDeep] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const mutation = useMutation({
    mutationFn: (q: string) => askAI(q, deep),
    onSuccess: (data) => {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.answer,
          meta: {
            model: data.model,
            elapsed_ms: data.elapsed_ms,
            usage: data.usage,
            tools_called: data.tools_called,
          },
        },
      ]);
    },
  });

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = question.trim();
    if (!q || mutation.isPending) return;
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setQuestion("");
    mutation.mutate(q);
  }

  return (
    <EndpointSection
      method="POST"
      path="/api/v1/ask/"
      description="Pergunte sobre seus checkouts em linguagem natural. Use Deep Mode para análises complexas."
      error={mutation.error?.message || null}
      onRetry={() => mutation.reset()}
    >
      <div className="space-y-3">
        {/* Messages */}
        <div
          ref={scrollRef}
          className="space-y-3 max-h-64 overflow-y-auto min-h-[100px]"
        >
          {messages.length === 0 && (
            <div className="flex flex-col items-center py-6 text-zinc-400">
              <Sparkles size={24} className="mb-2 text-violet-300" />
              <p className="text-xs">Faça uma pergunta sobre seus checkouts</p>
              <div className="flex flex-wrap gap-1 mt-2">
                {[
                  "Quantos checkouts foram pagos hoje?",
                  "Qual o ticket médio?",
                  "Checkouts pendentes esta semana",
                ].map((s) => (
                  <button
                    key={s}
                    onClick={() => setQuestion(s)}
                    className="rounded-full border border-zinc-200 px-2 py-0.5 text-[10px] text-zinc-500 hover:border-violet-300 hover:text-violet-600 dark:border-zinc-800 dark:hover:border-violet-700 dark:hover:text-violet-400"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div
              key={i}
              className={`flex gap-2 ${m.role === "user" ? "justify-end" : ""}`}
            >
              {m.role === "assistant" && (
                <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-violet-100 dark:bg-violet-950">
                  <Brain size={12} className="text-violet-600 dark:text-violet-400" />
                </div>
              )}
              <div
                className={`rounded-xl px-3 py-2 text-xs max-w-[90%] ${
                  m.role === "user"
                    ? "bg-violet-600 text-white"
                    : "bg-zinc-100 text-zinc-800 dark:bg-zinc-900 dark:text-zinc-200"
                }`}
              >
                <p className="whitespace-pre-wrap leading-relaxed">{m.content}</p>
                {m.meta && (
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-[10px] opacity-60 border-t border-white/10 pt-1.5">
                    {m.meta.model && (
                      <span className="flex items-center gap-1">
                        <Cpu size={10} /> {m.meta.model}
                      </span>
                    )}
                    {m.meta.elapsed_ms && (
                      <span className="flex items-center gap-1">
                        <Clock size={10} /> {m.meta.elapsed_ms}ms
                      </span>
                    )}
                    {m.meta.tools_called && m.meta.tools_called.length > 0 && (
                      <span>{m.meta.tools_called.length} tools</span>
                    )}
                  </div>
                )}
              </div>
              {m.role === "user" && (
                <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-zinc-200 dark:bg-zinc-800">
                  <User size={12} className="text-zinc-500" />
                </div>
              )}
            </div>
          ))}

          {mutation.isPending && (
            <div className="flex gap-2">
              <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-violet-100 dark:bg-violet-950">
                <Brain size={12} className="text-violet-600 dark:text-violet-400" />
              </div>
              <div className="rounded-xl bg-zinc-100 dark:bg-zinc-900 px-3 py-2">
                <div className="flex gap-1">
                  <span className="h-1.5 w-1.5 rounded-full bg-violet-400 animate-bounce" />
                  <span className="h-1.5 w-1.5 rounded-full bg-violet-400 animate-bounce [animation-delay:0.1s]" />
                  <span className="h-1.5 w-1.5 rounded-full bg-violet-400 animate-bounce [animation-delay:0.2s]" />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Input */}
        <form onSubmit={handleSubmit} className="space-y-2">
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-1.5 cursor-pointer">
              <input
                type="checkbox"
                checked={deep}
                onChange={(e) => setDeep(e.target.checked)}
                className="rounded border-zinc-300 text-violet-600 focus:ring-violet-500"
              />
              <span className="text-[10px] font-semibold text-zinc-500">
                Deep Mode
              </span>
            </label>
          </div>
          <div className="flex items-end gap-2">
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e);
                }
              }}
              placeholder="Pergunte sobre seus checkouts..."
              rows={2}
              className="flex-1 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs text-zinc-900 placeholder:text-zinc-400 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100 resize-none"
            />
            <button
              type="submit"
              disabled={mutation.isPending || !question.trim()}
              className="rounded-lg bg-violet-600 p-2 text-white hover:bg-violet-700 disabled:opacity-50 shrink-0"
            >
              {mutation.isPending ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Send size={14} />
              )}
            </button>
          </div>
        </form>
      </div>
    </EndpointSection>
  );
}
