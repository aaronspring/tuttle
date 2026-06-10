import { useEffect, useState } from "react";
import {
  TrendingUp, Wallet, AlertTriangle, Gauge, FolderKanban,
  FileSignature, FileText, BarChart3,
} from "lucide-react";
import { rpc } from "../../api/rpc";
import { str, num, int } from "../../api/entity";
import { KPICard } from "../shared/KPICard";
import type { Entity } from "../../api/types";
import {
  Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
  ComposedChart,
} from "recharts";

interface BudgetEntry {
  project_id: number;
  project: string;
  hours_tracked: number;
  hours_planned: number;
  hours_budget: number;
  hours_remaining: number;
  planned_revenue: number;
  progress: number;
  budget_exceeded: boolean;
}

interface RevenueCurveEntry {
  month: string;
  revenue: number;
  cumulative_revenue: number;
  is_forecast: boolean;
  source: string;
}

interface RevenueBar {
  label: string;
  invoiced: number;
  pending: number;
  planned: number;
}

export function DashboardView() {
  const [kpis, setKpis] = useState<Entity | null>(null);
  const [revenueBars, setRevenueBars] = useState<RevenueBar[]>([]);
  const [budgets, setBudgets] = useState<BudgetEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { load(); }, []);

  async function load() {
    setLoading(true);
    const [kpiRes, chartRes, budgetRes, curveRes] = await Promise.all([
      rpc("dashboard.get_kpis"),
      rpc("dashboard.get_monthly_chart_data", { n_months: 12 }),
      rpc<BudgetEntry[]>("dashboard.get_project_budgets"),
      rpc<RevenueCurveEntry[]>("dashboard.get_revenue_curve", { forecast_months: 6 }),
    ]);
    if (kpiRes.ok && kpiRes.data) setKpis(kpiRes.data as Entity);
    if (budgetRes.ok && Array.isArray(budgetRes.data)) setBudgets(budgetRes.data);

    const byLabel = new Map<string, RevenueBar>();

    if (chartRes.ok && chartRes.data) {
      const d = chartRes.data as { revenue: Entity[]; spendable: Entity[] };
      for (const r of (d.revenue || []) as Entity[]) {
        const m = str(r, "month"), p = m.split("-");
        const label = p.length === 2 ? `${p[1]}/${p[0].slice(2)}` : m;
        byLabel.set(label, {
          label,
          invoiced: num(r, "revenue"),
          pending: num(r, "pipeline"),
          planned: 0,
        });
      }
    }

    if (curveRes.ok && Array.isArray(curveRes.data)) {
      for (const r of curveRes.data as RevenueCurveEntry[]) {
        const m = (r.month ?? "").slice(0, 7), p = m.split("-");
        const label = p.length === 2 ? `${p[1]}/${p[0].slice(2)}` : m;
        if (r.source === "calendar") {
          const existing = byLabel.get(label) ?? { label, invoiced: 0, pending: 0, planned: 0 };
          existing.planned += r.revenue ?? 0;
          byLabel.set(label, existing);
        }
      }
    }

    const sorted = [...byLabel.values()].sort((a, b) => {
      const [am, ay] = a.label.split("/");
      const [bm, by] = b.label.split("/");
      return (+(ay ?? 0) - +(by ?? 0)) || (+(am ?? 0) - +(bm ?? 0));
    });
    setRevenueBars(sorted);
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

      {revenueBars.length > 0 && (
        <div className="rounded-lg bg-bg-card border border-border-subtle p-4">
          <h2 className="text-sm font-medium text-secondary mb-1">Revenue</h2>
          <p className="text-[11px] text-tertiary mb-3">Invoiced + pending from past months, planned from calendar</p>
          <ResponsiveContainer width="100%" height={260}>
            <ComposedChart data={revenueBars} barGap={0}>
              <XAxis dataKey="label" tick={{ fill: "#b8b8bc", fontSize: 12 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "#b8b8bc", fontSize: 12 }} axisLine={false} tickLine={false}
                tickFormatter={(v: number) => v >= 1000 ? `€${(v / 1000).toFixed(0)}K` : `€${v}`} />
              <Tooltip
                contentStyle={{ background: "#3a3a3c", border: "1px solid #4a4a4c", borderRadius: 8, color: "#fff" }}
                labelStyle={{ color: "#b8b8bc" }}
                formatter={(value: number, name: string) => {
                  if (!value) return [null, null];
                  return [`€${value.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`, name];
                }}
              />
              <Legend wrapperStyle={{ fontSize: 12, color: "#b8b8bc" }} />
              <Bar dataKey="invoiced" name="Invoiced" stackId="rev" fill="#4ADE80" radius={[0, 0, 0, 0]} />
              <Bar dataKey="pending" name="Pending" stackId="rev" fill="#FACC15" radius={[0, 0, 0, 0]} />
              <Bar dataKey="planned" name="Planned" stackId="rev" fill="#60A5FA" radius={[3, 3, 0, 0]} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {budgets.length > 0 && (
        <div className="rounded-lg bg-bg-card border border-border-subtle p-4 space-y-3">
          <h2 className="text-sm font-medium text-secondary">Project Time Budgets</h2>
          {budgets.map((b) => {
            const trackedPct = b.hours_budget > 0 ? Math.min(b.hours_tracked / b.hours_budget, 1) : 0;
            const plannedPct = b.hours_budget > 0 ? Math.min(b.hours_planned / b.hours_budget, 1 - trackedPct) : 0;
            const subtitle = b.hours_planned > 0
              ? `${b.hours_tracked.toFixed(1)}h + ${b.hours_planned.toFixed(1)}h planned / ${b.hours_budget.toFixed(0)}h`
              : `${b.hours_tracked.toFixed(1)}h / ${b.hours_budget.toFixed(0)}h`;

            return (
              <div key={b.project_id} className="space-y-1">
                <div className="flex items-baseline justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-medium truncate">{b.project}</span>
                    {b.budget_exceeded && <AlertTriangle size={12} className="text-amber-400 shrink-0" />}
                  </div>
                  <span className="text-xs text-secondary tabular-nums">{subtitle}</span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-bg-hover overflow-hidden flex">
                  <div className="h-full rounded-l-full bg-secondary transition-all duration-300"
                    style={{ width: `${trackedPct * 100}%` }} />
                  {plannedPct > 0 && (
                    <div className="h-full transition-all duration-300"
                      style={{
                        width: `${plannedPct * 100}%`,
                        background: "repeating-linear-gradient(45deg, #60A5FA 0, #60A5FA 2px, transparent 2px, transparent 5px)",
                        opacity: 0.5,
                      }} />
                  )}
                </div>
                {b.budget_exceeded && (
                  <div className="text-[11px] text-amber-400 font-medium">Budget exceeded</div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
