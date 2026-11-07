import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { TrendingUp, TrendingDown, Wallet, Landmark, Users, Truck, PiggyBank } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { inr, dmy, VTYPES, VT } from "@/lib/format";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const Kpi = ({ label, value, icon: I, tone, testid, to }) => (
  <Link to={to} data-testid={testid} className="fade-up rounded-xl border bg-white p-5 hover:shadow-md hover:-translate-y-0.5 transition-[box-shadow,transform]">
    <div className="flex items-center justify-between">
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span>
      <span className={`h-9 w-9 rounded-lg flex items-center justify-center ${tone}`}><I className="h-4 w-4" /></span>
    </div>
    <div className="mt-3 num text-2xl font-semibold tracking-tight" data-testid={`${testid}-value`}>{inr(value)}</div>
  </Link>
);

export default function Dashboard() {
  const { fy, canWrite } = useApp();
  const [d, setD] = useState(null);
  const nav = useNavigate();
  useEffect(() => {
    if (fy) api.get("/reports/dashboard", { params: { from_date: fy.start_date, to_date: fy.end_date } }).then((r) => setD(r.data));
  }, [fy]);
  if (!d) return <div className="text-slate-500" data-testid="dashboard-loading">Loading dashboard...</div>;
  const chart = d.monthly.map((m) => ({ ...m, name: MONTHS[Number(m.month.slice(5)) - 1] }));

  return (
    <div className="space-y-8" data-testid="dashboard-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl sm:text-4xl font-extrabold tracking-tight">Dashboard</h1>
          <p className="text-slate-500 mt-1">FY {fy.name} · {dmy(fy.start_date)} to {dmy(fy.end_date)}</p>
        </div>
        <div className="rounded-xl border bg-white px-5 py-3">
          <div className="text-xs font-semibold uppercase text-slate-500">Net Profit (FY)</div>
          <div className={`num text-xl font-semibold ${d.net_profit >= 0 ? "text-emerald-700" : "text-red-600"}`} data-testid="kpi-net-profit">{inr(d.net_profit)}</div>
        </div>
      </div>

      {canWrite && (
        <div className="grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-8 gap-3" data-testid="quick-voucher-actions">
          {VTYPES.map((v) => (
            <button key={v.key} onClick={() => nav(`/voucher/${v.key}`)} data-testid={`quick-${v.key}-button`}
              className={`flex items-center gap-2 rounded-lg border px-4 py-3.5 text-sm font-semibold hover:shadow-sm active:scale-[0.98] transition-[box-shadow,transform] ${v.color}`}>
              <v.icon className="h-4 w-4" /> {v.label}
            </button>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
        <Kpi label="Total Sales" value={d.total_sales} icon={TrendingUp} tone="bg-emerald-50 text-emerald-700" testid="kpi-total-sales" to="/reports/sales-register" />
        <Kpi label="Total Purchases" value={d.total_purchases} icon={TrendingDown} tone="bg-amber-50 text-amber-700" testid="kpi-total-purchases" to="/reports/purchase-register" />
        <Kpi label="Cash Balance" value={d.cash_balance} icon={Wallet} tone="bg-sky-50 text-sky-700" testid="kpi-cash-balance" to="/reports/cash-book" />
        <Kpi label="Bank Balance" value={d.bank_balance} icon={Landmark} tone="bg-indigo-50 text-indigo-700" testid="kpi-bank-balance" to="/reports/bank-book" />
        <Kpi label="Customer Outstanding" value={d.receivables} icon={Users} tone="bg-teal-50 text-teal-700" testid="kpi-receivables" to="/reports/receivables" />
        <Kpi label="Supplier Outstanding" value={d.payables} icon={Truck} tone="bg-rose-50 text-rose-700" testid="kpi-payables" to="/reports/payables" />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-5 gap-6">
        <div className="xl:col-span-3 rounded-xl border bg-white p-5" data-testid="monthly-chart">
          <div className="flex items-center gap-2 mb-4"><PiggyBank className="h-4 w-4 text-slate-500" /><h3 className="font-heading font-semibold text-lg">Monthly Income vs Expenses</h3></div>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chart}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0" />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => (Math.abs(v) >= 100000 ? `${(v / 100000).toFixed(1)}L` : v >= 1000 ? `${Math.round(v / 1000)}k` : v)} />
                <Tooltip formatter={(v) => inr(v)} />
                <Legend />
                <Bar dataKey="income" name="Income" fill="#059669" radius={[4, 4, 0, 0]} />
                <Bar dataKey="expense" name="Expenses" fill="#DC2626" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="xl:col-span-2 rounded-xl border bg-white p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-heading font-semibold text-lg">Recent Vouchers</h3>
            <Link to="/vouchers" className="text-sm text-primary font-medium hover:underline" data-testid="view-all-vouchers-link">View all</Link>
          </div>
          {d.recent.length === 0 ? <p className="text-sm text-slate-500 py-8 text-center" data-testid="recent-empty">No vouchers yet. Create your first entry.</p> : (
            <table className="w-full eb-table" data-testid="recent-vouchers-table">
              <tbody>
                {d.recent.map((v) => (
                  <tr key={v.id}>
                    <td><div className="font-mono text-xs text-slate-500">{dmy(v.date)}</div><div className="font-medium truncate max-w-[180px]">{v.party_name}</div></td>
                    <td><span className="text-xs font-semibold">{VT[v.voucher_type]?.label}</span><div className="font-mono text-[11px] text-slate-500">{v.voucher_no}</div></td>
                    <td className="text-right num">{inr(v.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
