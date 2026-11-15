import { useCallback, useEffect, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Plus, Search, Trash2 } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { amt, dmy, todayIso } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ReasonDialog } from "@/components/erp/InvoiceSide";
import { useErp, Badge } from "@/pages/erp/ErpShell";

export const SUBTABS = [["prs", "Requisitions"], ["rfqs", "RFQ & Comparison"], ["pos", "Purchase Orders"], ["grns", "Goods Receipts"], ["bills", "Purchase Bills"]];
export const SubNav = () => (
  <div className="flex flex-wrap gap-2" data-testid="purchase-subnav">
    {SUBTABS.map(([k, l]) => <NavLink key={k} to={`/erp/purchases/${k}`} data-testid={`purchase-tab-${k}`}
      className={({ isActive }) => `rounded-full border px-4 py-1.5 text-sm font-medium ${isActive ? "bg-slate-900 text-white" : "bg-white"}`}>{l}</NavLink>)}
  </div>
);

export const useProjects = () => {
  const [p, setP] = useState([]);
  useEffect(() => { api.get("/erp/projects").then((r) => setP(r.data)); }, []);
  return p;
};
export const useVendors = () => {
  const [v, setV] = useState([]);
  useEffect(() => { api.get("/erp/parties", { params: { kind: "vendor" } }).then((r) => setV(r.data)); }, []);
  return v;
};
export const Sel = ({ value, onChange, opts, placeholder, testid, disabled }) => (
  <select className="h-10 w-full rounded-md border px-2 bg-white" value={value} onChange={(e) => onChange(e.target.value)} data-testid={testid} disabled={disabled}>
    {placeholder !== undefined && <option value="">{placeholder}</option>}{opts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
  </select>
);

export const ReqLines = ({ lines, setLines, prefix = "req" }) => (
  <div className="space-y-2">
    {lines.map((l, i) => <div key={i} className="flex gap-2 items-end">
      {[["description", "Item / service", "flex-1"], ["unit", "Unit", "w-20"], ["qty", "Qty", "w-24"], ["notes", "Notes", "w-40"]].map(([k, lb, w]) =>
        <label key={k} className={w}><span className="block text-[10px] font-semibold uppercase text-slate-500">{lb}</span>
          <Input className="h-10" type={k === "qty" ? "number" : "text"} step="any" value={l[k]} onChange={(e) => setLines(lines.map((x, n) => (n === i ? { ...x, [k]: e.target.value } : x)))} data-testid={`${prefix}-${i}-${k}`} /></label>)}
      <button type="button" disabled={lines.length === 1} onClick={() => setLines(lines.filter((_, n) => n !== i))} className="p-2 text-slate-400 hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
    </div>)}
    <Button type="button" size="sm" variant="outline" onClick={() => setLines([...lines, { description: "", unit: "", qty: 1, notes: "" }])} data-testid={`${prefix}-add`}><Plus className="h-4 w-4 mr-1" /> Add item</Button>
  </div>
);
export const cleanReq = (ls) => ls.map((l) => ({ description: l.description.trim(), unit: l.unit || "", qty: Number(l.qty || 0), notes: l.notes || "" }));

export const Register = ({ path, cols, row, statuses, newBtn, extraParams, testid }) => {
  const [rows, setRows] = useState([]);
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const load = useCallback(() => api.get(`/erp/${path}`, { params: { status: status || undefined, q: q || undefined, ...(extraParams || {}) } }).then((r) => setRows(r.data)), [path, status, q, extraParams]);
  useEffect(() => { load(); }, [load]);
  return (
    <div className="space-y-3" data-testid={testid}>
      <div className="flex flex-wrap gap-2 items-center">
        {statuses && ["", ...statuses].map((s) => <button key={s || "all"} onClick={() => setStatus(s)} className={`rounded-full border px-3 py-1 text-xs capitalize ${status === s ? "bg-emerald-700 text-white" : "bg-white"}`} data-testid={`${testid}-filter-${s || "all"}`}>{s || "All"}</button>)}
        <div className="relative ml-auto"><Search className="h-4 w-4 absolute left-3 top-3 text-slate-400" /><Input className="h-10 pl-9 w-56" placeholder="Search" value={q} onChange={(e) => setQ(e.target.value)} data-testid={`${testid}-search`} /></div>
        {newBtn}
      </div>
      <div className="rounded-xl border bg-white overflow-x-auto">
        <table className="w-full eb-table min-w-[860px]"><thead><tr>{cols.map((c) => <th key={c}>{c}</th>)}</tr></thead>
          <tbody>{rows.length === 0 && <tr><td colSpan={cols.length} className="text-center py-8 text-slate-500">Nothing here yet.</td></tr>}{rows.map((r) => row(r, load))}</tbody></table>
      </div>
    </div>
  );
};

const PRForm = ({ init, onClose, onSaved }) => {
  const projects = useProjects();
  const [f, setF] = useState(init);
  const save = async () => {
    const body = { project_id: f.project_id, date: f.date, required_by: f.required_by, remarks: f.remarks, items: cleanReq(f.items) };
    try { await (f.id ? api.put(`/erp/prs/${f.id}`, body) : api.post("/erp/prs", body)); toast.success("Requisition saved"); onSaved(); onClose(); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div className="grid gap-3 sm:grid-cols-3" data-testid="pr-form">
      <div className="space-y-1"><Label>Project *</Label><Sel value={f.project_id} onChange={(v) => setF({ ...f, project_id: v })} placeholder="Select project" opts={projects.map((p) => [p.id, `${p.code} · ${p.name}`])} testid="pr-project-select" /></div>
      <div className="space-y-1"><Label>Date</Label><Input type="date" value={f.date} onChange={(e) => setF({ ...f, date: e.target.value })} data-testid="pr-date-input" /></div>
      <div className="space-y-1"><Label>Required by</Label><Input type="date" value={f.required_by} onChange={(e) => setF({ ...f, required_by: e.target.value })} data-testid="pr-required-input" /></div>
      <div className="sm:col-span-3"><ReqLines lines={f.items} setLines={(items) => setF({ ...f, items })} prefix="pr-line" /></div>
      <div className="sm:col-span-3 space-y-1"><Label>Remarks</Label><Input value={f.remarks} onChange={(e) => setF({ ...f, remarks: e.target.value })} data-testid="pr-remarks-input" /></div>
      <div className="sm:col-span-3 flex justify-end gap-2"><Button variant="outline" onClick={onClose}>Close</Button><Button onClick={save} data-testid="pr-save-button">Save</Button></div>
    </div>
  );
};

export const PRList = () => {
  const { perm } = useErp();
  const nav = useNavigate();
  const [edit, setEdit] = useState(null);
  const [cancel, setCancel] = useState(null);
  const [key, setKey] = useState(0);
  const act = async (r, action, reload) => {
    const note = action === "reject" ? window.prompt("Reason for rejecting?") : "";
    if (note === null) return;
    try { await api.post(`/erp/prs/${r.id}/action`, { action, note }); toast.success({ submit: "Requisition submitted", approve: "Requisition approved", reject: "Requisition rejected" }[action]); reload(); } catch (e) { toast.error(errMsg(e)); }
  };
  const B = (r, l, fn, id, show = true) => show && <Button key={id} size="sm" variant="outline" onClick={fn} data-testid={`pr-${id}-${r.number}`}>{l}</Button>;
  return (
    <>
      <Register key={key} path="prs" testid="pr-register" statuses={["draft", "submitted", "approved", "rejected", "rfq", "closed", "cancelled"]}
        cols={["Number", "Date", "Project", "Items", "Required by", "Status", ""]}
        newBtn={perm("create") && <Button onClick={() => setEdit({ project_id: "", date: todayIso(), required_by: "", remarks: "", items: [{ description: "", unit: "", qty: 1, notes: "" }] })} data-testid="pr-new-button"><Plus className="h-4 w-4 mr-1" /> New requisition</Button>}
        row={(r, reload) => <tr key={r.id} data-testid={`pr-row-${r.number}`}><td className="font-mono font-semibold">{r.number}</td><td>{dmy(r.date)}</td><td>{r.project_code} {r.project_name}</td>
          <td className="text-xs">{r.items.map((i) => `${i.description} × ${i.qty} ${i.unit}`).join(", ")}</td><td>{dmy(r.required_by)}</td><td><Badge s={r.status} /></td>
          <td className="whitespace-nowrap space-x-1">
            {B(r, "Edit", () => setEdit({ ...r, required_by: r.required_by || "" }), "edit", ["draft", "rejected"].includes(r.status) && perm("edit"))}
            {B(r, "Submit", () => act(r, "submit", reload), "submit", r.status === "draft" && perm("edit"))}
            {B(r, "Approve", () => act(r, "approve", reload), "approve", r.status === "submitted" && perm("approve"))}
            {B(r, "Reject", () => act(r, "reject", reload), "reject", r.status === "submitted" && perm("approve"))}
            {B(r, "Create RFQ", () => nav(`/erp/purchases/rfqs/new?pr=${r.id}`), "rfq", ["approved", "rfq"].includes(r.status) && perm("create"))}
            {B(r, "Cancel", () => setCancel(r), "cancel", !["cancelled", "closed"].includes(r.status) && perm("cancel"))}
            {B(r, "Delete", async () => { if (window.confirm("Delete draft?")) { try { await api.delete(`/erp/prs/${r.id}`); toast.success("Draft deleted"); reload(); } catch (e) { toast.error(errMsg(e)); } } }, "delete", r.status === "draft" && perm("delete"))}
          </td></tr>} />
      <Dialog open={!!edit} onOpenChange={(o) => !o && setEdit(null)}><DialogContent className="max-w-3xl"><DialogHeader><DialogTitle>{edit?.id ? `Edit ${edit.number}` : "New purchase requisition"}</DialogTitle></DialogHeader>
        {edit && <PRForm init={edit} onClose={() => setEdit(null)} onSaved={() => setKey(key + 1)} />}</DialogContent></Dialog>
      <ReasonDialog open={!!cancel} onClose={() => setCancel(null)} title={`Cancel ${cancel?.number}`} note="The requisition stays on record as cancelled."
        onOk={async (reason) => { try { await api.post(`/erp/prs/${cancel.id}/cancel`, { reason }); setCancel(null); setKey(key + 1); } catch (e) { toast.error(errMsg(e)); } }} />
    </>
  );
};

export const RFQList = () => {
  const { perm } = useErp();
  const nav = useNavigate();
  return <Register path="rfqs" testid="rfq-register" statuses={["open", "selected", "ordered", "cancelled"]} cols={["Number", "Date", "Project", "Vendors", "Selected vendor", "PO", "Status"]}
    newBtn={perm("create") && <Link to="/erp/purchases/rfqs/new"><Button data-testid="rfq-new-button"><Plus className="h-4 w-4 mr-1" /> New RFQ</Button></Link>}
    row={(r) => <tr key={r.id} className="cursor-pointer hover:bg-slate-50" onClick={() => nav(`/erp/purchases/rfqs/${r.id}`)} data-testid={`rfq-row-${r.number}`}><td className="font-mono font-semibold text-primary">{r.number}</td><td>{dmy(r.date)}</td>
      <td>{r.project_code} {r.project_name}</td><td className="text-xs">{r.vendors.map((v) => v.company_name).join(", ")}</td><td>{r.selected_vendor_name}</td><td className="font-mono">{r.po_number}</td><td><Badge s={r.status} /></td></tr>} />;
};

export const POList = () => {
  const { perm } = useErp();
  const nav = useNavigate();
  return <Register path="pos" testid="po-register" statuses={["draft", "approved", "closed", "cancelled"]} cols={["Number", "Date", "Project", "Vendor", "Total", "Received", "Status"]}
    newBtn={perm("create") && <Link to="/erp/purchases/pos/new"><Button data-testid="po-new-button"><Plus className="h-4 w-4 mr-1" /> New PO</Button></Link>}
    row={(r) => <tr key={r.id} className="cursor-pointer hover:bg-slate-50" onClick={() => nav(`/erp/purchases/pos/${r.id}`)} data-testid={`po-row-${r.number}`}><td className="font-mono font-semibold text-primary">{r.number}</td><td>{dmy(r.date)}</td>
      <td>{r.project_code} {r.project_name}</td><td>{r.vendor_name}</td><td className="font-mono text-right">{amt(r.totals.total)}</td><td><Badge s={r.receipt_status} /></td><td><Badge s={r.status} /></td></tr>} />;
};

export const GRNList = () => {
  const { perm } = useErp();
  const [cancel, setCancel] = useState(null);
  const [key, setKey] = useState(0);
  return (
    <>
      <Register key={key} path="grns" testid="grn-register" cols={["Number", "Date", "PO", "Project", "Vendor", "Received / accepted / rejected", "Value", "Status", ""]}
        row={(r) => <tr key={r.id} data-testid={`grn-row-${r.number}`}><td className="font-mono font-semibold">{r.number}</td><td>{dmy(r.date)}</td><td className="font-mono">{r.po_number}</td><td>{r.project_code}</td><td>{r.vendor_name}</td>
          <td className="text-xs">{r.lines.map((l) => `${l.description}: ${l.received}/${l.accepted}/${l.rejected}`).join("; ")}</td><td className="font-mono text-right">{amt(r.accepted_value)}</td><td><Badge s={r.status} /></td>
          <td>{r.status === "posted" && perm("cancel") && <Button size="sm" variant="outline" onClick={() => setCancel(r)} data-testid={`grn-cancel-${r.number}`}>Cancel</Button>}</td></tr>} />
      <ReasonDialog open={!!cancel} onClose={() => setCancel(null)} title={`Cancel ${cancel?.number}`} note="Received quantities go back to pending on the PO."
        onOk={async (reason) => { try { await api.post(`/erp/grns/${cancel.id}/cancel`, { reason }); setCancel(null); setKey(key + 1); } catch (e) { toast.error(errMsg(e)); } }} />
    </>
  );
};

export const BillList = () => {
  const { perm } = useErp();
  const nav = useNavigate();
  return <Register path="bills" testid="bill-register" statuses={["draft", "posted", "cancelled"]} cols={["Number", "Vendor invoice", "Date", "Project", "Vendor", "PO", "Total", "Balance", "Status"]}
    newBtn={perm("create") && <Link to="/erp/purchases/bills/new"><Button data-testid="bill-new-button"><Plus className="h-4 w-4 mr-1" /> New bill</Button></Link>}
    row={(r) => <tr key={r.id} className="cursor-pointer hover:bg-slate-50" onClick={() => nav(`/erp/purchases/bills/${r.id}`)} data-testid={`bill-row-${r.number}`}><td className="font-mono font-semibold text-primary">{r.number}</td><td className="font-mono">{r.vendor_invoice_no}</td>
      <td>{dmy(r.vendor_invoice_date)}</td><td>{r.project_code}</td><td>{r.vendor_name}</td><td className="font-mono">{r.po_number}</td><td className="font-mono text-right">{amt(r.totals.total)}</td>
      <td className="font-mono text-right">{r.status === "posted" ? amt(r.balance) : "-"}</td><td className="space-x-1"><Badge s={r.status} />{r.pay_status && <Badge s={r.pay_status} />}{r.overdue && <Badge s="overdue" />}</td></tr>} />;
};

export default function Purchases({ tab }) {
  const C = { prs: PRList, rfqs: RFQList, pos: POList, grns: GRNList, bills: BillList }[tab] || PRList;
  return <div className="space-y-4" data-testid="erp-purchases-page"><SubNav /><C /></div>;
}
