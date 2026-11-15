import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Printer } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { amt, dmy, todayIso } from "@/lib/format";
import { BLANK_LINE, TEMPLATES, computeLines, guessGst, loadLogo, loadSignature, printNode } from "@/lib/erp";
import { useApp } from "@/context/AppContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DocTemplate } from "@/components/erp/DocTemplate";
import { LineItems, cleanLines } from "@/components/erp/LineItems";
import { ReasonDialog } from "@/components/erp/InvoiceSide";
import { useErp, Badge } from "@/pages/erp/ErpShell";
import { Sel, SubNav, useProjects, useVendors } from "@/pages/erp/Purchases";

const GRNDialog = ({ po, onClose, onSaved }) => {
  const [f, setF] = useState({ date: todayIso(), challan_no: "", vehicle_no: "", notes: "", lines: po.items.map((it, i) => ({ line: i, received: it.pending > 0 ? it.pending : 0, accepted: it.pending > 0 ? it.pending : 0, rejected: 0 })) });
  const setL = (i, k, v) => setF({ ...f, lines: f.lines.map((l, n) => { if (n !== i) return l; const x = { ...l, [k]: v }; if (k !== "accepted") x.accepted = Math.max(Number(x.received || 0) - Number(x.rejected || 0), 0); return x; }) });
  const [saving, setSaving] = useState(false);
  const save = async () => {
    setSaving(true);
    try {
      await api.post("/erp/grns", { ...f, po_id: po.id, lines: f.lines.filter((l) => Number(l.received) > 0).map((l) => ({ line: l.line, received: Number(l.received), accepted: Number(l.accepted), rejected: Number(l.rejected || 0) })) });
      toast.success("Goods receipt saved"); onSaved(); onClose();
    } catch (e) { toast.error(errMsg(e)); } finally { setSaving(false); }
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}><DialogContent className="max-w-3xl"><DialogHeader><DialogTitle>Goods receipt against {po.number}</DialogTitle></DialogHeader>
      <div className="grid gap-3 sm:grid-cols-3">{[["date", "Date", "date"], ["challan_no", "Delivery challan no", "text"], ["vehicle_no", "Vehicle no", "text"]].map(([k, l, t]) =>
        <div key={k} className="space-y-1"><Label>{l}</Label><Input type={t} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} data-testid={`grn-${k}-input`} /></div>)}</div>
      <table className="w-full eb-table"><thead><tr><th>Item</th><th>Ordered</th><th>Pending</th><th>Received</th><th>Rejected</th><th>Accepted</th></tr></thead>
        <tbody>{po.items.map((it, i) => <tr key={i}><td>{it.description}</td><td>{it.qty} {it.unit}</td><td>{it.pending}</td>
          {["received", "rejected", "accepted"].map((k) => <td key={k}><Input type="number" step="any" className="h-9 w-24 font-mono" value={f.lines[i][k]} onChange={(e) => setL(i, k, e.target.value)} data-testid={`grn-${i}-${k}`} /></td>)}</tr>)}</tbody></table>
      <div className="flex justify-end"><Button onClick={save} disabled={saving} data-testid="grn-save-button">Save GRN</Button></div>
    </DialogContent></Dialog>
  );
};

export default function PoEditor() {
  const { id } = useParams();
  const isNew = id === "new";
  const nav = useNavigate();
  const { settings } = useApp();
  const { perm } = useErp();
  const projects = useProjects();
  const vendors = useVendors();
  const [doc, setDoc] = useState(null);
  const [f, setF] = useState(isNew ? { number: "", date: todayIso(), project_id: "", vendor_id: "", delivery_date: "", delivery_address: "", template: "classic", gst_type: "", items: [{ ...BLANK_LINE }], payment_terms: "", terms: "" } : null);
  const [logo, setLogo] = useState(null);
  const [grn, setGrn] = useState(false);
  const [cancel, setCancel] = useState(false);
  const [working, setWorking] = useState(false);
  const ref = useRef();
  const load = useCallback(async () => {
    if (isNew) return;
    const { data } = await api.get(`/erp/pos/${id}`);
    setDoc(data);
    setF({ ...data, gst_type: data.gst_type || "", delivery_date: data.delivery_date || "", items: data.items.map((x) => ({ ...BLANK_LINE, ...x })) });
  }, [id, isNew]);
  useEffect(() => { load(); }, [load]);
  const [sig, setSig] = useState(null);
  const [es, setEs] = useState({});
  useEffect(() => { loadLogo(settings).then(setLogo); }, [settings]);
  useEffect(() => { api.get("/erp/settings").then((r) => { setEs(r.data); loadSignature(r.data).then(setSig); }); }, []);
  const vendor = vendors.find((v) => v.id === f?.vendor_id);
  const project = projects.find((p) => p.id === f?.project_id);
  const gst = f?.gst_type || guessGst(settings?.state, vendor?.state);
  const preview = useMemo(() => f && { ...f, ...computeLines(f.items, gst), gst_type: gst, client: vendor || doc?.vendor, project_code: project?.code || doc?.project_code, project_name: project?.name || doc?.project_name, status: doc?.status }, [f, gst, vendor, project, doc]);
  if (!f) return <div className="text-slate-500">Loading...</div>;
  const st = doc?.status || "new";
  const editable = st === "new" || st === "draft";
  const run = async (fn, msg) => { if (working) return null; setWorking(true); try { const r = await fn(); toast.success(msg); return r; } catch (e) { toast.error(errMsg(e)); return null; } finally { setWorking(false); } };
  const save = async () => {
    const body = { ...f, gst_type: f.gst_type || null, rfq_id: f.rfq_id || null, items: cleanLines(f.items) };
    const r = await run(() => (isNew ? api.post("/erp/pos", body) : api.put(`/erp/pos/${id}`, body)), "Purchase order saved");
    if (r) { if (isNew) nav(`/erp/purchases/pos/${r.data.id}`, { replace: true }); else load(); }
  };
  const post = async (p, msg) => { const r = await run(() => api.post(`/erp/pos/${id}/${p}`), msg); if (r) (p === "duplicate" ? nav(`/erp/purchases/pos/${r.data.id}`) : load()); };
  const wa = () => { const m = (vendor?.mobile || "").replace(/\D/g, ""); window.open(`https://wa.me/${m.length === 10 ? "91" + m : m}?text=${encodeURIComponent(`${settings?.company_name}: Purchase Order ${doc.number} dated ${doc.date} for ₹${amt(doc.totals.total)}. Delivery: ${doc.delivery_date || "as agreed"}.`)}`, "_blank"); };
  return (
    <div className="space-y-4" data-testid="po-editor">
      <SubNav />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2"><h2 className="font-heading text-xl font-bold" data-testid="po-title">{doc?.number || "New purchase order"}</h2>
            {doc && <Badge s={doc.status} testid="po-status" />}{doc && doc.status !== "draft" && <Badge s={doc.receipt_status} testid="po-receipt-status" />}</div>
          {doc?.cancel_reason && <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-800">Cancelled: {doc.cancel_reason}</div>}
          <fieldset disabled={!editable} className="rounded-xl border bg-white p-4 grid gap-3 sm:grid-cols-2">
            <div className="space-y-1"><Label>PO number</Label><Input className="font-mono" placeholder="Automatic" value={f.number} onChange={(e) => setF({ ...f, number: e.target.value })} data-testid="po-number-input" /></div>
            <div className="space-y-1"><Label>Date</Label><Input type="date" value={f.date} onChange={(e) => setF({ ...f, date: e.target.value })} data-testid="po-date-input" /></div>
            <div className="space-y-1"><Label>Project *</Label><Sel value={f.project_id} onChange={(v) => setF({ ...f, project_id: v })} placeholder="Select project" opts={projects.map((p) => [p.id, `${p.code} · ${p.name}`])} testid="po-project-select" /></div>
            <div className="space-y-1"><Label>Vendor *</Label><Sel value={f.vendor_id} onChange={(v) => setF({ ...f, vendor_id: v })} placeholder="Select vendor" opts={vendors.map((v) => [v.id, v.company_name])} testid="po-vendor-select" /></div>
            <div className="space-y-1"><Label>Delivery date</Label><Input type="date" value={f.delivery_date} onChange={(e) => setF({ ...f, delivery_date: e.target.value })} data-testid="po-delivery-input" /></div>
            <div className="space-y-1"><Label>GST</Label><Sel value={f.gst_type || ""} onChange={(v) => setF({ ...f, gst_type: v })} placeholder={`Automatic (${gst === "inter" ? "IGST" : "CGST + SGST"})`} opts={[["intra", "CGST + SGST"], ["inter", "IGST"], ["none", "No GST"]]} testid="po-gst-select" /></div>
            <div className="sm:col-span-2 space-y-1"><Label>Delivery address</Label><Input value={f.delivery_address} onChange={(e) => setF({ ...f, delivery_address: e.target.value })} data-testid="po-address-input" /></div>
            <div className="sm:col-span-2"><LineItems prefix="po-line" lines={f.items} setLines={(items) => setF({ ...f, items })} disabled={!editable} /></div>
            <div className="space-y-1"><Label>Payment terms</Label><Input value={f.payment_terms} onChange={(e) => setF({ ...f, payment_terms: e.target.value })} data-testid="po-payterms-input" /></div>
            <div className="space-y-1"><Label>Other terms</Label><Input value={f.terms} onChange={(e) => setF({ ...f, terms: e.target.value })} data-testid="po-terms-input" /></div>
          </fieldset>
          <div className={`flex flex-wrap gap-2 ${working ? "pointer-events-none opacity-60" : ""}`} data-testid="po-actions">
            {editable && perm(isNew ? "create" : "edit") && <Button onClick={save} data-testid="po-save-button">Save draft</Button>}
            {st === "draft" && perm("approve") && <Button className="bg-emerald-700 hover:bg-emerald-800" onClick={() => post("approve", "Purchase order approved")} data-testid="po-approve-button">Approve</Button>}
            {st === "approved" && perm("create") && doc.receipt_status !== "received" && <Button onClick={() => setGrn(true)} data-testid="po-grn-button">Receive goods (GRN)</Button>}
            {st !== "new" && st !== "draft" && st !== "cancelled" && perm("create") && <Button variant="outline" onClick={() => nav(`/erp/purchases/bills/new?po=${id}`)} data-testid="po-bill-button">Enter purchase bill</Button>}
            {st === "approved" && perm("approve") && <Button variant="outline" onClick={() => post("close", "PO closed")} data-testid="po-close-button">Close PO</Button>}
            {doc && <Button variant="outline" onClick={() => printNode(ref.current, doc.number)} data-testid="po-print-button"><Printer className="h-4 w-4 mr-1" /> Print / PDF</Button>}
            {doc && perm("create") && <Button variant="outline" onClick={() => post("duplicate", "Duplicated as new draft")} data-testid="po-duplicate-button">Duplicate</Button>}
            {doc && vendor?.mobile && st !== "draft" && <Button variant="outline" className="text-[#128C7E]" onClick={wa} data-testid="po-whatsapp-button">WhatsApp</Button>}
            {doc && !["cancelled", "closed"].includes(st) && perm("cancel") && <Button variant="outline" className="text-red-600" onClick={() => setCancel(true)} data-testid="po-cancel-button">Cancel</Button>}
            {st === "draft" && perm("delete") && <Button variant="outline" className="text-red-600" onClick={async () => window.confirm("Delete draft?") && (await run(() => api.delete(`/erp/pos/${id}`), "Deleted")) && nav("/erp/purchases/pos")} data-testid="po-delete-button">Delete</Button>}
          </div>
          {doc && doc.status !== "draft" && <div className="rounded-xl border bg-white overflow-x-auto" data-testid="po-receipt-table">
            <div className="px-4 py-3 font-semibold">Receipt status · received value ₹{amt(doc.received_value)}</div>
            <table className="w-full eb-table"><thead><tr><th>Item</th><th>Ordered</th><th>Accepted</th><th>Rejected</th><th>Pending</th><th>Billed</th></tr></thead>
              <tbody>{doc.items.map((it, i) => <tr key={i}><td>{it.description}</td><td>{it.qty}</td><td>{it.accepted}</td><td>{it.rejected}</td><td className={it.pending > 0 ? "text-amber-700 font-semibold" : ""}>{it.pending}</td><td>{it.billed_qty}</td></tr>)}</tbody></table>
            <div className="px-4 py-2 text-sm space-y-1">{doc.grns.map((g) => <div key={g.id}>{g.number} · {dmy(g.date)} · ₹{amt(g.accepted_value)} <Badge s={g.status} /></div>)}
              {doc.bills.map((b) => <div key={b.id}><a className="text-primary" href={`/erp/purchases/bills/${b.id}`}>{b.number}</a> · vendor inv {b.vendor_invoice_no} · ₹{amt(b.totals.total)} <Badge s={b.status} /></div>)}</div>
          </div>}
        </div>
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2 items-center"><span className="text-xs uppercase tracking-wide text-slate-500">Live preview · format</span>
            {TEMPLATES.map(([k, l]) => <button key={k} disabled={!editable} onClick={() => setF({ ...f, template: k })} className={`rounded-full border px-3 py-1 text-xs font-semibold ${f.template === k ? "bg-slate-900 text-white" : "bg-white"}`} data-testid={`po-template-${k}`}>{l}</button>)}</div>
          <div className="rounded-xl border bg-slate-100 p-3 overflow-x-auto"><DocTemplate ref={ref} kind="po" doc={preview} company={settings || {}} logo={logo} template={f.template} signatory={es.authorized_signatory} signature={sig} /></div>
        </div>
      </div>
      {grn && <GRNDialog po={doc} onClose={() => setGrn(false)} onSaved={load} />}
      <ReasonDialog open={cancel} onClose={() => setCancel(false)} title={`Cancel ${doc?.number}`} note="Only possible before any goods are received or billed."
        onOk={async (reason) => { if (await run(() => api.post(`/erp/pos/${id}/cancel`, { reason }), "Cancelled")) { setCancel(false); load(); } }} />
    </div>
  );
}
