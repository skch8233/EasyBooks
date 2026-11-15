import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, errMsg } from "@/lib/api";
import { amt, dmyTime } from "@/lib/format";
import { Badge } from "@/pages/erp/ErpShell";

const Stat = ({ l, v, id, money }) => (
  <div className="rounded-xl border bg-white p-4" data-testid={`erp-stat-${id}`}>
    <div className="text-xs uppercase tracking-wide text-slate-500">{l}</div>
    <div className="font-heading text-2xl font-bold mt-1 font-mono">{money ? `₹${amt(v)}` : v}</div>
  </div>
);

export default function ErpDashboard() {
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  const load = () => { setErr(""); api.get("/erp/dashboard").then((r) => setD(r.data)).catch((e) => setErr(errMsg(e))); };
  useEffect(() => { load(); }, []);
  if (err) return <div className="text-sm text-red-700" data-testid="erp-dashboard-error">Could not load the ERP dashboard: {err} <button className="underline" onClick={load}>Try again</button></div>;
  if (!d) return <div className="text-slate-500" data-testid="erp-dashboard-loading">Loading...</div>;
  return (
    <div className="space-y-6" data-testid="erp-dashboard">
      <div className="grid gap-3 grid-cols-2 md:grid-cols-4 xl:grid-cols-6">
        <Stat l="Total projects" v={d.projects} id="projects" /><Stat l="Active" v={d.active_projects} id="active" /><Stat l="Completed" v={d.completed_projects} id="completed" />
        <Stat l="Clients" v={d.clients} id="clients" /><Stat l="Quotations" v={d.quotations} id="quotations" /><Stat l="Invoices" v={d.invoices} id="invoices" />
        <Stat l="Contract value" v={d.contract_value} id="contract" money /><Stat l="Invoiced" v={d.invoiced} id="invoiced" money /><Stat l="Received" v={d.received} id="received" money />
        <Stat l="Outstanding" v={d.outstanding} id="outstanding" money /><Stat l="Overdue invoices" v={d.overdue} id="overdue" /><Stat l="Profit (billed − costs)" v={d.profit} id="profit" money />
      </div>
      <div className="grid gap-3 grid-cols-2 md:grid-cols-4 xl:grid-cols-6">
        <Stat l="Purchase orders" v={d.purchase_orders} id="pos" /><Stat l="Purchases (bills)" v={d.purchases} id="purchases" money /><Stat l="Expenses" v={d.expenses} id="expenses" money />
        <Stat l="Unpaid bills" v={d.pending_bills} id="pending-bills" /><Stat l="PRs awaiting approval" v={d.pending_prs} id="pending-prs" /><Stat l="Vendors" v={d.vendors} id="vendors" />
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 rounded-xl border bg-white overflow-x-auto">
          <div className="px-4 py-3 font-semibold">Project profitability</div>
          <table className="w-full eb-table min-w-[640px]" data-testid="erp-project-table">
            <thead><tr><th>Project</th><th>Client</th><th>Status</th><th className="text-right">Contract</th><th className="text-right">Billed</th><th className="text-right">Outstanding</th><th className="text-right">Profit</th></tr></thead>
            <tbody>
              {d.by_project.length === 0 && <tr><td colSpan={7} className="text-center py-8 text-slate-500">No projects yet. <Link to="/erp/projects" className="text-primary underline">Create your first project</Link></td></tr>}
              {d.by_project.map((p) => <tr key={p.id}><td><Link className="text-primary font-medium" to={`/erp/projects/${p.id}`}>{p.code}</Link> {p.name}</td><td>{p.client_name}</td><td><Badge s={p.status} /></td>
                <td className="text-right font-mono">{amt(p.contract_value)}</td><td className="text-right font-mono">{amt(p.billed)}</td><td className="text-right font-mono">{amt(p.outstanding)}</td><td className="text-right font-mono">{amt(p.profit)}</td></tr>)}
            </tbody>
          </table>
        </div>
        <div className="rounded-xl border bg-white p-4" data-testid="erp-activity">
          <div className="font-semibold mb-2">Recent activity</div>
          {d.activity.length === 0 && <div className="text-sm text-slate-500">Nothing yet.</div>}
          <ul className="space-y-2 text-sm">{d.activity.map((a, i) => <li key={i} className="border-b pb-2"><b className="capitalize">{a.action.replace(/_/g, " ")}</b> · {a.entity.replace("erp_", "")} {a.note && <span className="text-slate-600">· {a.note}</span>}
            <div className="text-xs text-slate-400">{a.user_name} · {dmyTime(a.timestamp)}</div></li>)}</ul>
        </div>
      </div>
    </div>
  );
}
