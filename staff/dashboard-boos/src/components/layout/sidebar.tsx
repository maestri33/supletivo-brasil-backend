"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Activity,
  Server,
  FileText,
  Bell,
  Settings,
  ChevronLeft,
  ChevronRight,
  Boxes,
} from "lucide-react";
import { clsx } from "clsx";

const navItems = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/services", label: "Serviços", icon: Server },
  { href: "/metrics", label: "Métricas", icon: Activity },
  { href: "/logs", label: "Logs", icon: FileText },
  { href: "/alerts", label: "Alertas", icon: Bell },
  { href: "/topology", label: "Topologia", icon: Boxes },
  { href: "/settings", label: "Config", icon: Settings },
];

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();

  return (
    <aside
      className={clsx(
        "flex flex-col border-r border-zinc-200 bg-white transition-all duration-300 dark:border-zinc-800 dark:bg-zinc-950",
        collapsed ? "w-16" : "w-60"
      )}
    >
      {/* Logo */}
      <div className="flex h-14 items-center gap-3 border-b border-zinc-200 px-3 dark:border-zinc-800">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-violet-600 to-indigo-600 text-sm font-bold text-white shrink-0">
          B
        </div>
        {!collapsed && (
          <span className="text-lg font-bold tracking-tight text-zinc-900 dark:text-white">
            Boos
          </span>
        )}
      </div>

      {/* Nav items */}
      <nav className="flex flex-1 flex-col gap-1 p-2">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                active
                  ? "bg-violet-50 text-violet-700 dark:bg-violet-950 dark:text-violet-300"
                  : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-900"
              )}
            >
              <Icon size={20} className="shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center justify-center border-t border-zinc-200 py-3 text-zinc-400 hover:text-zinc-600 dark:border-zinc-800 dark:hover:text-zinc-300"
      >
        {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
      </button>
    </aside>
  );
}
