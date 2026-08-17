import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

export type ChartType = "line" | "bar"

interface AnalyticsDatum {
  label: string
  value: number
}

const tooltipStyle = {
  background: "var(--surface-raised)",
  border: "1px solid var(--border-strong)",
  borderRadius: 8,
  color: "var(--text-primary)",
  fontSize: 12,
  boxShadow: "0 10px 30px rgba(0, 0, 0, .22)",
}

export function AnalyticsChart({ data, chartType }: { data: AnalyticsDatum[]; chartType: ChartType }) {
  const shared = <><CartesianGrid stroke="var(--chart-grid)" vertical={false} /><XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fill: "var(--text-muted)", fontSize: 11 }} /><YAxis tickLine={false} axisLine={false} tick={{ fill: "var(--text-muted)", fontSize: 11 }} width={38} /><Tooltip cursor={chartType === "line" ? { stroke: "var(--accent)", strokeWidth: 1 } : { fill: "var(--surface-hover)" }} contentStyle={tooltipStyle} formatter={(value) => Number(value).toLocaleString()} /></>
  const chart = chartType === "line"
    ? <LineChart data={data} margin={{ top: 12, right: 12, left: 0, bottom: 0 }}>{shared}<Line type="monotone" dataKey="value" stroke="var(--accent)" strokeWidth={2.25} dot={false} activeDot={{ r: 5, fill: "var(--accent)" }} animationDuration={240} /></LineChart>
    : <BarChart data={data} margin={{ top: 12, right: 12, left: 0, bottom: 0 }}>{shared}<Bar dataKey="value" fill="var(--accent)" radius={[4, 4, 0, 0]} animationDuration={240} /></BarChart>

  return <div className="analytics-chart" data-testid="analytics-chart" aria-label={`${chartType} chart of dashboard metrics`}><ResponsiveContainer width="100%" height="100%">{chart}</ResponsiveContainer></div>
}
