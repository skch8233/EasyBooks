import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { FileDown, FileSpreadsheet } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { amt, dmy } from "@/lib/format";
import { exportExcel, exportPdf } from "@/lib/export";
import { useApp } from "@/context/AppContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sel, useProjects } from "@/pages/erp/Purchases";

const useParties = (kind) => {
  const [p, setP] = useState([]);
  useEffect(() => { api.get("/erp/parties", { params: { kind } }).then((r) => setP(r.data)); }, [kind]);
  return p;
};
const fmt = (c, v) => (c.num ? amt(v) : /date|due|valid|cancelled_at/.test(c.key) && /^\d{4}-\d{2}-\d{2}$/.test(v || "") ? dmy(v) : v);

export default function ErpReports() {
  const { settings } = useApp();
  const [sp, setSp] = useSearchParams();
  const [list, setList] = useState([]);
  const [f, setF] = useState({ from_date: "", to_date: "", project_id: "", client_id: "", vendor_id: "", status: "" });
  const [data, setData] = useState(null);
  const projects = useProjects();
  const clients = useParties("client");
  const vendors = useParties("vendor");
  const key = sp.get("r") || "project_profitability";
  const meta = list.find((x) => x.key === key);
  useEffect(() => { api.get("/erp/reports").then((r) => setList(r.data)); }, []);
  useEffect(() => {
    const params = Object.fromEntries(Object.entries(f).filter(([, v]) => v));
    api.get(`/erp/reports/${key}`, { params }).then((r) => setData(r.data)).catch((e) => toast.error(errMsg(e)));
  }, [key, f]);
  const sub = [f.from_date && `From ${dmy(f.from_date)}`, f.to_date && `To ${dmy(f.to_date)}`, f.project_id && projects.find((p) => p.id === f.project_id)?.code,
    f.client_id && clients.find((p) => p.id === f.client_id)?.company_name, f.vendor_id && vendors.find((p) => p.id === f.vendor_id)?.company_name, f.status].filter(Boolean).join(" · ") || "All records";
  const section = data && [{ columns: data.columns, rows: data.rows.map((r) => Object.fromEntries(data.columns.map((c) => [c.key, c.num ? r[c.key] : fmt(c, r[c.key])]))), footer: { ...data.footer, [data.columns[0].key]: "Total" } }];
  const pick = (k) => { setSp({ r: k }); setF({ ...f, status: "" }); };
  return (
    <div className="grid gap-5 lg:grid-cols-[260px_minmax(0,1fr)]" data-testid="erp-reports-page">
      <nav className="rounded-xl border bg-white p-2 h-fit space-y-0.5" data-testid="erp-report-list">
        {list.map((r) => <button key={r.key} onClick={() => pick(r.key)} data-testid={`erp-report-${r.key}`}
          className={`w-full text-left rounded-lg px-3 py-2 text-sm ${r.key === key ? "bg-slate-900 text-white font-semibold" : "hover:bg-slate-100"}`}>{r.title}</button>)}
      </nav>
      <div className="space-y-4 min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="font-heading text-xl font-bold" data-testid="erp-report-title">{data?.title || "Report"}</h2>
          <span className="text-sm text-slate-500" data-testid="erp-report-count">{data?.count ?? 0} rows</span>
          <div className="ml-auto flex gap-2">
            <Button variant="outline" disabled={!data} onClick={() => exportExcel(data.title, sub, section)} data-testid="erp-report-excel"><FileSpreadsheet className="h-4 w-4 mr-1" /> Excel</Button>
            <Button variant="outline" disabled={!data} onClick={() => exportPdf(data.title, sub, section, settings?.company_name)} data-testid="erp-report-pdf"><FileDown className="h-4 w-4 mr-1" /> PDF</Button>
          </div>
        </div>
        <div className="rounded-xl border bg-white p-4 grid gap-3 sm:grid-cols-3 xl:grid-cols-6" data-testid="erp-report-filters">
          <div className="space-y-1"><Label>From</Label><Input type="date" value={f.from_date} onChange={(e) => setF({ ...f, from_date: e.target.value })} data-testid="erp-filter-from" /></div>
          <div className="space-y-1"><Label>To</Label><Input type="date" value={f.to_date} onChange={(e) => setF({ ...f, to_date: e.target.value })} data-testid="erp-filter-to" /></div>
          {meta?.filters.includes("project_id") && <div className="space-y-1"><Label>Project</Label><Sel value={f.project_id} onChange={(v) => setF({ ...f, project_id: v })} placeholder="All projects" opts={projects.map((p) => [p.id, `${p.code} · ${p.name}`])} testid="erp-filter-project" /></div>}
          {meta?.filters.includes("client_id") && <div className="space-y-1"><Label>Client</Label><Sel value={f.client_id} onChange={(v) => setF({ ...f, client_id: v })} placeholder="All clients" opts={clients.map((p) => [p.id, p.company_name])} testid="erp-filter-client" /></div>}
          {meta?.filters.includes("vendor_id") && <div className="space-y-1"><Label>Vendor</Label><Sel value={f.vendor_id} onChange={(v) => setF({ ...f, vendor_id: v })} placeholder="All vendors" opts={vendors.map((p) => [p.id, p.company_name])} testid="erp-filter-vendor" /></div>}
          {meta?.statuses.length > 0 && <div className="space-y-1"><Label>Status</Label><Sel value={f.status} onChange={(v) => setF({ ...f, status: v })} placeholder="All statuses" opts={meta.statuses.map((s) => [s, s])} testid="erp-filter-status" /></div>}
          <div className="flex items-end"><Button variant="ghost" onClick={() => setF({ from_date: "", to_date: "", project_id: "", client_id: "", vendor_id: "", status: "" })} data-testid="erp-filter-clear">Clear filters</Button></div>
        </div>
        <div className="rounded-xl border bg-white overflow-x-auto">
          <table className="w-full eb-table text-sm" data-testid="erp-report-table">
            <thead><tr>{data?.columns.map((c) => <th key={c.key} className={c.num ? "text-right" : ""}>{c.label}</th>)}</tr></thead>
            <tbody>
              {data && data.rows.length === 0 && <tr><td colSpan={data.columns.length} className="text-center py-8 text-slate-500">No records for these filters.</td></tr>}
              {data?.rows.map((r, i) => <tr key={i} data-testid={`erp-report-row-${i}`}>{data.columns.map((c) => <td key={c.key} className={c.num ? "text-right font-mono whitespace-nowrap" : ""}>{fmt(c, r[c.key])}</td>)}</tr>)}
            </tbody>
            {data?.rows.length > 0 && <tfoot><tr className="font-semibold bg-slate-50" data-testid="erp-report-footer">{data.columns.map((c, i) => <td key={c.key} className={c.num ? "text-right font-mono" : ""}>{i === 0 ? "Total" : c.key in data.footer ? amt(data.footer[c.key]) : ""}</td>)}</tr></tfoot>}
          </table>
        </div>
      </div>
    </div>
  );
}
