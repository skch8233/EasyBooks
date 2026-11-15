import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Plus, Search } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { amt, dmy } from "@/lib/format";
import { PROJECT_STATUSES } from "@/lib/erp";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useErp, Badge } from "@/pages/erp/ErpShell";

export const EMPTY_PROJECT = { code: "", name: "", client_id: "", manager: "", location: "", description: "", start_date: "", end_date: "", contract_value: 0, status: "Planning", progress: 0 };

export const ProjectForm = ({ init, onSaved, onClose }) => {
  const [f, setF] = useState(init);
  const [clients, setClients] = useState([]);
  useEffect(() => { api.get("/erp/parties", { params: { kind: "client" } }).then((r) => setClients(r.data)); }, []);
  const save = async (e) => {
    e.preventDefault();
    const body = { ...f, contract_value: Number(f.contract_value || 0), progress: Number(f.progress || 0) };
    try { const { data } = await (f.id ? api.put(`/erp/projects/${f.id}`, body) : api.post("/erp/projects", body)); toast.success(`Project ${data.code} saved`); onSaved(data); onClose(); } catch (er) { toast.error(errMsg(er)); }
  };
  const inp = (k, l, type = "text") => <div className="space-y-1"><Label>{l}</Label><Input type={type} className="h-10" value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} data-testid={`project-${k}-input`} /></div>;
  return (
    <form onSubmit={save} className="grid gap-3 sm:grid-cols-2" data-testid="project-form">
      <div className="space-y-1"><Label>Project name *</Label><Input required className="h-10" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} data-testid="project-name-input" /></div>
      {inp("code", "Project code (blank = automatic)")}
      <div className="space-y-1"><Label>Client *</Label><select required className="h-10 w-full rounded-md border px-2 bg-white" value={f.client_id} onChange={(e) => setF({ ...f, client_id: e.target.value })} data-testid="project-client-select">
        <option value="">Select client</option>{clients.map((c) => <option key={c.id} value={c.id}>{c.company_name}</option>)}</select>
        {clients.length === 0 && <div className="text-xs text-amber-700">Add a client first in Clients & Vendors.</div>}</div>
      {inp("manager", "Project manager")}{inp("location", "Location")}{inp("contract_value", "Contract value (₹, before GST)", "number")}
      {inp("start_date", "Start date", "date")}{inp("end_date", "Completion date", "date")}
      <div className="space-y-1"><Label>Status</Label><select className="h-10 w-full rounded-md border px-2 bg-white" value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })} data-testid="project-status-select">
        {PROJECT_STATUSES.map((s) => <option key={s}>{s}</option>)}</select></div>
      {inp("progress", "Progress %", "number")}
      <div className="sm:col-span-2 space-y-1"><Label>Description</Label><textarea rows={3} className="w-full rounded-md border p-2 text-sm" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} data-testid="project-description-input" /></div>
      <div className="sm:col-span-2 flex justify-end gap-2"><Button type="button" variant="outline" onClick={onClose}>Close</Button><Button type="submit" data-testid="project-save-button">Save project</Button></div>
    </form>
  );
};

export default function Projects() {
  const { perm } = useErp();
  const nav = useNavigate();
  const [rows, setRows] = useState([]);
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [edit, setEdit] = useState(null);
  const load = useCallback(() => api.get("/erp/projects", { params: { status: status || undefined, q: q || undefined } }).then((r) => setRows(r.data)), [status, q]);
  useEffect(() => { load(); }, [load]);
  return (
    <div className="space-y-4" data-testid="erp-projects-page">
      <div className="flex flex-wrap gap-2 items-center">
        {["", ...PROJECT_STATUSES].map((s) => <button key={s || "all"} onClick={() => setStatus(s)} className={`rounded-full border px-3 py-1.5 text-sm ${status === s ? "bg-slate-900 text-white" : "bg-white"}`} data-testid={`projects-filter-${s || "all"}`}>{s || "All"}</button>)}
        <div className="relative ml-auto"><Search className="h-4 w-4 absolute left-3 top-3 text-slate-400" /><Input className="h-10 pl-9 w-60" placeholder="Search code, name, client" value={q} onChange={(e) => setQ(e.target.value)} data-testid="projects-search" /></div>
        {perm("create") && <Button onClick={() => setEdit({ ...EMPTY_PROJECT })} data-testid="project-new-button"><Plus className="h-4 w-4 mr-1" /> New project</Button>}
      </div>
      <div className="rounded-xl border bg-white overflow-x-auto">
        <table className="w-full eb-table min-w-[860px]" data-testid="projects-table">
          <thead><tr><th>Code</th><th>Project</th><th>Client</th><th>Manager</th><th>Dates</th><th className="text-right">Contract (₹)</th><th>Status</th></tr></thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan={7} className="text-center py-8 text-slate-500">No projects found.</td></tr>}
            {rows.map((p) => <tr key={p.id} className="cursor-pointer hover:bg-slate-50" onClick={() => nav(`/erp/projects/${p.id}`)} data-testid={`project-row-${p.code}`}>
              <td className="font-mono font-semibold"><Link to={`/erp/projects/${p.id}`} className="text-primary">{p.code}</Link></td><td className="font-medium">{p.name}<div className="text-xs text-slate-500">{p.location}</div></td>
              <td>{p.client_name}</td><td>{p.manager}</td><td className="text-xs font-mono">{dmy(p.start_date)} → {dmy(p.end_date)}</td><td className="text-right font-mono">{amt(p.contract_value)}</td><td><Badge s={p.status} /></td></tr>)}
          </tbody>
        </table>
      </div>
      <Dialog open={!!edit} onOpenChange={(o) => !o && setEdit(null)}><DialogContent className="max-w-2xl"><DialogHeader><DialogTitle>New project</DialogTitle></DialogHeader>
        {edit && <ProjectForm init={edit} onSaved={(p) => nav(`/erp/projects/${p.id}`)} onClose={() => setEdit(null)} />}</DialogContent></Dialog>
    </div>
  );
}
