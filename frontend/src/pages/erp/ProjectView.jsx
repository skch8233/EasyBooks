import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Download, FileUp, Pencil, Plus, Trash2 } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { amt, dmy, dmyTime } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useErp, Badge } from "@/pages/erp/ErpShell";
import { ProjectForm } from "@/pages/erp/Projects";

export const DocList = ({ docs, projectId, partyId, onChange }) => {
  const { perm } = useErp();
  const ref = useRef();
  const upload = async (file) => {
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try { await api.post("/erp/documents", fd, { params: { project_id: projectId || "", party_id: partyId || "" } }); toast.success("Uploaded"); onChange(); } catch (e) { toast.error(errMsg(e)); }
    ref.current.value = "";
  };
  const download = async (d) => {
    const r = await api.get(`/erp/documents/${d.id}`, { responseType: "blob" });
    const a = document.createElement("a"); a.href = URL.createObjectURL(r.data); a.download = d.name; a.click();
  };
  const remove = async (d) => { if (!window.confirm(`Delete ${d.name}?`)) return; await api.delete(`/erp/documents/${d.id}`); onChange(); };
  return (
    <div className="rounded-xl border bg-white p-4 space-y-2" data-testid="documents-panel">
      <div className="flex items-center"><b>Documents ({docs.length})</b>
        {perm("create") && <><input ref={ref} type="file" className="hidden" onChange={(e) => upload(e.target.files[0])} data-testid="document-file-input" />
          <Button size="sm" variant="outline" className="ml-auto" onClick={() => ref.current.click()} data-testid="document-upload-button"><FileUp className="h-4 w-4 mr-1" /> Upload</Button></>}</div>
      {docs.length === 0 && <div className="text-sm text-slate-500">Drawings, contracts, work orders, photos (up to 15 MB each).</div>}
      {docs.map((d) => <div key={d.id} className="flex items-center gap-2 text-sm border-t pt-2" data-testid={`document-${d.id}`}><span className="flex-1 truncate">{d.name}</span>
        <span className="text-xs text-slate-400">{(d.size / 1024).toFixed(0)} KB · {dmy(d.created_at)}</span>
        <button onClick={() => download(d)} className="p-1 text-primary" data-testid={`document-download-${d.id}`}><Download className="h-4 w-4" /></button>
        {perm("delete") && <button onClick={() => remove(d)} className="p-1 text-red-600" data-testid={`document-delete-${d.id}`}><Trash2 className="h-4 w-4" /></button>}</div>)}
    </div>
  );
};

const Kpi = ({ l, v, id }) => <div className="rounded-xl border bg-white p-4" data-testid={`project-kpi-${id}`}><div className="text-xs uppercase text-slate-500">{l}</div><div className="font-heading text-xl font-bold font-mono mt-1">₹{amt(v)}</div></div>;

export default function ProjectView() {
  const { id } = useParams();
  const { perm } = useErp();
  const [p, setP] = useState(null);
  const [edit, setEdit] = useState(false);
  const load = useCallback(() => api.get(`/erp/projects/${id}`).then((r) => setP(r.data)), [id]);
  useEffect(() => { load(); }, [load]);
  if (!p) return <div className="text-slate-500">Loading...</div>;
  const n = p.numbers;
  return (
    <div className="space-y-5" data-testid="project-dashboard">
      <div className="flex flex-wrap items-start gap-3">
        <div><div className="font-mono text-sm text-slate-500" data-testid="project-code">{p.code}</div><h2 className="font-heading text-2xl font-bold">{p.name}</h2>
          <div className="text-sm text-slate-600">{[p.client_name, p.location, p.manager && `PM: ${p.manager}`, (p.start_date || p.end_date) && `${dmy(p.start_date) || "?"} → ${dmy(p.end_date) || "?"}`].filter(Boolean).join(" · ")}</div></div>
        <Badge s={p.status} testid="project-status" />
        <div className="ml-auto flex flex-wrap gap-2">
          {perm("create") && <Link to={`/erp/quotations/new?project=${p.id}`}><Button variant="outline" data-testid="project-new-quote"><Plus className="h-4 w-4 mr-1" /> Quotation</Button></Link>}
          {perm("create") && <Link to={`/erp/invoices/new?project=${p.id}`}><Button data-testid="project-new-invoice"><Plus className="h-4 w-4 mr-1" /> Invoice</Button></Link>}
          {perm("edit") && <Button variant="outline" onClick={() => setEdit(true)} data-testid="project-edit-button"><Pencil className="h-4 w-4 mr-1" /> Edit</Button>}
        </div>
      </div>
      <div className="h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full bg-emerald-500" style={{ width: `${p.progress}%` }} data-testid="project-progress" /></div>
      <div className="grid gap-3 grid-cols-2 md:grid-cols-4 xl:grid-cols-5">
        <Kpi l="Contract value" v={n.contract_value} id="contract" /><Kpi l="Quoted" v={n.quoted_value} id="quoted" /><Kpi l="Billed (incl GST)" v={n.billed} id="billed" />
        <Kpi l="Received" v={n.received} id="received" /><Kpi l="Outstanding" v={n.outstanding} id="outstanding" /><Kpi l="Balance to bill" v={n.balance_to_bill} id="to-bill" />
        <Kpi l="Credit notes" v={n.credit_notes} id="cn" /><Kpi l="Purchases (Phase B)" v={n.purchases} id="purchases" /><Kpi l="Expenses (Phase B)" v={n.expenses} id="expenses" /><Kpi l="Profit" v={n.profit} id="profit" />
      </div>
      {p.description && <p className="text-sm text-slate-600 whitespace-pre-line">{p.description}</p>}
      <div className="grid gap-5 lg:grid-cols-2">
        <div className="rounded-xl border bg-white overflow-x-auto"><div className="px-4 py-3 font-semibold">Quotations ({p.quotations.length})</div>
          <table className="w-full eb-table"><tbody>{p.quotations.map((q) => <tr key={q.id}><td><Link className="text-primary font-mono" to={`/erp/quotations/${q.id}`}>{q.number}</Link></td><td>{dmy(q.date)}</td><td className="text-right font-mono">{amt(q.totals.total)}</td><td><Badge s={q.status} /></td></tr>)}
            {p.quotations.length === 0 && <tr><td className="text-slate-500 text-center py-4">None</td></tr>}</tbody></table></div>
        <div className="rounded-xl border bg-white overflow-x-auto"><div className="px-4 py-3 font-semibold">Invoices ({p.invoices.length})</div>
          <table className="w-full eb-table"><tbody>{p.invoices.map((i) => <tr key={i.id}><td><Link className="text-primary font-mono" to={`/erp/invoices/${i.id}`}>{i.number || "Draft"}</Link></td><td>{dmy(i.date)}</td><td className="text-right font-mono">{amt(i.totals.net_payable)}</td><td><Badge s={i.status} /></td></tr>)}
            {p.invoices.length === 0 && <tr><td className="text-slate-500 text-center py-4">None</td></tr>}</tbody></table></div>
        <DocList docs={p.documents} projectId={p.id} onChange={load} />
        <div className="rounded-xl border bg-white p-4"><b>Activity</b><ul className="mt-2 space-y-1 text-sm">{p.activity.map((a, i) => <li key={i}><span className="capitalize">{a.action.replace(/_/g, " ")}</span> · {a.note} <span className="text-xs text-slate-400">{a.user_name} {dmyTime(a.timestamp)}</span></li>)}</ul></div>
      </div>
      <Dialog open={edit} onOpenChange={setEdit}><DialogContent className="max-w-2xl"><DialogHeader><DialogTitle>Edit project</DialogTitle></DialogHeader>
        {edit && <ProjectForm init={p} onSaved={load} onClose={() => setEdit(false)} />}</DialogContent></Dialog>
    </div>
  );
}
