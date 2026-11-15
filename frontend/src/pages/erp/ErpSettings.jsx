import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/api";
import { TEMPLATES, loadSignature } from "@/lib/erp";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useErp } from "@/pages/erp/ErpShell";

const ROLE_LABEL = { admin: "Administrator", accountant: "Accountant", project_manager: "Project Manager", data_entry: "Data Entry", viewer: "Viewer" };

export default function ErpSettings() {
  const { reload } = useErp();
  const [s, setS] = useState(null);
  const [sig, setSig] = useState(null);
  const file = useRef();
  const loadS = () => api.get("/erp/settings").then((r) => { setS(r.data); loadSignature(r.data).then(setSig); });
  useEffect(() => { loadS(); }, []);
  const upload = async (fl) => {
    const fd = new FormData(); fd.append("file", fl);
    try { await api.post("/erp/settings/signature", fd); toast.success("Signature uploaded"); loadS(); } catch (e) { toast.error(errMsg(e)); }
  };
  const removeSig = async () => { await api.delete("/erp/settings/signature"); setSig(null); loadS(); };
  if (!s) return <div className="text-slate-500">Loading...</div>;
  const toggle = (a, r) => { const cur = s.permissions[a] || []; setS({ ...s, permissions: { ...s.permissions, [a]: cur.includes(r) ? cur.filter((x) => x !== r) : [...cur, r] } }); };
  const save = async () => {
    try { const { industries, roles, actions, ...body } = s; const { data } = await api.put("/erp/settings", body); setS({ ...s, ...data }); reload(); toast.success("ERP settings saved"); } catch (e) { toast.error(errMsg(e)); }
  };
  const sel = (k, opts) => <select className="h-10 w-full rounded-md border px-2 bg-white" value={s[k]} onChange={(e) => setS({ ...s, [k]: e.target.value })} data-testid={`erp-${k}-select`}>{opts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>;
  return (
    <div className="space-y-6 max-w-4xl" data-testid="erp-settings-page">
      <div className="rounded-xl border bg-white p-5 grid gap-4 sm:grid-cols-2">
        <div className="space-y-1"><Label>Industry</Label>{sel("industry", [["", "Select industry"], ...s.industries.map((i) => [i, i])])}</div>
        <div className="space-y-1"><Label>Authorised signatory (name / designation)</Label><Input className="h-10" value={s.authorized_signatory} onChange={(e) => setS({ ...s, authorized_signatory: e.target.value })} data-testid="erp-signatory-input" /></div>
        <div className="space-y-1"><Label>Quotation prefix</Label><Input className="h-10 font-mono" value={s.quotation_prefix} onChange={(e) => setS({ ...s, quotation_prefix: e.target.value.toUpperCase() })} data-testid="erp-quote-prefix-input" /></div>
        <div className="space-y-1"><Label>Invoice prefix</Label><Input className="h-10 font-mono" value={s.invoice_prefix} onChange={(e) => setS({ ...s, invoice_prefix: e.target.value.toUpperCase() })} data-testid="erp-invoice-prefix-input" /></div>
        <div className="space-y-1"><Label>Default quotation format</Label>{sel("default_quote_template", TEMPLATES)}</div>
        <div className="space-y-1"><Label>Default invoice format</Label>{sel("default_invoice_template", TEMPLATES)}</div>
        <div className="sm:col-span-2 space-y-1"><Label>Default quotation terms</Label><textarea rows={3} className="w-full rounded-md border p-2 text-sm" value={s.quote_terms} onChange={(e) => setS({ ...s, quote_terms: e.target.value })} data-testid="erp-quote-terms-input" /></div>
        <div className="sm:col-span-2 space-y-2" data-testid="erp-signature-block"><Label>Authorised signature image (printed on invoices, quotations and POs)</Label>
          <div className="flex items-center gap-3">
            {sig ? <img src={sig} alt="signature" className="h-14 max-w-[200px] object-contain border rounded bg-white p-1" data-testid="erp-signature-preview" /> : <span className="text-sm text-slate-500">No signature uploaded</span>}
            <input ref={file} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(e) => e.target.files[0] && upload(e.target.files[0])} data-testid="erp-signature-file" />
            <Button type="button" variant="outline" onClick={() => file.current.click()} data-testid="erp-signature-upload">Upload signature</Button>
            {sig && <Button type="button" variant="outline" className="text-red-600" onClick={removeSig} data-testid="erp-signature-remove">Remove</Button>}
          </div></div>
        <div className="sm:col-span-2 rounded-lg bg-slate-50 border p-3 text-sm text-slate-600" data-testid="erp-company-links">
          Company name, logo, address, GSTIN, PAN, bank details, GST rates and invoice terms: <Link className="text-primary underline" to="/settings" data-testid="erp-link-company">Settings → Company</Link>.
          Financial year (April–March): <Link className="text-primary underline" to="/settings?tab=fy" data-testid="erp-link-fy">Settings → Financial Years</Link>.
          Users and roles: <Link className="text-primary underline" to="/settings?tab=users" data-testid="erp-link-users">Settings → Users</Link>. Backup and restore (includes all ERP data): <Link className="text-primary underline" to="/settings?tab=backup" data-testid="erp-link-backup">Settings → Backup</Link>.
        </div>
      </div>
      <div className="rounded-xl border bg-white overflow-x-auto">
        <div className="px-5 py-3 font-semibold">Role permissions (Super Admin always has full access)</div>
        <table className="w-full eb-table min-w-[720px]" data-testid="erp-permissions-table">
          <thead><tr><th>Action</th>{s.roles.map((r) => <th key={r} className="text-center">{ROLE_LABEL[r]}</th>)}</tr></thead>
          <tbody>{s.actions.map((a) => <tr key={a}><td className="capitalize">{a.replace(/_/g, " ")}</td>
            {s.roles.map((r) => <td key={r} className="text-center"><input type="checkbox" className="h-4 w-4" checked={(s.permissions[a] || []).includes(r)} disabled={a === "settings" && r === "admin"}
              onChange={() => toggle(a, r)} data-testid={`perm-${a}-${r}`} /></td>)}</tr>)}</tbody>
        </table>
      </div>
      <Button onClick={save} data-testid="erp-settings-save">Save ERP settings</Button>
    </div>
  );
}
