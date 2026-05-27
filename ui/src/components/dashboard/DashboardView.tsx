import { useEffect, useState } from "react";
import {
  TrendingUp, Wallet, AlertTriangle, Gauge, FolderKanban,
  FileSignature, FileText, BarChart3,
} from "lucide-react";
import { rpc } from "../../api/rpc";
import { str, num, int } from "../../api/entity";
import { KPICard } from "../shared/KPICard";
import { ProgressBar } from "../shared/ProgressBar";
import type { Entity } from "../../api/types";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";

interface BudgetEntry {
  project_id: number;
  project: string;
  hours_tracked: number;
  hours_budget: number;
  progress: number;
}

export function DashboardView() {
  const [kpis, setKpis] = useState<Entity | null>(null);
  const [chartData, setChartData] = useState<{ label: string; revenue: number; pipeline: number; spendable: number }[]>([]);
  const [budgets, setBudgets] = useState<BudgetEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { load(); }, []);

  async function load() {
    setLoading(true);
    const [kpiRes, chartRes, budgetRes] = await Promise.all([
      rpc("dashboard.get_kpis"),
      rpc("dashboard.get_monthly_chart_data", { n_months: 12 }),
      rpc<BudgetEntry[]>("dashboard.get_project_budgets"),
    ]);
    if (kpiRes.ok && kpiRes.data) setKpis(kpiRes.data as Entity);
    if (budgetRes.ok && Array.isArray(budgetRes.data)) setBudgets(budgetRes.data);
    if (chartRes.ok && chartRes.data) {
      const d = chartRes.data as { revenue: Entity[]; spendable: Entity[] };
      const rev = (d.revenue || []) as Entity[];
      const spend = (d.spendable || []) as Entity[];
      setChartData(rev.map((r, i) => {
        const m = str(r, "month"), p = m.split("-");
        return {
          label: p.length === 2 ? `${p[1]}/${p[0].slice(2)}` : m,
          revenue: num(r, "revenue"),
          pipeline: num(r, "pipeline"),
          spendable: spend[i] ? num(spend[i], "spendable") : 0,
        };
      }));
    }
    setLoading(false);
  }

  if (loading) return <div className="flex items-center justify-center h-full text-secondary">Loading dashboard…</div>;
  if (!kpis) return (
    <div className="flex flex-col items-center justify-center h-full gap-2 text-secondary">
      <BarChart3 size={40} strokeWidth={1.2} /><span>No data. Install demo data to get started.</span>
    </div>
  );

  return (
    <div className="p-6 space-y-6 max-w-6xl">
      <h1 className="text-lg font-semibold">Dashboard</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KPICard title="Revenue (YTD)" value={str(kpis, "total_revenue_ytd_formatted")} icon={TrendingUp}
          valueColor={num(kpis, "total_revenue_ytd") > 0 ? "#4ade80" : undefined} />
        <KPICard title="Outstanding" value={str(kpis, "outstanding_amount_formatted")} icon={Wallet}
          valueColor={num(kpis, "outstanding_amount") > 0 ? "#facc15" : undefined} />
        <KPICard title="Overdue" value={str(kpis, "overdue_amount_formatted")} icon={AlertTriangle}
          valueColor={num(kpis, "overdue_amount") > 0 ? "#f87171" : undefined} />
        <KPICard title="Eff. Hourly Rate" value={str(kpis, "effective_hourly_rate_formatted")} icon={Gauge}
          valueColor="#60a5fa" />
        <KPICard title="Active Projects" value={String(int(kpis, "active_projects"))} icon={FolderKanban} />
        <KPICard title="Active Contracts" value={String(int(kpis, "active_contracts"))} icon={FileSignature} />
        <KPICard title="Unpaid Invoices" value={String(int(kpis, "unpaid_invoices"))} icon={FileText}
          valueColor={int(kpis, "unpaid_invoices") > 0 ? "#facc15" : undefined} />
        <KPICard title="Spendable Income" value={str(kpis, "spendable_income_formatted")} icon={Wallet}
          valueColor={num(kpis, "spendable_income") > 0 ? "#4ade80" : "#f87171"} />
      </div>

      {chartData.length > 0 && (
        <div className="rounded-lg bg-bg-card border border-border-subtle p-4">
          <h2 className="text-sm font-medium text-secondary mb-3">Monthly Revenue vs Spendable Income</h2>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={chartData} barGap={2}>
              <XAxis dataKey="label" tick={{ fill: "#b8b8bc", fontSize: 12 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "#b8b8bc", fontSize: 12 }} axisLine={false} tickLine={false}
                tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(0)}K` : String(v)} />
              <Tooltip contentStyle={{ background: "#3a3a3c", border: "1px solid #4a4a4c", borderRadius: 8, color: "#fff" }}
                labelStyle={{ color: "#b8b8bc" }} />
              <Legend wrapperStyle={{ fontSize: 13, color: "#b8b8bc" }} />
              <Bar dataKey="revenue" name="Revenue" stackId="income" fill="#3b82f6" radius={[0, 0, 0, 0]} />
              <Bar dataKey="pipeline" name="Pending" stackId="income" fill="#93c5fd" radius={[3, 3, 0, 0]} />
              <Bar dataKey="spendable" name="Spendable" fill="#4ade80" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {budgets.length > 0 && (
        <div className="rounded-lg bg-bg-card border border-border-subtle p-4 space-y-3">
          <h2 className="text-sm font-medium text-secondary">Project Time Budgets</h2>
          {budgets.map((b) => (
            <ProgressBar
              key={b.project_id}
              progress={b.progress}
              label={b.project}
              subtitle={`${b.hours_tracked.toFixed(1)}h / ${b.hours_budget.toFixed(0)}h`}
            />
          ))}
        </div>
      )}
    </div>
  );
}
