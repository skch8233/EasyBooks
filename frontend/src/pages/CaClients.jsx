import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { CheckCircle2, Circle, FileSpreadsheet, Calculator, LogIn, Plus, Trash2, UserPlus } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { STATES } from "@/lib/format";
import { OFFLINE } from "@/lib/offline";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const BT = { company: "Company", llp: "LLP", partnership: "Partnership", proprietorship: "Proprietorship" };
const Tick = ({ ok, testid }) => ok ? <CheckCircle2 className="h-4 w-4 text-emerald-600" data-testid={testid} /> : <Circle className="h-4 w-4 text-slate-300" data-testid={testid} />;
const BLANK = { business_name: "", business_type: "proprietorship", state: "", gstin: "", phone: "" };
const sel = "h-10 w-full rounded-md border px-3 bg-white text-sm";

const AddClient = ({ open, onClose, onDone }) => {
  const [f, setF] = useState(BLANK);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) setF(BLANK); }, [open]);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const save = async () => {
    setBusy(true);
    try { const { data } = await api.post("/ca/clients", f); toast.success(`${data.name} added to your clients`); onDone(); }
    catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent data-testid="ca-add-client-dialog">
        <DialogHeader><DialogTitle>Add a client business</DialogTitle></DialogHeader>
        <div className="grid gap-4">
          <div className="space-y-1.5"><Label>Business name</Label><Input value={f.business_name} onChange={set("business_name")} data-testid="ca-client-name-input" /></div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5"><Label>Type</Label><select className={sel} value={f.business_type} onChange={set("business_type")} data-testid="ca-client-type-select">
              {Object.entries(BT).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>
            <div className="space-y-1.5"><Label>State</Label><select className={sel} value={f.state} onChange={set("state")} data-testid="ca-client-state-select">
              <option value="">Not set</option>{STATES.map((s) => <option key={s} value={s}>{s}</option>)}</select></div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5"><Label>GSTIN (optional)</Label><Input value={f.gstin} onChange={(e) => setF({ ...f, gstin: e.target.value.toUpperCase() })} data-testid="ca-client-gstin-input" /></div>
            <div className="space-y-1.5"><Label>Phone (optional)</Label><Input value={f.phone} onChange={set("phone")} data-testid="ca-client-phone-input" /></div>
          </div>
        </div>
        <DialogFooter><Button variant="outline" onClick={onClose} data-testid="ca-client-cancel">Cancel</Button>
          <Button onClick={save} disabled={busy || !f.business_name.trim()} data-testid="ca-client-save">Add client</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

const ClientRow = ({ b, onOpen }) => (
  <tr className="border-t" data-testid={`ca-client-row-${b.id}`}>
    <td className="py-3 pr-3"><div className="font-semibold">{b.name}{b.home && <span className="ml-2 text-[11px] uppercase text-slate-500">my firm</span>}
      {b.current && <span className="ml-2 rounded bg-emerald-100 px-1.5 py-0.5 text-[11px] font-semibold text-emerald-800" data-testid={`ca-client-current-${b.id}`}>open now</span>}</div>
      <div className="text-xs text-slate-500">{BT[b.business_type]}{b.gstin && ` · ${b.gstin}`} · {b.role}</div></td>
    <td className="py-3 pr-3 font-mono text-sm">{b.fy || "-"}</td>
    <td className="py-3 pr-3 text-right font-mono text-sm" data-testid={`ca-client-vouchers-${b.id}`}>{b.vouchers}</td>
    <td className="py-3 pr-3 font-mono text-sm">{b.last_entry || "-"}</td>
    <td className="py-3 pr-3"><Tick ok={b.depreciation_posted} testid={`ca-client-dep-${b.id}`} /></td>
    <td className="py-3 pr-3"><Tick ok={b.tax_posted} testid={`ca-client-tax-${b.id}`} /></td>
    <td className="py-3 pr-3 text-xs capitalize">{b.plan_status}</td>
    <td className="py-3 text-right whitespace-nowrap space-x-1">
      <Button size="sm" variant="outline" onClick={() => onOpen(b, "/")} data-testid={`ca-open-${b.id}`}><LogIn className="h-3.5 w-3.5 mr-1" />Open</Button>
      <Button size="sm" variant="outline" onClick={() => onOpen(b, "/year-end")} data-testid={`ca-yearend-${b.id}`}><Calculator className="h-3.5 w-3.5 mr-1" />Dep & Tax</Button>
      <Button size="sm" onClick={() => onOpen(b, "/final-accounts")} data-testid={`ca-final-${b.id}`}><FileSpreadsheet className="h-3.5 w-3.5 mr-1" />Final accounts</Button>
    </td>
  </tr>
);

const AccessCard = () => {
  const { settings } = useApp();
  const [list, setList] = useState([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("accountant");
  const load = useCallback(() => api.get("/ca/access").then((r) => setList(r.data)).catch(() => {}), []);
  useEffect(() => { load(); }, [load]);
  const grant = async () => {
    try { const { data } = await api.post("/ca/access", { email, role }); toast.success(`${data.name} can now open ${settings?.company_name}`); setEmail(""); load(); }
    catch (e) { toast.error(errMsg(e)); }
  };
  const revoke = async (m) => {
    try { await api.delete(`/ca/access/${m.user_id}`); toast.success(`Access removed for ${m.name}`); load(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div className="rounded-xl border bg-white p-5 space-y-4" data-testid="ca-access-card">
      <div><h2 className="font-heading text-lg font-bold">Give your CA access to {settings?.company_name}</h2>
        <p className="text-sm text-slate-500">Your CA signs up once with their own email. Add that email here and this business appears in their client list. People added here are listed below, not under Settings &gt; Users.</p></div>
      <div className="flex flex-wrap gap-2">
        <Input className="h-10 max-w-xs" placeholder="ca@firm.in" value={email} onChange={(e) => setEmail(e.target.value)} data-testid="ca-access-email-input" />
        <select className="h-10 rounded-md border px-3 bg-white text-sm" value={role} onChange={(e) => setRole(e.target.value)} data-testid="ca-access-role-select">
          <option value="accountant">Accountant (can post entries)</option><option value="admin">Admin</option><option value="viewer">Viewer (read only)</option></select>
        <Button onClick={grant} disabled={!email.trim()} data-testid="ca-access-grant-button"><UserPlus className="h-4 w-4 mr-1" />Give access</Button>
      </div>
      {list.length > 0 && <ul className="divide-y text-sm" data-testid="ca-access-list">
        {list.map((m) => <li key={m.user_id} className="flex items-center gap-3 py-2" data-testid={`ca-access-row-${m.email}`}>
          <span className="font-medium">{m.name}</span><span className="text-slate-500">{m.email}</span><span className="text-xs uppercase text-emerald-700">{m.role}</span>
          <Button size="sm" variant="ghost" className="ml-auto text-red-600" onClick={() => revoke(m)} data-testid={`ca-access-revoke-${m.email}`}><Trash2 className="h-4 w-4" /></Button></li>)}
      </ul>}
    </div>
  );
};

export default function CaClients() {
  const { switchBusiness, isAdmin, user } = useApp();
  const [list, setList] = useState(null);
  const [add, setAdd] = useState(false);
  const nav = useNavigate();
  const load = useCallback(() => api.get("/ca/businesses").then((r) => setList(r.data)).catch((e) => { toast.error(errMsg(e)); setList([]); }), []);
  useEffect(() => { load(); }, [load, user?.business_id]);
  const open = async (b, to) => {
    try { if (!b.current) await switchBusiness(b.id); nav(to); } catch (e) { toast.error(errMsg(e)); }
  };
  const done = (k) => (list || []).filter((b) => b[k]).length;
  return (
    <div className="space-y-6" data-testid="ca-clients-page">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><h1 className="font-heading text-3xl font-extrabold tracking-tight">CA Clients</h1>
          <p className="text-slate-500 mt-1">One login for every client. Open a business to post entries, depreciation and tax, then prepare its final accounts.</p></div>
        {(user?.home_role || user?.role) !== "viewer" && <Button onClick={() => setAdd(true)} data-testid="ca-add-client-button"><Plus className="h-4 w-4 mr-1" />Add client business</Button>}
      </div>
      {list && <div className="grid grid-cols-3 gap-3 max-w-xl" data-testid="ca-summary">
        {[["Businesses", list.length, "ca-count"], ["Depreciation posted", done("depreciation_posted"), "ca-dep-count"], ["Tax posted", done("tax_posted"), "ca-tax-count"]].map(([l, v, t]) =>
          <div key={t} className="rounded-lg border bg-white px-4 py-3"><div className="text-xs uppercase text-slate-500">{l}</div><div className="font-mono text-2xl font-bold" data-testid={t}>{v}</div></div>)}
      </div>}
      <div className="rounded-xl border bg-white p-5 overflow-x-auto">
        {!list ? <div className="text-slate-500">Loading...</div> : (
          <table className="w-full text-left" data-testid="ca-clients-table">
            <thead className="text-xs uppercase text-slate-500"><tr><th className="pb-2 pr-3">Business</th><th className="pb-2 pr-3">Year</th><th className="pb-2 pr-3 text-right">Entries</th>
              <th className="pb-2 pr-3">Last entry</th><th className="pb-2 pr-3">Dep.</th><th className="pb-2 pr-3">Tax</th><th className="pb-2 pr-3">Plan</th><th /></tr></thead>
            <tbody>{list.map((b) => <ClientRow key={b.id} b={b} onOpen={open} />)}</tbody>
          </table>)}
        {list && list.length < 2 && <p className="mt-4 text-sm text-slate-500" data-testid="ca-empty-hint">No client businesses yet. {OFFLINE ? "Add one here. Each client gets its own separate books on this PC." : "Add one here, or ask a client to give your email access from their own CA Clients page."}</p>}
      </div>
      {isAdmin && !OFFLINE && <AccessCard />}
      <AddClient open={add} onClose={() => setAdd(false)} onDone={() => { setAdd(false); load(); window.dispatchEvent(new Event("eb-businesses")); }} />
    </div>
  );
}
