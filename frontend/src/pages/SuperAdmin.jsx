import { useCallback, useEffect, useMemo, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Building2, CalendarClock, Download, IndianRupee, Search, ShieldCheck } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { OfflineLicencesAdmin } from "@/components/OfflineLicencesAdmin";
import { api, errMsg } from "@/lib/api";
import { dmy, inr } from "@/lib/format";
import { INDUSTRIES, IND_KEYS, MODES, hasModes } from "@/lib/industry";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Card, Pick, Td, Th, useList } from "@/components/industry/common";

const STATUS = { active: "bg-emerald-100 text-emerald-800", trial: "bg-sky-100 text-sky-800", expired: "bg-red-100 text-red-700", suspended: "bg-slate-800 text-white" };
const Badge = ({ o }) => <span className={`rounded px-2 py-0.5 text-xs font-semibold capitalize ${STATUS[o.status]}`} data-testid={`org-status-${o.id}`}>{o.status === "expired" ? (o.grace ? "Expired · grace" : "Expired · locked") : o.status}</span>;
const csv = (rows, cols, name) => {
  const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const blob = new Blob(["\uFEFF" + [cols.map((c) => esc(c[1])).join(","), ...rows.map((r) => cols.map((c) => esc(r[c[0]])).join(","))].join("\r\n")], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name; a.click();
};

const Overview = () => {
  const [d] = useList("/super/overview");
  if (!d) return <div className="text-slate-500">Loading...</div>;
  const k = [["Total organizations", d.total_orgs, Building2, "kpi-total-orgs"], ["Active paid subscriptions", d.active_paid, ShieldCheck, "kpi-active-paid"],
    ["Expiring in next 7 days", d.expiring_7d, CalendarClock, "kpi-expiring"], ["Revenue (last 12 months)", inr(d.revenue_year), IndianRupee, "kpi-revenue"]];
  return (
    <div className="space-y-6" data-testid="super-overview">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{k.map(([l, v, I, t]) => <Card key={t}><div className="flex items-center justify-between text-xs uppercase text-slate-500">{l}<I className="h-4 w-4" /></div><div className="mt-2 num text-3xl font-bold" data-testid={t}>{v}</div></Card>)}</div>
      <div className="text-sm text-slate-600">Last 30 days revenue <b className="num" data-testid="kpi-revenue-month">{inr(d.revenue_month)}</b> · {d.trials} on trial · {d.expired} expired · {d.suspended} suspended</div>
      <Card><div className="font-semibold mb-3">Industry breakdown</div>
        <table className="w-full text-sm" data-testid="industry-breakdown"><thead><tr className="text-left"><Th>Industry</Th><Th r>Active paid</Th><Th r>Trial</Th><Th r>All</Th></tr></thead>
          <tbody>{d.industries.map((i) => <tr key={i.key} className="border-t" data-testid={`industry-row-${i.key}`}><Td>{i.label}</Td><Td r className="font-semibold">{i.active}</Td><Td r>{i.trial}</Td><Td r>{i.total}</Td></tr>)}</tbody></table></Card>
    </div>
  );
};

const ExtendDialog = ({ org, plans, onClose, onDone }) => {
  const [f, setF] = useState({ period: "year", days: 365, plan: "", amount: "", method: "UPI", reference: "", note: "", lift_suspension: false });
  useEffect(() => { if (org) setF({ period: "year", days: 365, plan: "", amount: "", method: "UPI", reference: "", note: "", lift_suspension: false }); }, [org]);
  const opts = plans.filter((p) => p.industry === org?.industry_type && p.active !== false);
  const plan = f.plan || (opts.find((p) => p.key === org?.plan) || opts.find((p) => p.mode === org?.industry_mode && p.tier === "base") || opts[0])?.key || "";
  const save = async () => {
    try { const { data } = await api.post(`/super/orgs/${org.id}/extend`, { ...f, plan, days: Number(f.days || 0), amount: Number(f.amount || 0) }); toast.success(`Valid till ${dmy(data.new_expiry)}`); onDone(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Dialog open={!!org} onOpenChange={(o) => !o && onClose()}><DialogContent data-testid="extend-dialog">
      <DialogHeader><DialogTitle>Extend / activate · {org?.name}</DialogTitle></DialogHeader>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1 col-span-2"><Label className="text-xs">Period</Label><Pick value={f.period} onChange={(v) => setF({ ...f, period: v })} data-testid="extend-period-select">
          <option value="trial14">+14 days free trial</option><option value="month">+1 month</option><option value="year">+1 year</option><option value="days">Custom days</option></Pick></div>
        {f.period === "days" && <div className="space-y-1"><Label className="text-xs">Days</Label><Input type="number" value={f.days} onChange={(e) => setF({ ...f, days: e.target.value })} data-testid="extend-days-input" /></div>}
        {f.period !== "trial14" && <div className="space-y-1 col-span-2"><Label className="text-xs">Plan</Label><Pick value={plan} onChange={(v) => setF({ ...f, plan: v })} data-testid="extend-plan-select">
          {opts.map((p) => <option key={p.key} value={p.key}>{p.name} · {inr(p.price)}/yr{p.monthly_price ? ` · ${inr(p.monthly_price)}/mo` : ""}</option>)}</Pick></div>}
        <div className="space-y-1"><Label className="text-xs">Amount received (₹)</Label><Input type="number" value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value })} data-testid="extend-amount-input" /></div>
        <div className="space-y-1"><Label className="text-xs">Paid by</Label><Pick value={f.method} onChange={(v) => setF({ ...f, method: v })} data-testid="extend-method-select">{["UPI", "NEFT", "Cheque", "Cash", "Card", "Other", "None"].map((m) => <option key={m} value={m}>{m}</option>)}</Pick></div>
        <div className="space-y-1 col-span-2"><Label className="text-xs">Transaction reference (UTR / cheque no)</Label><Input value={f.reference} onChange={(e) => setF({ ...f, reference: e.target.value })} data-testid="extend-reference-input" /></div>
        {org?.status === "suspended" && <label className="col-span-2 flex items-center gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm" data-testid="extend-lift-suspension-label">
          <input type="checkbox" checked={f.lift_suspension} onChange={(e) => setF({ ...f, lift_suspension: e.target.checked })} data-testid="extend-lift-suspension-checkbox" />
          This organization is suspended. Lift the suspension and reactivate it with this extension (recorded in the audit log).</label>}
      </div>
      <DialogFooter><Button variant="outline" onClick={onClose}>Cancel</Button><Button onClick={save} data-testid="extend-save-button">Save & record payment</Button></DialogFooter>
    </DialogContent></Dialog>
  );
};

const ConfigDialog = ({ org, plans, onClose, onDone }) => {
  const [f, setF] = useState(null);
  useEffect(() => { setF(org ? { id: org.id, industry_type: org.industry_type, industry_mode: org.industry_mode, plan: org.plan, max_users_override: org.max_users_override || "", erp: "erp" in org.modules ? String(org.modules.erp) : "" } : null); }, [org]);
  if (!org || !f || f.id !== org.id) return null;
  const opts = plans.filter((p) => p.industry === f.industry_type && p.mode === f.industry_mode);
  const save = async () => {
    try { await api.put(`/super/orgs/${org.id}/config`, { industry_type: f.industry_type, industry_mode: hasModes(f.industry_type) ? f.industry_mode : "complete", plan: opts.some((p) => p.key === f.plan) ? f.plan : null,
      max_users_override: f.max_users_override ? Number(f.max_users_override) : null, erp: f.erp === "" ? null : f.erp === "true" }); toast.success("Organization updated"); onDone(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}><DialogContent data-testid="config-dialog">
      <DialogHeader><DialogTitle>Industry, mode & plan · {org.name}</DialogTitle></DialogHeader>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1"><Label className="text-xs">Industry</Label><Pick value={f.industry_type} onChange={(v) => setF({ ...f, industry_type: v, industry_mode: hasModes(v) ? f.industry_mode : "complete" })} data-testid="config-industry-select">{IND_KEYS.map((k) => <option key={k} value={k}>{INDUSTRIES[k].label}</option>)}</Pick></div>
        <div className="space-y-1"><Label className="text-xs">Mode</Label><Pick value={f.industry_mode} onChange={(v) => setF({ ...f, industry_mode: v })} data-testid="config-mode-select">{(hasModes(f.industry_type) ? ["billing", "complete"] : ["complete"]).map((m) => <option key={m} value={m}>{MODES[m]}</option>)}</Pick></div>
        <div className="space-y-1 col-span-2"><Label className="text-xs">Plan tier (keeps the current expiry date)</Label><Pick value={opts.some((p) => p.key === f.plan) ? f.plan : ""} onChange={(v) => setF({ ...f, plan: v })} data-testid="config-plan-select"><option value="">Keep current plan</option>{opts.map((p) => <option key={p.key} value={p.key}>{p.name} · {p.max_users} users</option>)}</Pick></div>
        <div className="space-y-1"><Label className="text-xs">Seat limit override</Label><Input type="number" placeholder="Plan default" value={f.max_users_override} onChange={(e) => setF({ ...f, max_users_override: e.target.value })} data-testid="config-seats-input" /></div>
        <div className="space-y-1"><Label className="text-xs">Projects / ERP module</Label><Pick value={f.erp} onChange={(v) => setF({ ...f, erp: v })} data-testid="config-erp-select"><option value="">As per plan</option><option value="true">Always on</option><option value="false">Off</option></Pick></div>
      </div>
      <DialogFooter><Button variant="outline" onClick={onClose}>Cancel</Button><Button onClick={save} data-testid="config-save-button">Save</Button></DialogFooter>
    </DialogContent></Dialog>
  );
};

const Orgs = ({ plans }) => {
  const { enterSupport } = useApp();
  const nav = useNavigate();
  const [flt, setFlt] = useState({ q: "", industry: "", status: "" });
  const [rows, setRows] = useState(null);
  const [ext, setExt] = useState(null);
  const [cfg, setCfg] = useState(null);
  const load = useCallback(() => api.get("/super/orgs", { params: flt }).then((r) => setRows(r.data)).catch((e) => toast.error(errMsg(e))), [flt]);
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [load]);
  const act = async (o, kind) => {
    try {
      if (kind === "support") {
        const reason = window.prompt(`Reason for opening ${o.name} in support view (logged)`);
        if (!reason) return;
        await enterSupport((await api.post(`/super/orgs/${o.id}/support-view`, { reason })).data); nav("/"); return;
      }
      if (kind === "suspend") { const reason = window.prompt(`Suspend ${o.name}? Reason:`); if (reason === null) return; await api.post(`/super/orgs/${o.id}/suspend`, { reason }); }
      else await api.post(`/super/orgs/${o.id}/reactivate`);
      toast.success("Done"); load();
    } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div className="space-y-4" data-testid="super-orgs">
      <div className="flex flex-wrap gap-2 items-center">
        <div className="relative"><Search className="absolute left-3 top-3 h-4 w-4 text-slate-400" /><Input className="h-10 pl-9 w-72" placeholder="Search name, owner, email, phone" value={flt.q} onChange={(e) => setFlt({ ...flt, q: e.target.value })} data-testid="orgs-search-input" /></div>
        <Pick className="w-56" value={flt.industry} onChange={(v) => setFlt({ ...flt, industry: v })} data-testid="orgs-industry-filter"><option value="">All industries</option>{IND_KEYS.map((k) => <option key={k} value={k}>{INDUSTRIES[k].label}</option>)}</Pick>
        <Pick className="w-44" value={flt.status} onChange={(v) => setFlt({ ...flt, status: v })} data-testid="orgs-status-filter"><option value="">All statuses</option>{["active", "trial", "expired", "grace", "suspended"].map((s) => <option key={s} value={s}>{s}</option>)}</Pick>
        <span className="ml-auto text-sm text-slate-500" data-testid="orgs-count">{rows?.length ?? 0} organizations</span>
      </div>
      <Card className="overflow-x-auto !p-0"><table className="w-full text-sm min-w-[1100px]" data-testid="orgs-table">
        <thead className="bg-slate-50"><tr className="text-left"><th className="p-3">Organization</th><th className="p-3">Owner & contact</th><th className="p-3">Industry</th><th className="p-3">Current plan</th><th className="p-3">Expiry</th><th className="p-3">Status</th><th className="p-3">Users</th><th className="p-3">Actions</th></tr></thead>
        <tbody>{rows && !rows.length && <tr><td colSpan={8} className="p-8 text-center text-slate-500" data-testid="orgs-empty">No organizations match these filters.</td></tr>}{(rows || []).map((o) => <tr key={o.id} className="border-t align-top" data-testid={`org-row-${o.id}`}>
          <td className="p-3 font-semibold">{o.name}</td><td className="p-3">{o.owner_name}<div className="text-xs text-slate-500">{o.owner_email}{o.owner_phone && ` · ${o.owner_phone}`}</div></td>
          <td className="p-3">{o.industry_label}{hasModes(o.industry_type) && <div className="text-xs text-slate-500">{MODES[o.industry_mode]}</div>}</td>
          <td className="p-3">{o.plan_label}</td><td className="p-3 font-mono text-xs">{dmy(o.ends_at)}</td><td className="p-3"><Badge o={o} /></td><td className="p-3">{o.users}/{o.max_users}</td>
          <td className="p-3"><div className="flex flex-wrap gap-1">
            <Button size="sm" onClick={() => setExt(o)} data-testid={`org-extend-${o.id}`}>Extend</Button>
            <Button size="sm" variant="outline" onClick={() => setCfg(o)} data-testid={`org-config-${o.id}`}>Industry / plan</Button>
            {o.status === "suspended" ? <Button size="sm" variant="outline" onClick={() => act(o, "reactivate")} data-testid={`org-reactivate-${o.id}`}>Reactivate</Button>
              : <Button size="sm" variant="outline" className="text-red-600" onClick={() => act(o, "suspend")} data-testid={`org-suspend-${o.id}`}>Suspend</Button>}
            <Button size="sm" variant="ghost" onClick={() => act(o, "support")} data-testid={`org-support-${o.id}`}>Support view</Button></div></td></tr>)}</tbody></table></Card>
      <ExtendDialog org={ext} plans={plans} onClose={() => setExt(null)} onDone={() => { setExt(null); load(); }} />
      <ConfigDialog org={cfg} plans={plans} onClose={() => setCfg(null)} onDone={() => { setCfg(null); load(); }} />
    </div>
  );
};

const PlanRow = ({ p, onDone }) => {
  const [f, setF] = useState({ name: p.name, price: p.price, monthly_price: p.monthly_price || 0, max_users: p.max_users, active: p.active !== false });
  const save = async () => { try { await api.put(`/super/plans/${p.key}`, { ...f, price: Number(f.price), monthly_price: Number(f.monthly_price || 0), max_users: Number(f.max_users), modules: p.modules || [] }); toast.success(`${f.name} saved`); onDone(); } catch (e) { toast.error(errMsg(e)); } };
  return (
    <tr className="border-t" data-testid={`plan-row-${p.key}`}>
      <Td><Input className="h-9" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} data-testid={`plan-name-${p.key}`} /><div className="text-xs text-slate-500 mt-1 font-mono">{p.key}</div></Td>
      <Td>{INDUSTRIES[p.industry]?.short} · {p.mode === "billing" ? "Billing" : "Complete"}</Td>
      <Td><Input className="h-9 w-28 num" type="number" value={f.price} onChange={(e) => setF({ ...f, price: e.target.value })} data-testid={`plan-price-${p.key}`} /></Td>
      <Td><Input className="h-9 w-24 num" type="number" value={f.monthly_price} onChange={(e) => setF({ ...f, monthly_price: e.target.value })} data-testid={`plan-monthly-${p.key}`} /></Td>
      <Td><Input className="h-9 w-20 num" type="number" value={f.max_users} onChange={(e) => setF({ ...f, max_users: e.target.value })} data-testid={`plan-users-${p.key}`} /></Td>
      <Td><input type="checkbox" checked={f.active} onChange={(e) => setF({ ...f, active: e.target.checked })} data-testid={`plan-active-${p.key}`} /></Td>
      <Td r><Button size="sm" onClick={save} data-testid={`plan-save-${p.key}`}>Save</Button></Td>
    </tr>
  );
};

const Plans = ({ plans, reload }) => {
  const [n, setN] = useState({ key: "", name: "", industry: "retail", mode: "complete", price: "", monthly_price: "", max_users: 5 });
  const add = async () => { try { await api.post("/super/plans", { ...n, price: Number(n.price), monthly_price: Number(n.monthly_price || 0), max_users: Number(n.max_users) }); toast.success("Plan created"); setN({ ...n, key: "", name: "", price: "" }); reload(); } catch (e) { toast.error(errMsg(e)); } };
  return (
    <div className="space-y-4" data-testid="super-plans">
      <p className="text-sm text-slate-500">Annual price excludes 18% GST. Changes apply to new purchases and renewals immediately; current expiry dates are not changed.</p>
      <Card className="overflow-x-auto !p-3"><table className="w-full text-sm min-w-[900px]"><thead><tr className="text-left"><Th>Plan</Th><Th>Industry</Th><Th>Annual ₹</Th><Th>Monthly ₹</Th><Th>Max users</Th><Th>On sale</Th><Th /></tr></thead>
        <tbody>{plans.map((p) => <PlanRow key={`${p.key}-${p.price}-${p.max_users}-${p.name}`} p={p} onDone={reload} />)}</tbody></table></Card>
      <Card className="grid gap-3 md:grid-cols-8 items-end" data-testid="new-plan-form">
        <div className="space-y-1"><Label className="text-xs">Key</Label><Input className="h-10" placeholder="college_erp_pro" value={n.key} onChange={(e) => setN({ ...n, key: e.target.value.toLowerCase() })} data-testid="new-plan-key" /></div>
        <div className="space-y-1 md:col-span-2"><Label className="text-xs">Name</Label><Input className="h-10" placeholder="College ERP Pro" value={n.name} onChange={(e) => setN({ ...n, name: e.target.value })} data-testid="new-plan-name" /></div>
        <div className="space-y-1"><Label className="text-xs">Industry</Label><Pick value={n.industry} onChange={(v) => setN({ ...n, industry: v, mode: hasModes(v) ? n.mode : "complete" })} data-testid="new-plan-industry">{IND_KEYS.map((k) => <option key={k} value={k}>{INDUSTRIES[k].short}</option>)}</Pick></div>
        <div className="space-y-1"><Label className="text-xs">Mode</Label><Pick value={n.mode} onChange={(v) => setN({ ...n, mode: v })} data-testid="new-plan-mode">{(hasModes(n.industry) ? ["billing", "complete"] : ["complete"]).map((m) => <option key={m} value={m}>{m === "billing" ? "Billing" : "Complete"}</option>)}</Pick></div>
        <div className="space-y-1"><Label className="text-xs">Annual ₹</Label><Input className="h-10" type="number" value={n.price} onChange={(e) => setN({ ...n, price: e.target.value })} data-testid="new-plan-price" /></div>
        <div className="space-y-1"><Label className="text-xs">Max users</Label><Input className="h-10" type="number" value={n.max_users} onChange={(e) => setN({ ...n, max_users: e.target.value })} data-testid="new-plan-users" /></div>
        <Button onClick={add} disabled={!n.key || !n.name || !(Number(n.price) > 0)} data-testid="new-plan-create">Create plan</Button>
      </Card>
    </div>
  );
};

const Payments = () => {
  const [rows] = useList("/super/payments");
  const [log] = useList("/super/support-log");
  const cols = [["date", "Date"], ["org", "Organization"], ["plan", "Plan"], ["amount", "Amount (₹)"], ["method", "Method"], ["reference", "Reference"], ["days", "Days"], ["source", "Source"], ["by", "Recorded by"]];
  const total = useMemo(() => (rows || []).reduce((a, r) => a + r.amount, 0), [rows]);
  return (
    <div className="space-y-4" data-testid="super-payments">
      <div className="flex items-center gap-3"><div className="text-sm">Total recorded <b className="num" data-testid="payments-total">{inr(total)}</b></div>
        <Button size="sm" variant="outline" className="ml-auto" onClick={() => csv(rows || [], cols, "easybooks-payments.csv")} data-testid="payments-export-csv"><Download className="h-4 w-4 mr-1" />Export CSV (Excel)</Button></div>
      <Card className="overflow-x-auto !p-3"><table className="w-full text-sm" data-testid="payments-table"><thead><tr className="text-left">{cols.map((c) => <Th key={c[0]} r={c[0] === "amount"}>{c[1]}</Th>)}</tr></thead>
        <tbody>{(rows || []).map((r, i) => <tr key={i} className="border-t"><Td>{dmy(r.date)}</Td><Td>{r.org}</Td><Td>{r.plan}</Td><Td r>{r.amount.toLocaleString("en-IN")}</Td><Td>{r.method}</Td><Td className="font-mono text-xs">{r.reference}</Td><Td>{r.days}</Td><Td>{r.source}</Td><Td>{r.by}</Td></tr>)}</tbody></table></Card>
      <Card data-testid="support-log"><div className="font-semibold mb-2">Support view access log</div>
        {(log || []).map((l) => <div key={l.id} className="text-sm border-t py-1.5">{dmy(l.at)} {l.at?.slice(11, 16)} · <b>{l.by}</b> opened <b>{l.org}</b> - {l.reason}</div>)}
        {log && !log.length && <div className="text-sm text-slate-500">No support access yet.</div>}</Card>
    </div>
  );
};

export default function SuperAdmin() {
  const { user } = useApp();
  const [plans, reload] = useList("/super/plans");
  if (!user?.is_superadmin || user?.support_view) return <Navigate to="/" replace />;
  return (
    <div className="space-y-6" data-testid="super-admin-page">
      <div><h1 className="font-heading text-3xl font-extrabold tracking-tight">Super Admin</h1><p className="text-slate-500 mt-1">All organizations, subscriptions, plans and SaaS revenue.</p></div>
      <Tabs defaultValue="overview">
        <TabsList className="h-auto bg-slate-100 p-1">{[["overview", "Overview"], ["orgs", "Organizations"], ["plans", "Subscription plans"], ["payments", "Payments & renewals"], ["licences", "Offline licences"]].map(([v, l]) =>
          <TabsTrigger key={v} value={v} className="px-4 py-2" data-testid={`super-tab-${v}`}>{l}</TabsTrigger>)}</TabsList>
        <TabsContent value="overview" className="mt-5"><Overview /></TabsContent>
        <TabsContent value="orgs" className="mt-5"><Orgs plans={plans || []} /></TabsContent>
        <TabsContent value="plans" className="mt-5"><Plans plans={plans || []} reload={reload} /></TabsContent>
        <TabsContent value="payments" className="mt-5"><Payments /></TabsContent>
        <TabsContent value="licences" className="mt-5"><OfflineLicencesAdmin /></TabsContent>
      </Tabs>
    </div>
  );
}
