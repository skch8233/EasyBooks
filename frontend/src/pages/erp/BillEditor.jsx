import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/api";
import { amt, dmy, todayIso } from "@/lib/format";
import { BLANK_LINE, computeLines, guessGst } from "@/lib/erp";
import { useApp } from "@/context/AppContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { LineItems, cleanLines } from "@/components/erp/LineItems";
import { ReasonDialog } from "@/components/erp/InvoiceSide";
import { useErp, Badge } from "@/pages/erp/ErpShell";
import { Sel, SubNav, useProjects, useVendors } from "@/pages/erp/Purchases";

export const PayOut = ({ title, balance, onSave, onClose }) => {
  const [banks, setBanks] = useState([]);
  const [f, setF] = useState({ date: todayIso(), amount: balance, ledger_id: "", reference: "" });
  const [saving, setSaving] = useState(false);
  useEffect(() => { api.get("/ledgers").then((r) => { const b = r.data.filter((l) => ["cash", "bank"].includes(l.group)); setBanks(b); setF((x) => ({ ...x, ledger_id: b[0]?.id || "" })); }); }, []);
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}><DialogContent><DialogHeader><DialogTitle>{title}</DialogTitle></DialogHeader>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1"><Label>Date</Label><Input type="date" value={f.date} onChange={(e) => setF({ ...f, date: e.target.value })} data-testid="payout-date-input" /></div>
        <div className="space-y-1"><Label>Amount (₹)</Label><Input type="number" step="any" value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value })} data-testid="payout-amount-input" /></div>
        <div className="space-y-1"><Label>Paid from</Label><Sel value={f.ledger_id} onChange={(v) => setF({ ...f, ledger_id: v })} opts={banks.map((b) => [b.id, b.name])} testid="payout-ledger-select" /></div>
        <div className="space-y-1"><Label>Reference</Label><Input value={f.reference} onChange={(e) => setF({ ...f, reference: e.target.value })} data-testid="payout-reference-input" /></div>
      </div>
      <div className="flex justify-end"><Button disabled={saving} onClick={async () => { setSaving(true); await onSave({ ...f, amount: Number(f.amount) }); setSaving(false); }} data-testid="payout-save-button">Save payment</Button></div>
    </DialogContent></Dialog>
  );
};

export default function BillEditor() {
  const { id } = useParams();
  const isNew = id === "new";
  const [sp] = useSearchParams();
  const nav = useNavigate();
  const { settings } = useApp();
  const { perm } = useErp();
  const projects = useProjects();
  const vendors = useVendors();
  const [doc, setDoc] = useState(null);
  const [pos, setPos] = useState([]);
  const [f, setF] = useState(null);
  const [pay, setPay] = useState(false);
  const [cancel, setCancel] = useState(false);
  const [working, setWorking] = useState(false);
  const fromPo = useCallback(async (poId, base) => {
    const { data: po } = await api.get(`/erp/pos/${poId}`);
    const { data: others } = await api.get("/erp/bills", { params: { status: "draft" } });
    const drafted = {};
    others.filter((b) => b.po_id === poId && b.id !== base.id).forEach((b) => b.items.forEach((x) => { if (x.po_line != null) drafted[x.po_line] = (drafted[x.po_line] || 0) + x.qty; }));
    const items = po.items.map((it, i) => ({ ...BLANK_LINE, ...it, qty: Math.max(it.accepted - it.billed_qty - (drafted[i] || 0), 0), po_line: i })).filter((it) => it.qty > 0);
    setF({ ...base, po_id: po.id, vendor_id: po.vendor_id, project_id: po.project_id, gst_type: po.gst_type, grn_ids: po.grns.filter((g) => g.status === "posted").map((g) => g.id),
      items: items.length ? items : [{ ...BLANK_LINE }] });
    if (!items.length) toast.info("Everything received on this PO is already billed (or in a draft bill).");
  }, []);
  const load = useCallback(async () => {
    if (isNew) {
      const base = { vendor_id: "", project_id: "", po_id: "", grn_ids: [], vendor_invoice_no: "", vendor_invoice_date: todayIso(), due_date: "", gst_type: "", items: [{ ...BLANK_LINE }], notes: "" };
      if (sp.get("po")) await fromPo(sp.get("po"), base); else setF(base);
      return;
    }
    const { data } = await api.get(`/erp/bills/${id}`);
    setDoc(data);
    setF({ ...data, po_id: data.po_id || "", gst_type: data.gst_type || "", items: data.items.map((x) => ({ ...BLANK_LINE, ...x })) });
  }, [id, isNew, sp, fromPo]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (f?.vendor_id) api.get("/erp/pos", { params: { q: "" } }).then((r) => setPos(r.data.filter((p) => p.vendor_id === f.vendor_id && ["approved", "closed"].includes(p.status)))); }, [f?.vendor_id]);
  const vendor = vendors.find((v) => v.id === f?.vendor_id);
  const gst = f?.gst_type || guessGst(settings?.state, vendor?.state);
  const calc = useMemo(() => f && computeLines(f.items, gst), [f, gst]);
  if (!f) return <div className="text-slate-500">Loading...</div>;
  const st = doc?.status || "new";
  const editable = st === "new" || st === "draft";
  const run = async (fn, msg) => { if (working) return null; setWorking(true); try { const r = await fn(); toast.success(msg); return r; } catch (e) { toast.error(errMsg(e)); return null; } finally { setWorking(false); } };
  const save = async () => {
    if (!f.vendor_invoice_no.trim()) { toast.error("Vendor invoice number is required"); return; }
    const body = { ...f, po_id: f.po_id || null, gst_type: f.gst_type || null, items: cleanLines(f.items).map((x, i) => ({ ...x, po_line: f.items[i].po_line ?? null })) };
    const r = await run(() => (isNew ? api.post("/erp/bills", body) : api.put(`/erp/bills/${id}`, body)), "Bill saved as draft");
    if (r) { if (isNew) nav(`/erp/purchases/bills/${r.data.id}`, { replace: true }); else load(); }
  };
  const T = calc.totals;
  return (
    <div className="space-y-4 max-w-5xl" data-testid="bill-editor">
      <SubNav />
      <div className="flex flex-wrap items-center gap-2"><h2 className="font-heading text-xl font-bold" data-testid="bill-title">{doc?.number || "New purchase bill"}</h2>
        {doc && <Badge s={doc.status} testid="bill-status" />}{doc?.pay_status && <Badge s={doc.pay_status} testid="bill-pay-status" />}{doc?.overdue && <Badge s="overdue" />}</div>
      {doc?.cancel_reason && <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-800">Cancelled: {doc.cancel_reason}</div>}
      <fieldset disabled={!editable} className="rounded-xl border bg-white p-4 grid gap-3 sm:grid-cols-3">
        <div className="space-y-1"><Label>Vendor *</Label><Sel value={f.vendor_id} onChange={(v) => setF({ ...f, vendor_id: v, po_id: "" })} placeholder="Select vendor" opts={vendors.map((v) => [v.id, v.company_name])} testid="bill-vendor-select" /></div>
        <div className="space-y-1"><Label>Purchase order (optional)</Label><Sel value={f.po_id} onChange={(v) => (v ? fromPo(v, f) : setF({ ...f, po_id: "", grn_ids: [] }))} placeholder="No PO" opts={pos.map((p) => [p.id, `${p.number} · ₹${amt(p.totals.total)}`])} testid="bill-po-select" /></div>
        <div className="space-y-1"><Label>Project *</Label><Sel value={f.project_id} disabled={!!f.po_id} onChange={(v) => setF({ ...f, project_id: v })} placeholder="Select project" opts={projects.map((p) => [p.id, `${p.code} · ${p.name}`])} testid="bill-project-select" /></div>
        <div className="space-y-1"><Label>Vendor invoice no *</Label><Input className="font-mono" value={f.vendor_invoice_no} onChange={(e) => setF({ ...f, vendor_invoice_no: e.target.value })} data-testid="bill-vinv-input" /></div>
        <div className="space-y-1"><Label>Vendor invoice date</Label><Input type="date" value={f.vendor_invoice_date} onChange={(e) => setF({ ...f, vendor_invoice_date: e.target.value })} data-testid="bill-vdate-input" /></div>
        <div className="space-y-1"><Label>Due date</Label><Input type="date" value={f.due_date} onChange={(e) => setF({ ...f, due_date: e.target.value })} data-testid="bill-due-input" /></div>
        <div className="sm:col-span-3"><LineItems prefix="bill-line" lines={f.items} setLines={(items) => setF({ ...f, items })} disabled={!editable} />
          {f.po_id && <p className="text-xs text-slate-500 mt-1">Lines from the PO are limited to the quantity accepted in GRNs and not yet billed.</p>}</div>
        <div className="sm:col-span-2 space-y-1"><Label>Notes</Label><Input value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} data-testid="bill-notes-input" /></div>
        <div className="text-sm text-right font-mono" data-testid="bill-totals">Taxable ₹{amt(T.taxable)}<br />GST ₹{amt(T.cgst + T.sgst + T.igst)} ({gst === "inter" ? "IGST" : "CGST+SGST"})<br /><b>Total ₹{amt(T.total)}</b></div>
      </fieldset>
      <div className={`flex flex-wrap gap-2 ${working ? "pointer-events-none opacity-60" : ""}`}>
        {editable && perm(isNew ? "create" : "edit") && <Button onClick={save} data-testid="bill-save-button">Save draft</Button>}
        {st === "draft" && perm("finalize") && <Button className="bg-emerald-700 hover:bg-emerald-800" onClick={async () => window.confirm("Post this bill to Easy Books as a purchase entry?") && (await run(() => api.post(`/erp/bills/${id}/post`), "Bill posted to accounts")) && load()} data-testid="bill-post-button">Post to accounts</Button>}
        {st === "posted" && doc.balance > 0 && perm("finalize") && <Button onClick={() => setPay(true)} data-testid="bill-pay-button">Record payment</Button>}
        {doc && st !== "cancelled" && perm("cancel") && <Button variant="outline" className="text-red-600" onClick={() => setCancel(true)} data-testid="bill-cancel-button">Cancel</Button>}
        {st === "draft" && perm("delete") && <Button variant="outline" className="text-red-600" onClick={async () => window.confirm("Delete draft?") && (await run(() => api.delete(`/erp/bills/${id}`), "Deleted")) && nav("/erp/purchases/bills")} data-testid="bill-delete-button">Delete</Button>}
      </div>
      {st === "posted" && <div className="rounded-xl border bg-white p-4 text-sm space-y-2" data-testid="bill-payments">
        <div>Posted as <b>{doc.voucher_no}</b> · Paid ₹{amt(doc.paid)} · Balance <b data-testid="bill-balance">₹{amt(doc.balance)}</b> due {dmy(doc.due_date)}</div>
        {doc.payments.map((p) => <div key={p.id} className="border-t pt-1">{dmy(p.date)} · ₹{amt(p.amount)} via {p.mode} {p.reference} · {p.voucher_no}</div>)}
      </div>}
      {pay && <PayOut title={`Pay ${doc.vendor_name} · balance ₹${amt(doc.balance)}`} balance={doc.balance} onClose={() => setPay(false)}
        onSave={async (b) => { if (await run(() => api.post(`/erp/bills/${id}/payments`, b), "Payment posted")) { setPay(false); load(); } }} />}
      <ReasonDialog open={cancel} onClose={() => setCancel(false)} title={`Cancel ${doc?.number}`} note="The purchase entry in Easy Books is cancelled too."
        onOk={async (reason) => { if (await run(() => api.post(`/erp/bills/${id}/cancel`, { reason }), "Cancelled")) { setCancel(false); load(); } }} />
    </div>
  );
}
