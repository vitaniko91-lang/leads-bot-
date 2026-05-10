"use client";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";

type Point = { hour: string; count: number };

export function LeadFlowChart({ data }: { data: Point[] }) {
  const formatted = data.map((p) => ({
    label: new Date(p.hour).toLocaleString("en-US", { hour: "2-digit", weekday: "short" }),
    count: p.count,
  }));
  return (
    <div className="h-64">
      <ResponsiveContainer>
        <AreaChart data={formatted} margin={{ top: 10, right: 16, bottom: 0, left: -16 }}>
          <defs>
            <linearGradient id="leadFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#4ADE80" stopOpacity={0.4} />
              <stop offset="100%" stopColor="#4ADE80" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
          <XAxis dataKey="label" stroke="rgba(250,250,250,0.42)" fontSize={11} tickLine={false} axisLine={false} />
          <YAxis stroke="rgba(250,250,250,0.42)" fontSize={11} tickLine={false} axisLine={false} allowDecimals={false} />
          <Tooltip
            contentStyle={{
              background: "#161616", border: "1px solid rgba(255,255,255,0.12)",
              borderRadius: 6, fontSize: 12,
            }}
            cursor={{ stroke: "rgba(74,222,128,0.4)", strokeDasharray: 3 }}
          />
          <Area type="monotone" dataKey="count" stroke="#4ADE80" strokeWidth={2} fill="url(#leadFill)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
