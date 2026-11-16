import { useCallback, useEffect, useState } from "react";
import { fillEmpty, useGstinAutofill } from "@/lib/gstin";
import { toast } from "sonner";
import { Plus, Search } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { amt, dmy, STATES } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useErp, Badge } from "@/pages/erp/ErpShell";
import { DocList } from "@/pages/erp/ProjectView";

const EMPTY = { kind: "client", company_name: "", gstin: "", pan: "", address: "", state: "", contact_person: "", mobile: "", email: "", opening_balance: 0, opening_type: "Dr", payment_terms_days: 30 };
const FIELDS = [["company_name", "Company name *"], ["contact_person", "Contact person"], ["mobile", "Mobile"], ["email", "Email"], ["gstin", "GSTIN"], ["pan", "PAN"],
  ["payment_terms_days", "Payment terms (days)"], ["opening_balance", "Opening balance (₹)"]];

const PartyForm = ({ init, onSaved, onClose }) => {
  const [f, setF] = useState(init);
  useGstinAutofill(f.gstin, (d) => setF((x) => ({ ...fillEmpty(x, { company_name: x.id ? "" : d.name, address: d.address, mobile: d.phone, email: d.email, contact_person: d.contact_person }), pan: d.pan || x.pan, state: d.state || x.state })));
  const save = async (e) => {
    e.preventDefault();
    const body = { ...f, opening_balance: Number(f.opening_balance || 0), payment_terms_days: Number(f.payment_terms_days || 0), gstin: f.gstin.toUpperCase(), pan: f.pan.toUpperCase() };
    try { await (f.id ? api.put(`/erp/parties/${f.id}`, body) : api.post("/erp/parties", body)); toast.success("Saved"); onSaved(); onClose(); } catch (er) { toast.error(errMsg(er)); }
  };
  return (
    <form onSubmit={save} className="grid gap-3 sm:grid-cols-2" data-testid="party-form">
      {!f.id && <div className="sm:col-span-2 flex gap-2">{["client", "vendor"].map((k) => <button type="button" key={k} onClick={() => setF({ ...f, kind: k, opening_type: k === "client" ? "Dr" : "Cr" })}
        className={`rounded-full border px-4 py-1.5 text-sm capitalize ${f.kind === k ? "bg-primary text-white border-primary" : ""}`} data-testid={`party-kind-${k}`}>{k}</button>)}</div>}
      {FIELDS.map(([k, l]) => <div key={k} className="space-y-1"><Label>{l}</Label><Input required={k === "company_name"} disabled={k === "company_name" && !!f.id} value={f[k]}
        onChange={(e) => setF({ ...f, [k]: e.target.value })} className="h-10" data-testid={`party-${k}-input`} /></div>)}
      <div className="space-y-1"><Label>State</Label><select className="h-10 w-full rounded-md border px-2 bg-white" value={f.state} onChange={(e) => setF({ ...f, state: e.target.value })} data-testid="party-state-select">
        <option value="">Select state</option>{STATES.map((s) => <option key={s.name || s} value={s.name || s}>{s.name || s}</option>)}</select></div>
      <div className="space-y-1"><Label>Opening balance is</Label><select className="h-10 w-full rounded-md border px-2 bg-white" value={f.opening_type} onChange={(e) => setF({ ...f, opening_type: e.target.value })} data-testid="party-opening-type">
        <option value="Dr">Dr (they owe us)</option><option value="Cr">Cr (we owe them)</option></select></div>
      <div className="sm:col-span-2 space-y-1"><Label>Address</Label><textarea className="w-full rounded-md border p-2 text-sm" rows={2} value={f.address} onChange={(e) => setF({ ...f, address: e.target.value })} data-testid="party-address-input" /></div>
      <div className="sm:col-span-2 flex justify-end gap-2"><Button type="button" variant="outline" onClick={onClose}>Close</Button><Button type="submit" data-testid="party-save-button">Save</Button></div>
    </form>
  );
};

const Detail = ({ id }) => {
  const [d, setD] = useState(null);
  const load = useCallback(() => api.get(`/erp/parties/${id}`).then((r) => setD(r.data)), [id]);
  useEffect(() => { load(); }, [load]);
  if (!d) return null;
  return (
    <div className="space-y-4 text-sm" data-testid="party-history">
      <div><b>Projects ({d.projects.length})</b>{d.projects.map((p) => <div key={p.id}><a className="text-primary" href={`/erp/projects/${p.id}`}>{p.code}</a> {p.name} · <Badge s={p.status} /></div>)}</div>
      <div><b>Quotations ({d.quotations.length})</b>{d.quotations.map((q) => <div key={q.id}><a className="text-primary" href={`/erp/quotations/${q.id}`}>{q.number}</a> · {dmy(q.date)} · ₹{amt(q.totals.total)} · <Badge s={q.status} /></div>)}</div>
      <div><b>Invoices ({d.invoices.length})</b>{d.invoices.map((i) => <div key={i.id}><a className="text-primary" href={`/erp/invoices/${i.id}`}>{i.number || "Draft"}</a> · {dmy(i.date)} · ₹{amt(i.totals.net_payable)} · <Badge s={i.status} /></div>)}</div>
      <DocList docs={d.documents} partyId={id} onChange={load} />
    </div>
  );
};

export default function Parties() {
  const { perm } = useErp();
  const [rows, setRows] = useState([]);
  const [kind, setKind] = useState("client");
  const [q, setQ] = useState("");
  const [edit, setEdit] = useState(null);
  const [view, setView] = useState(null);
  const load = useCallback(() => api.get("/erp/parties", { params: { kind, q: q || undefined } }).then((r) => setRows(r.data)), [kind, q]);
  useEffect(() => { load(); }, [load]);
  return (
    <div className="space-y-4" data-testid="erp-parties-page">
      <div className="flex flex-wrap gap-2 items-center">
        {["client", "vendor"].map((k) => <button key={k} onClick={() => setKind(k)} className={`rounded-full border px-4 py-2 text-sm font-medium capitalize ${kind === k ? "bg-slate-900 text-white" : "bg-white"}`} data-testid={`parties-filter-${k}`}>{k}s</button>)}
        <div className="relative ml-auto"><Search className="h-4 w-4 absolute left-3 top-3 text-slate-400" /><Input className="h-10 pl-9 w-64" placeholder="Search" value={q} onChange={(e) => setQ(e.target.value)} data-testid="parties-search" /></div>
        {perm("create") && <Button onClick={() => setEdit({ ...EMPTY, kind, opening_type: kind === "client" ? "Dr" : "Cr" })} data-testid="party-new-button"><Plus className="h-4 w-4 mr-1" /> New {kind}</Button>}
      </div>
      <div className="rounded-xl border bg-white overflow-x-auto">
        <table className="w-full eb-table min-w-[820px]" data-testid="parties-table">
          <thead><tr><th>Company</th><th>Contact</th><th>GSTIN / PAN</th><th>State</th><th className="text-right">Opening</th><th>Terms</th><th></th></tr></thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan={7} className="text-center py-8 text-slate-500">No {kind}s yet.</td></tr>}
            {rows.map((p) => <tr key={p.id} data-testid={`party-row-${p.id}`}><td className="font-medium">{p.company_name}</td><td>{p.contact_person}<div className="text-xs text-slate-500">{p.mobile} {p.email}</div></td>
              <td className="font-mono text-xs">{p.gstin}<div>{p.pan}</div></td><td>{p.state}</td><td className="text-right font-mono">{amt(p.opening_balance)} {p.opening_type}</td><td>{p.payment_terms_days} days</td>
              <td className="whitespace-nowrap space-x-1"><Button size="sm" variant="outline" onClick={() => setView(p)} data-testid={`party-view-${p.id}`}>History</Button>
                {perm("edit") && <Button size="sm" variant="outline" onClick={() => setEdit(p)} data-testid={`party-edit-${p.id}`}>Edit</Button>}</td></tr>)}
          </tbody>
        </table>
      </div>
      <Dialog open={!!edit} onOpenChange={(o) => !o && setEdit(null)}><DialogContent className="max-w-2xl"><DialogHeader><DialogTitle>{edit?.id ? "Edit" : "New"} {edit?.kind}</DialogTitle></DialogHeader>
        {edit && <PartyForm init={edit} onSaved={load} onClose={() => setEdit(null)} />}</DialogContent></Dialog>
      <Dialog open={!!view} onOpenChange={(o) => !o && setView(null)}><DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto"><DialogHeader><DialogTitle>{view?.company_name}: history</DialogTitle></DialogHeader>
        {view && <Detail id={view.id} />}</DialogContent></Dialog>
    </div>
  );
}
