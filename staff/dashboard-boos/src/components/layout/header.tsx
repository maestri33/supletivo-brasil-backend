"use client";

import { Moon, Sun, Search } from "lucide-react";
import { useEffect, useState } from "react";

export function Header() {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const m = matchMedia("(prefers-color-scheme: dark)");
    setDark(document.documentElement.classList.contains("dark"));
    const cb = () => {
      const isDark = document.documentElement.classList.contains("dark");
      setDark(isDark);
    };
    m.addEventListener("change", cb);
    return () => m.removeEventListener("change", cb);
  }, []);

  function toggleDark() {
    document.documentElement.classList.toggle("dark");
    setDark(!dark);
    localStorage.setItem("theme", dark ? "light" : "dark");
  }

  return (
    <header className="flex h-14 items-center gap-4 border-b border-zinc-200 bg-white px-6 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="relative flex-1 max-w-md">
        <Search
          size={16}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400"
        />
        <input
          type="text"
          placeholder="Buscar serviço, log, métrica..."
          className="w-full rounded-lg border border-zinc-200 bg-zinc-50 py-2 pl-9 pr-4 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100 dark:placeholder:text-zinc-500"
        />
      </div>

      <div className="flex items-center gap-3">
        {/* Status indicator */}
        <div className="flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
          <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
          6/8 UP
        </div>

        {/* Dark mode toggle */}
        <button
          onClick={toggleDark}
          className="rounded-lg p-2 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-900 dark:hover:text-zinc-300"
        >
          {dark ? <Sun size={18} /> : <Moon size={18} />}
        </button>

        {/* Avatar placeholder */}
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-violet-600 text-xs font-semibold text-white">
          AD
        </div>
      </div>
    </header>
  );
}
