import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Plus, Search } from "lucide-react";
import { api } from "@/lib/api";
import { amt, dmy } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useErp, Badge } from "@/pages/erp/ErpShell";

export default function DocRegister({ kind }) {
  const inv = kind === "invoices";
  const { perm } = useErp();
  const nav = useNavigate();
  const [rows, setRows] = useState([]);
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const statuses = inv ? ["", "draft", "finalized", "cancelled", "overdue"] : ["", "draft", "sent", "accepted", "rejected", "expired", "converted", "cancelled"];
  const load = useCallback(() => api.get(`/erp/${kind}`, { params: { status: status && status !== "overdue" ? status : undefined, overdue: status === "overdue" || undefined, q: q || undefined } })
    .then((r) => setRows(r.data)), [kind, status, q]);
  useEffect(() => { load(); }, [load]);
  return (
    <div className="space-y-4" data-testid={`erp-${kind}-page`}>
      <div className="flex flex-wrap gap-2 items-center">
        {statuses.map((s) => <button key={s || "all"} onClick={() => setStatus(s)} className={`rounded-full border px-3 py-1.5 text-sm capitalize ${status === s ? "bg-slate-900 text-white" : "bg-white"}`} data-testid={`${kind}-filter-${s || "all"}`}>{s || "All"}</button>)}
        <div className="relative ml-auto"><Search className="h-4 w-4 absolute left-3 top-3 text-slate-400" /><Input className="h-10 pl-9 w-60" placeholder="Search number, client, project" value={q} onChange={(e) => setQ(e.target.value)} data-testid={`${kind}-search`} /></div>
        {perm("create") && <Link to={`/erp/${kind}/new`}><Button data-testid={`${kind}-new-button`}><Plus className="h-4 w-4 mr-1" /> New {inv ? "invoice" : "quotation"}</Button></Link>}
      </div>
      <div className="rounded-xl border bg-white overflow-x-auto">
        <table className="w-full eb-table min-w-[900px]" data-testid={`${kind}-table`}>
          <thead><tr><th>Number</th><th>Date</th><th>Client</th><th>Project</th><th className="text-right">{inv ? "Net payable" : "Total"}</th>{inv && <th className="text-right">Balance</th>}<th>Status</th></tr></thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan={7} className="text-center py-8 text-slate-500">Nothing here yet.</td></tr>}
            {rows.map((r) => <tr key={r.id} className="cursor-pointer hover:bg-slate-50" onClick={() => nav(`/erp/${kind}/${r.id}`)} data-testid={`${kind}-row-${r.id}`}>
              <td className="font-mono font-semibold text-primary">{r.number || "Draft"}</td><td className="font-mono text-xs">{dmy(r.date)}{inv && r.due_date ? ` → ${dmy(r.due_date)}` : ""}</td>
              <td>{r.client_name}</td><td>{r.project_code} {r.project_name}</td><td className="text-right font-mono">{amt(inv ? r.totals.net_payable : r.totals.total)}</td>
              {inv && <td className="text-right font-mono">{r.status === "finalized" ? amt(r.balance) : "-"}</td>}
              <td className="space-x-1"><Badge s={r.status} />{r.pay_status && <Badge s={r.pay_status} />}{r.overdue && <Badge s="overdue" />}</td></tr>)}
          </tbody>
        </table>
      </div>
    </div>
  );
}
