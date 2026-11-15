import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { Lock, Briefcase } from "lucide-react";
import { api } from "@/lib/api";
import { amt } from "@/lib/format";
import { TONE } from "@/lib/erp";

const ErpCtx = createContext(null);
export const useErp = () => useContext(ErpCtx);

const TABS = [["/erp", "Dashboard", "dashboard"], ["/erp/projects", "Projects", "projects"], ["/erp/parties", "Clients & Vendors", "parties"],
  ["/erp/quotations", "Quotations", "quotations"], ["/erp/invoices", "Invoices", "invoices"], ["/erp/purchases", "Purchases", "purchases"], ["/erp/expenses", "Expenses", "expenses"], ["/erp/reports", "Reports", "reports"], ["/erp/settings", "ERP Settings", "settings"]];

export const Badge = ({ s, testid }) => <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${TONE[s] || "bg-slate-100"}`} data-testid={testid}>{String(s).replace(/_/g, " ")}</span>;

const Locked = ({ st }) => (
  <div className="max-w-xl rounded-2xl border bg-white p-8 space-y-4" data-testid="erp-locked">
    <div className="h-12 w-12 rounded-xl bg-amber-100 flex items-center justify-center"><Lock className="h-6 w-6 text-amber-700" /></div>
    <h2 className="font-heading text-2xl font-bold">Unlock Projects / ERP</h2>
    <p className="text-slate-600">Project-wise quotations, advanced invoices with retention and running bills, client and vendor masters, project dashboards and documents. Every approved invoice and payment posts straight into your Easy Books ledgers.</p>
    <div className="text-3xl font-extrabold font-heading" data-testid="erp-plan-price">₹{amt(st.plan.price).replace(".00", "")} <span className="text-base font-medium text-slate-500">+ GST / year (₹{amt(st.plan.total)})</span></div>
    <p className="text-sm text-slate-500">Online payment is being set up. To activate now, contact Hannusoft; the platform admin can switch on the ERP plan for your business.</p>
  </div>
);

export default function ErpShell() {
  const [st, setSt] = useState(null);
  const load = useCallback(() => api.get("/erp/status").then((r) => setSt(r.data)), []);
  useEffect(() => { load(); }, [load]);
  if (!st) return <div className="text-slate-500">Loading...</div>;
  const perm = (a) => !!st.my_permissions?.[a];
  return (
    <ErpCtx.Provider value={{ st, perm, reload: load }}>
      <div className="space-y-6" data-testid="erp-shell">
        <div className="flex flex-wrap items-center gap-3">
          <Briefcase className="h-7 w-7 text-emerald-600" />
          <h1 className="font-heading text-3xl font-extrabold tracking-tight">Projects / ERP</h1>
          {st.industry && <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold" data-testid="erp-industry">{st.industry}</span>}
        </div>
        {!st.active ? <Locked st={st} /> : <>
          <div className="flex gap-1 overflow-x-auto border-b no-print">
            {TABS.filter(([, , id]) => id !== "settings" || perm("settings")).map(([to, l, id]) => (
              <NavLink key={id} to={to} end={to === "/erp"} data-testid={`erp-tab-${id}`}
                className={({ isActive }) => `whitespace-nowrap px-4 py-2.5 text-sm font-semibold border-b-2 -mb-px ${isActive ? "border-emerald-600 text-emerald-700" : "border-transparent text-slate-500 hover:text-slate-800"}`}>{l}</NavLink>
            ))}
          </div>
          <Outlet />
        </>}
      </div>
    </ErpCtx.Provider>
  );
}
