import type { ReactElement } from "react"
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

export type ChartType = "line" | "bar" | "donut"

export interface AnalyticsDatum {
  label: string
  value: number
  // Optional per-bar/slice color (CSS color or var(--token)) -- e.g. decision
  // distribution reuses the same fixed semantic tokens StatusBadge does
  // (var(--success)/var(--warning)/var(--danger)), never a personalizable
  // accent, so BUY/REVIEW/PASS stay distinguishable regardless of theme
  // customization. Ignored for line charts (a single trend line has one
  // color by design).
  color?: string
}

const tooltipStyle = {
  background: "var(--surface-raised)",
  border: "1px solid var(--border-strong)",
  borderRadius: 8,
  color: "var(--text-primary)",
  fontSize: 12,
  boxShadow: "0 10px 30px rgba(0, 0, 0, .22)",
}

const FALLBACK_COLORS = ["var(--accent)", "var(--success)", "var(--warning)", "var(--danger)", "var(--info)", "var(--chart-grid)"]

// A chart communicates shape at a glance; it never replaces the numbers.
// Every chart ships with a plain-text summary so the same data is
// available to screen readers and to anyone who prefers reading a list
// (non-color-only status, per the accessibility baseline).
export function ChartTextSummary({ title, data }: { title: string; data: AnalyticsDatum[] }) {
  const total = data.reduce((sum, d) => sum + d.value, 0)
  return (
    <ul className="chart-text-summary" aria-label={`${title}, as text`}>
      {data.map((d) => (
        <li key={d.label}>
          <span>{d.label}</span>
          <strong>
            {d.value.toLocaleString()}
            {total > 0 && <em>{` (${((d.value / total) * 100).toFixed(0)}%)`}</em>}
          </strong>
        </li>
      ))}
    </ul>
  )
}

export function AnalyticsChart({ data, chartType }: { data: AnalyticsDatum[]; chartType: ChartType }) {
  const shared = (
    <>
      <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
      <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fill: "var(--text-muted)", fontSize: 11 }} />
      <YAxis tickLine={false} axisLine={false} tick={{ fill: "var(--text-muted)", fontSize: 11 }} width={38} allowDecimals={false} />
      <Tooltip
        cursor={chartType === "line" ? { stroke: "var(--accent)", strokeWidth: 1 } : { fill: "var(--surface-hover)" }}
        contentStyle={tooltipStyle}
        formatter={(value) => Number(value).toLocaleString()}
      />
    </>
  )

  let chart: ReactElement
  if (chartType === "line") {
    chart = (
      <LineChart data={data} margin={{ top: 12, right: 12, left: 0, bottom: 0 }}>
        {shared}
        <Line type="monotone" dataKey="value" stroke="var(--accent)" strokeWidth={2.25} dot={false} activeDot={{ r: 5, fill: "var(--accent)" }} animationDuration={240} />
      </LineChart>
    )
  } else if (chartType === "donut") {
    chart = (
      <PieChart margin={{ top: 4, right: 4, left: 4, bottom: 4 }}>
        <Tooltip contentStyle={tooltipStyle} formatter={(value, name) => [Number(value).toLocaleString(), name]} />
        <Pie data={data} dataKey="value" nameKey="label" innerRadius="55%" outerRadius="90%" paddingAngle={data.length > 1 ? 2 : 0} animationDuration={240}>
          {data.map((d, index) => (
            <Cell key={d.label} fill={d.color ?? FALLBACK_COLORS[index % FALLBACK_COLORS.length]} />
          ))}
        </Pie>
      </PieChart>
    )
  } else {
    chart = (
      <BarChart data={data} margin={{ top: 12, right: 12, left: 0, bottom: 0 }}>
        {shared}
        <Bar dataKey="value" fill="var(--accent)" radius={[4, 4, 0, 0]} animationDuration={240}>
          {data.some((d) => d.color) && data.map((d) => <Cell key={d.label} fill={d.color ?? "var(--accent)"} />)}
        </Bar>
      </BarChart>
    )
  }

  return (
    <div className="analytics-chart" data-testid="analytics-chart" role="img" aria-label={`${chartType} chart: ${data.map((d) => `${d.label} ${d.value}`).join(", ")}`}>
      <ResponsiveContainer width="100%" height="100%">
        {chart}
      </ResponsiveContainer>
    </div>
  )
}
