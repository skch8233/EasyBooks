import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { FileUp, Plus } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { amt, dmy, todayIso } from "@/lib/format";
import { exportExcel } from "@/lib/export";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ReasonDialog } from "@/components/erp/InvoiceSide";
import { useErp, Badge } from "@/pages/erp/ErpShell";
import { Sel, useProjects, useVendors } from "@/pages/erp/Purchases";

const ExpenseForm = ({ init, cats, onClose, onSaved }) => {
  const projects = useProjects();
  const vendors = useVendors();
  const [banks, setBanks] = useState([]);
  const [f, setF] = useState(init);
  useEffect(() => { api.get("/ledgers").then((r) => { const b = r.data.filter((l) => ["cash", "bank"].includes(l.group)); setBanks(b); setF((x) => ({ ...x, payment_ledger_id: x.payment_ledger_id || b[0]?.id || "" })); }); }, []);
  const [saving, setSaving] = useState(false);
  const save = async () => {
    if (saving) return;
    setSaving(true);
    const body = { ...f, vendor_id: f.vendor_id || null, amount: Number(f.amount), gst_rate: Number(f.gst_rate || 0) };
    try { await (f.id ? api.put(`/erp/expenses/${f.id}`, body) : api.post("/erp/expenses", body)); toast.success("Expense saved as draft"); onSaved(); onClose(); } catch (e) { toast.error(errMsg(e)); } finally { setSaving(false); }
  };
  const inp = (k, l, t = "text") => <div className="space-y-1"><Label>{l}</Label><Input type={t} step="any" value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} data-testid={`expense-${k}-input`} /></div>;
  return (
    <div className="grid gap-3 sm:grid-cols-3" data-testid="expense-form">
      <div className="space-y-1"><Label>Project *</Label><Sel value={f.project_id} onChange={(v) => setF({ ...f, project_id: v })} placeholder="Select project" opts={projects.map((p) => [p.id, `${p.code} · ${p.name}`])} testid="expense-project-select" /></div>
      {inp("date", "Date", "date")}
      <div className="space-y-1"><Label>Category *</Label><Sel value={f.category} onChange={(v) => setF({ ...f, category: v })} placeholder="Select category" opts={cats.map((c) => [c, c])} testid="expense-category-select" /></div>
      {inp("paid_to", "Paid to (person / vendor) *")}
      <div className="space-y-1"><Label>Linked vendor (optional)</Label><Sel value={f.vendor_id || ""} onChange={(v) => setF({ ...f, vendor_id: v, paid_to: f.paid_to || vendors.find((x) => x.id === v)?.company_name || "" })} placeholder="None" opts={vendors.map((v) => [v.id, v.company_name])} testid="expense-vendor-select" /></div>
      {inp("amount", "Amount before GST (₹) *", "number")}{inp("gst_rate", "GST %", "number")}
      <div className="space-y-1"><Label>GST type</Label><Sel value={f.gst_type} onChange={(v) => setF({ ...f, gst_type: v })} opts={[["intra", "CGST + SGST"], ["inter", "IGST"]]} testid="expense-gsttype-select" /></div>
      <div className="space-y-1"><Label>Payment mode *</Label><Sel value={f.payment_ledger_id} onChange={(v) => setF({ ...f, payment_ledger_id: v })} opts={banks.map((b) => [b.id, b.name])} testid="expense-ledger-select" /></div>
      {inp("reference", "Bill / receipt no")}
      <div className="sm:col-span-2">{inp("notes", "Notes")}</div>
      <div className="sm:col-span-3 flex justify-end gap-2"><Button variant="outline" onClick={onClose}>Close</Button><Button onClick={save} data-testid="expense-save-button">Save</Button></div>
    </div>
  );
};

const Upload = ({ e, reload }) => {
  const ref = useRef();
  const up = async (file) => {
    const fd = new FormData(); fd.append("file", file);
    try { await api.post("/erp/documents", fd, { params: { project_id: e.project_id, expense_id: e.id } }); toast.success("Bill attached"); reload(); } catch (er) { toast.error(errMsg(er)); }
  };
  return <><input ref={ref} type="file" className="hidden" onChange={(x) => x.target.files[0] && up(x.target.files[0])} data-testid={`expense-file-${e.number}`} />
    <Button size="sm" variant="outline" onClick={() => ref.current.click()} data-testid={`expense-upload-${e.number}`}><FileUp className="h-4 w-4" /></Button></>;
};

export default function Expenses() {
  const { perm } = useErp();
  const [rows, setRows] = useState([]);
  const [cats, setCats] = useState([]);
  const [docs, setDocs] = useState({});
  const [fl, setFl] = useState({ project_id: "", category: "", status: "" });
  const [edit, setEdit] = useState(null);
  const [cancel, setCancel] = useState(null);
  const projects = useProjects();
  const load = useCallback(async () => {
    const { data } = await api.get("/erp/expenses", { params: { project_id: fl.project_id || undefined, category: fl.category || undefined, status: fl.status || undefined } });
    setRows(data);
    const r = await api.get("/erp/expense-documents");
    const m = {}; r.data.forEach((d) => { (m[d.expense_id] = m[d.expense_id] || []).push(d); }); setDocs(m);
  }, [fl]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { api.get("/erp/expense-categories").then((r) => setCats(r.data)); }, []);
  const posted = rows.filter((r) => r.status === "posted");
  const byCat = Object.entries(posted.reduce((a, r) => ({ ...a, [r.category]: (a[r.category] || 0) + r.totals.taxable }), {})).sort((a, b) => b[1] - a[1]);
  const [working, setWorking] = useState(null);
  const act = async (r, p, msg) => { if (working) return; setWorking(r.id); try { await api.post(`/erp/expenses/${r.id}/${p}`); toast.success(msg); load(); } catch (e) { toast.error(errMsg(e)); } finally { setWorking(null); } };
  const dl = async (d) => { const r = await api.get(`/erp/documents/${d.id}`, { responseType: "blob" }); const a = document.createElement("a"); a.href = URL.createObjectURL(r.data); a.download = d.name; a.click(); };
  const exportRows = () => exportExcel("Project Expenses", `As on ${dmy(todayIso())}`, [{
    columns: [["number", "Number"], ["date", "Date"], ["project", "Project"], ["category", "Category"], ["paid_to", "Paid to"], ["amount", "Amount", 1], ["gst", "GST", 1], ["total", "Total", 1], ["mode", "Mode"], ["status", "Status"]].map(([key, label, num]) => ({ key, label, num })),
    rows: rows.map((r) => ({ number: r.number, date: dmy(r.date), project: `${r.project_code} ${r.project_name}`, category: r.category, paid_to: r.paid_to, amount: r.totals.taxable, gst: r.totals.cgst + r.totals.sgst + r.totals.igst, total: r.totals.total, mode: r.payment_mode, status: r.status })),
  }]);
  return (
    <div className="space-y-4" data-testid="erp-expenses-page">
      <div className="flex flex-wrap gap-2 items-end">
        <div className="w-60"><Sel value={fl.project_id} onChange={(v) => setFl({ ...fl, project_id: v })} placeholder="All projects" opts={projects.map((p) => [p.id, `${p.code} · ${p.name}`])} testid="expenses-project-filter" /></div>
        <div className="w-48"><Sel value={fl.category} onChange={(v) => setFl({ ...fl, category: v })} placeholder="All categories" opts={cats.map((c) => [c, c])} testid="expenses-category-filter" /></div>
        <div className="w-40"><Sel value={fl.status} onChange={(v) => setFl({ ...fl, status: v })} placeholder="All statuses" opts={[["draft", "Draft"], ["posted", "Posted"], ["cancelled", "Cancelled"]]} testid="expenses-status-filter" /></div>
        <Button variant="outline" onClick={exportRows} data-testid="expenses-export">Export Excel</Button>
        {perm("create") && <Button className="ml-auto" onClick={() => setEdit({ project_id: fl.project_id, date: todayIso(), category: "", paid_to: "", vendor_id: "", amount: "", gst_rate: 0, gst_type: "intra", payment_ledger_id: "", reference: "", notes: "" })} data-testid="expense-new-button"><Plus className="h-4 w-4 mr-1" /> New expense</Button>}
      </div>
      <div className="flex flex-wrap gap-2" data-testid="expense-summary">
        <div className="rounded-xl border bg-white px-4 py-2"><div className="text-xs uppercase text-slate-500">Posted expenses</div><div className="font-mono font-bold">₹{amt(posted.reduce((s, r) => s + r.totals.taxable, 0))}</div></div>
        {byCat.map(([c, v]) => <div key={c} className="rounded-xl border bg-white px-4 py-2"><div className="text-xs uppercase text-slate-500">{c}</div><div className="font-mono">₹{amt(v)}</div></div>)}
      </div>
      <div className="rounded-xl border bg-white overflow-x-auto">
        <table className="w-full eb-table min-w-[980px]" data-testid="expenses-table">
          <thead><tr><th>Number</th><th>Date</th><th>Project</th><th>Category</th><th>Paid to</th><th className="text-right">Amount</th><th className="text-right">GST</th><th>Mode</th><th>Bills</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan={11} className="text-center py-8 text-slate-500">No expenses yet.</td></tr>}
            {rows.map((r) => <tr key={r.id} data-testid={`expense-row-${r.number}`}><td className="font-mono font-semibold">{r.number}</td><td>{dmy(r.date)}</td><td>{r.project_code}</td><td>{r.category}</td><td>{r.paid_to}</td>
              <td className="text-right font-mono">{amt(r.totals.taxable)}</td><td className="text-right font-mono">{amt(r.totals.cgst + r.totals.sgst + r.totals.igst)}</td><td>{r.payment_mode}</td>
              <td className="text-xs">{(docs[r.id] || []).map((d) => <button key={d.id} className="block text-primary underline" onClick={() => dl(d)}>{d.name}</button>)}</td>
              <td><Badge s={r.status} />{r.voucher_no && <div className="text-[10px] text-slate-500">{r.voucher_no}</div>}</td>
              <td className="whitespace-nowrap space-x-1">
                {perm("create") && r.status !== "cancelled" && <Upload e={r} reload={load} />}
                {r.status === "draft" && perm("edit") && <Button size="sm" variant="outline" onClick={() => setEdit(r)} data-testid={`expense-edit-${r.number}`}>Edit</Button>}
                {r.status === "draft" && perm("finalize") && <Button size="sm" disabled={working === r.id} onClick={() => act(r, "post", "Expense posted to accounts")} data-testid={`expense-post-${r.number}`}>Post</Button>}
                {r.status !== "cancelled" && perm("cancel") && <Button size="sm" variant="outline" className="text-red-600" onClick={() => setCancel(r)} data-testid={`expense-cancel-${r.number}`}>Cancel</Button>}
              </td></tr>)}
          </tbody>
        </table>
      </div>
      <Dialog open={!!edit} onOpenChange={(o) => !o && setEdit(null)}><DialogContent className="max-w-3xl"><DialogHeader><DialogTitle>{edit?.id ? `Edit ${edit.number}` : "New project expense"}</DialogTitle></DialogHeader>
        {edit && <ExpenseForm init={{ ...edit, vendor_id: edit.vendor_id || "" }} cats={cats} onClose={() => setEdit(null)} onSaved={load} />}</DialogContent></Dialog>
      <ReasonDialog open={!!cancel} onClose={() => setCancel(null)} title={`Cancel ${cancel?.number}`} note="If posted, the payment entry in EASYTALLY BOOKS is cancelled too."
        onOk={async (reason) => { try { await api.post(`/erp/expenses/${cancel.id}/cancel`, { reason }); setCancel(null); load(); } catch (e) { toast.error(errMsg(e)); } }} />
    </div>
  );
}
