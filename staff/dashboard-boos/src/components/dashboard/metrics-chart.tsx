"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { generateMetricsHistory } from "@/lib/mock-data";
import { useMemo } from "react";

const data = generateMetricsHistory(6);

export function MetricsChart() {
  const formatted = useMemo(
    () =>
      data.map((d) => ({
        ...d,
        time: new Date(d.timestamp).toLocaleTimeString("pt-BR", {
          hour: "2-digit",
          minute: "2-digit",
        }),
      })),
    []
  );

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950">
      <h3 className="mb-4 text-sm font-semibold text-zinc-900 dark:text-zinc-100">
        Requests & Latência (6h)
      </h3>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={formatted}>
            <defs>
              <linearGradient id="reqGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#e4e4e7"
              strokeOpacity={0.4}
            />
            <XAxis
              dataKey="time"
              tick={{ fontSize: 11, fill: "#71717a" }}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              yAxisId="left"
              tick={{ fontSize: 11, fill: "#71717a" }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              tick={{ fontSize: 11, fill: "#71717a" }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "#18181b",
                border: "1px solid #3f3f46",
                borderRadius: "8px",
                color: "#fafafa",
                fontSize: "12px",
              }}
            />
            <Area
              yAxisId="left"
              type="monotone"
              dataKey="requests"
              stroke="#8b5cf6"
              strokeWidth={2}
              fill="url(#reqGrad)"
              name="Requests"
            />
            <Area
              yAxisId="right"
              type="monotone"
              dataKey="latency"
              stroke="#f97316"
              strokeWidth={2}
              fill="none"
              name="Latência (ms)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
