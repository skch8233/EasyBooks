import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Ban, Copy, FileCheck2, Mail, MessageCircle, Printer, Save, Trash2 } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { amt, dmyTime, todayIso } from "@/lib/format";
import { GstMetaFields } from "@/components/GstMetaFields";
import { BLANK_LINE, INVOICE_TEMPLATES, TEMPLATES, computeLines, guessGst, invoiceTotals, loadLogo, loadSignature, printNode } from "@/lib/erp";
import { useApp } from "@/context/AppContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DocTemplate } from "@/components/erp/DocTemplate";
import { LineItems, cleanLines } from "@/components/erp/LineItems";
import { InvoiceSide, ReasonDialog } from "@/components/erp/InvoiceSide";
import { useErp, Badge } from "@/pages/erp/ErpShell";

const addDays = (iso, d) => { const x = new Date(iso); x.setDate(x.getDate() + Number(d || 0)); return x.toISOString().slice(0, 10); };

const blank = (inv, tpl) => ({ number: "", date: todayIso(), valid_until: addDays(todayIso(), 30), due_date: addDays(todayIso(), 30), client_id: "", project_id: "", template: tpl || "classic",
  gst_type: "", subject: "", items: [{ ...BLANK_LINE }], scope_of_work: "", delivery_terms: "", payment_terms: "", notes: "", terms: "",
  retention_pct: 0, advance_adjust: 0, deductions: 0, deduction_note: "", po_reference: "", gst_meta: {} });

export default function DocEditor({ kind }) {
  const inv = kind === "invoice";
  const base = inv ? "invoices" : "quotations";
  const { id } = useParams();
  const [sp] = useSearchParams();
  const nav = useNavigate();
  const { settings } = useApp();
  const { perm } = useErp();
  const [doc, setDoc] = useState(null);
  const [f, setF] = useState(null);
  const [clients, setClients] = useState([]);
  const [projects, setProjects] = useState([]);
  const [prevBilled, setPrevBilled] = useState(0);
  const [logo, setLogo] = useState(null);
  const [es, setEs] = useState({});
  const [sig, setSig] = useState(null);
  const [unlock, setUnlock] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);
  const ref = useRef();

  const load = useCallback(async () => {
    const [c, p, s] = await Promise.all([api.get("/erp/parties", { params: { kind: "client" } }), api.get("/erp/projects"), api.get("/erp/settings")]);
    setClients(c.data); setProjects(p.data); setEs(s.data); loadSignature(s.data).then(setSig);
    if (id) {
      const { data } = await api.get(`/erp/${base}/${id}`);
      setDoc(data);
      setF({ ...blank(inv), ...data, number: data.number || data.manual_number || "", project_id: data.project_id || "", items: data.items.map((x) => ({ ...BLANK_LINE, ...x })) });
      setUnlock(false);
    } else {
      const pid = sp.get("project");
      const pr = p.data.find((x) => x.id === pid);
      setF({ ...blank(inv, inv ? s.data.default_invoice_template : s.data.default_quote_template), project_id: pr?.id || "", client_id: pr?.client_id || "",
        payment_terms: !inv ? "" : "", notes: inv ? "" : s.data.quote_terms || "" });
    }
  }, [id, base, inv, sp]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadLogo(settings).then(setLogo); }, [settings]);
  useEffect(() => {
    if (!inv || !f?.project_id || doc?.status === "finalized" || doc?.status === "cancelled") return;
    api.get(`/erp/projects/${f.project_id}`).then((r) => setPrevBilled(r.data.numbers.billed)).catch(() => setPrevBilled(0));
  }, [inv, f?.project_id, doc?.status]);

  const client = clients.find((c) => c.id === f?.client_id);
  const project = projects.find((p) => p.id === f?.project_id);
  const gst = f?.gst_type || guessGst(settings?.state, client?.state);
  const preview = useMemo(() => {
    if (!f) return null;
    const { items, totals } = computeLines(f.items, gst);
    const prev = doc?.status === "finalized" || doc?.status === "cancelled" ? doc.billing?.previous || 0 : prevBilled;
    return { ...f, number: doc?.number || f.number, status: doc?.status, gst_type: gst, items, totals: inv ? invoiceTotals(totals, f) : totals,
      client: client || doc?.client, project_code: project?.code || doc?.project_code, project_name: project?.name || doc?.project_name, project_location: project?.location,
      billing: inv ? { previous: prev, contract_value: project?.contract_value || 0 } : null };
  }, [f, gst, client, project, doc, inv, prevBilled]);
  if (!f) return <div className="text-slate-500">Loading...</div>;

  const st = doc?.status || "new";
  const editable = inv ? (st === "new" || st === "draft" || (st === "finalized" && unlock)) : ["new", "draft", "sent"].includes(st);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const body = () => ({ ...f, gst_type: f.gst_type || null, project_id: f.project_id || (inv ? "" : null), items: cleanLines(f.items),
    retention_pct: Number(f.retention_pct || 0), advance_adjust: Number(f.advance_adjust || 0), deductions: Number(f.deductions || 0), template: f.template });
  const run = async (fn, msg) => { try { const r = await fn(); if (msg) toast.success(msg); return r; } catch (e) { toast.error(errMsg(e)); return null; } };
  const save = async () => {
    const r = await run(() => (id ? api.put(`/erp/${base}/${id}`, body()) : api.post(`/erp/${base}`, body())), st === "finalized" ? "Finalized invoice updated (new version saved, accounting entry updated)" : "Saved");
    if (r) { if (!id) nav(`/erp/${base}/${r.data.id}`, { replace: true }); else load(); }
  };
  const act = async (path, payload, msg, after) => { const r = await run(() => api.post(`/erp/${base}/${id}/${path}`, payload), msg); if (r) (after ? after(r.data) : load()); };
  const pickProject = (pid) => { const p = projects.find((x) => x.id === pid); setF({ ...f, project_id: pid, client_id: p ? p.client_id : f.client_id }); };
  const wa = () => {
    const m = (client?.mobile || "").replace(/\D/g, "");
    const text = `${settings?.company_name}: ${inv ? "Invoice" : "Quotation"} ${preview.number} dated ${preview.date} for ${preview.project_code || ""} ${preview.project_name || ""}. Amount ₹${amt(inv ? preview.totals.net_payable : preview.totals.total)}${inv && doc?.balance != null ? `, balance due ₹${amt(doc.balance)} by ${preview.due_date}` : ""}.`;
    window.open(`https://wa.me/${m.length === 10 ? "91" + m : m}?text=${encodeURIComponent(text)}`, "_blank");
  };

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]" data-testid={`${kind}-editor`}>
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="font-heading text-xl font-bold" data-testid={`${kind}-title`}>{doc ? (doc.number || `Draft ${inv ? "invoice" : "quotation"}`) : `New ${inv ? "invoice" : "quotation"}`}</h2>
          {doc && <Badge s={doc.status} testid={`${kind}-status`} />}{doc?.pay_status && <Badge s={doc.pay_status} testid="invoice-pay-status" />}{doc?.overdue && <Badge s="overdue" />}
          {doc?.revision > 0 && <span className="text-xs text-slate-500">Revision {doc.revision}</span>}
        </div>
        {doc?.status === "cancelled" && <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-800" data-testid="cancel-reason">Cancelled: {doc.cancel_reason}</div>}
        <fieldset disabled={!editable} className="rounded-xl border bg-white p-4 grid gap-3 sm:grid-cols-2">
          <div className="space-y-1"><Label>{inv ? "Invoice" : "Quotation"} number</Label><Input className="h-10 font-mono" placeholder="Automatic" value={f.number} onChange={set("number")} disabled={!!doc?.number} data-testid={`${kind}-number-input`} /></div>
          <div className="space-y-1"><Label>Date</Label><Input type="date" className="h-10" value={f.date} onChange={set("date")} disabled={st === "finalized"} data-testid={`${kind}-date-input`} /></div>
          <div className="space-y-1"><Label>Project{inv ? " *" : ""}</Label><select className="h-10 w-full rounded-md border px-2 bg-white" value={f.project_id} onChange={(e) => pickProject(e.target.value)} data-testid={`${kind}-project-select`} disabled={st === "finalized"}>
            <option value="">{inv ? "Select project" : "No project yet"}</option>{projects.map((p) => <option key={p.id} value={p.id}>{p.code} · {p.name}</option>)}</select></div>
          <div className="space-y-1"><Label>Client *</Label><select className="h-10 w-full rounded-md border px-2 bg-white" value={f.client_id} onChange={(e) => setF({ ...f, client_id: e.target.value, project_id: project && project.client_id !== e.target.value ? "" : f.project_id })} data-testid={`${kind}-client-select`} disabled={st === "finalized"}>
            <option value="">Select client</option>{clients.map((c) => <option key={c.id} value={c.id}>{c.company_name}</option>)}</select></div>
          {inv ? <div className="space-y-1"><Label>Due date</Label><Input type="date" className="h-10" value={f.due_date} onChange={set("due_date")} data-testid="invoice-due-input" /></div>
            : <div className="space-y-1"><Label>Valid until</Label><Input type="date" className="h-10" value={f.valid_until} onChange={set("valid_until")} data-testid="quotation-valid-input" /></div>}
          <div className="space-y-1"><Label>GST</Label><select className="h-10 w-full rounded-md border px-2 bg-white" value={f.gst_type || ""} onChange={set("gst_type")} data-testid={`${kind}-gst-select`}>
            <option value="">Automatic ({gst === "inter" ? "IGST" : "CGST + SGST"})</option><option value="intra">CGST + SGST</option><option value="inter">IGST</option><option value="none">No GST</option></select></div>
          {inv ? <div className="space-y-1 sm:col-span-2"><Label>PO / work order reference</Label><Input className="h-10" value={f.po_reference} onChange={set("po_reference")} data-testid="invoice-po-input" /></div>
            : <div className="space-y-1 sm:col-span-2"><Label>Subject</Label><Input className="h-10" value={f.subject} onChange={set("subject")} data-testid="quotation-subject-input" /></div>}
          <div className="sm:col-span-2"><LineItems lines={f.items} setLines={(items) => setF({ ...f, items })} disabled={!editable} /></div>
          {inv ? <>
            {[["retention_pct", "Retention %"], ["advance_adjust", "Advance adjustment (₹)"], ["deductions", "Other deductions (₹)"], ["deduction_note", "Deduction note"]].map(([k, l]) =>
              <div key={k} className="space-y-1"><Label>{l}</Label><Input className="h-10 font-mono" type={k === "deduction_note" ? "text" : "number"} step="any" min="0" value={f[k]} onChange={set(k)} data-testid={`invoice-${k}-input`} /></div>)}
            <div className="sm:col-span-2 space-y-1"><Label>Terms / notes</Label><textarea rows={2} className="w-full rounded-md border p-2 text-sm" value={f.terms} onChange={set("terms")} data-testid="invoice-terms-input" /></div>
            <GstMetaFields value={f.gst_meta || {}} onChange={(gst_meta) => setF({ ...f, gst_meta })} disabled={!editable} prefix="invoice-meta" />
          </> : [["scope_of_work", "Scope of work"], ["delivery_terms", "Delivery terms"], ["payment_terms", "Payment terms"], ["notes", "Terms & conditions"]].map(([k, l]) =>
            <div key={k} className="sm:col-span-2 space-y-1"><Label>{l}</Label><textarea rows={2} className="w-full rounded-md border p-2 text-sm" value={f[k]} onChange={set(k)} data-testid={`quotation-${k}-input`} /></div>)}
        </fieldset>
        <div className="flex flex-wrap gap-2" data-testid={`${kind}-actions`}>
          {editable && perm(st === "finalized" ? "edit_finalized" : id ? "edit" : "create") && <Button onClick={save} data-testid={`${kind}-save-button`}><Save className="h-4 w-4 mr-1" />{st === "finalized" ? "Save new version" : "Save draft"}</Button>}
          {inv && st === "draft" && perm("finalize") && <Button className="bg-emerald-700 hover:bg-emerald-800" onClick={() => window.confirm("Finalize this invoice? It gets a permanent number and is posted to your Easy Books sales ledger.") && act("finalize", {}, "Invoice finalized and posted to accounts")} data-testid="invoice-finalize-button"><FileCheck2 className="h-4 w-4 mr-1" /> Finalize & post</Button>}
          {inv && st === "finalized" && !unlock && perm("edit_finalized") && <Button variant="outline" onClick={() => setUnlock(true)} data-testid="invoice-unlock-button">Edit finalized</Button>}
          {!inv && st === "draft" && <Button variant="outline" onClick={() => act("status", { status: "sent" }, "Marked as sent")} data-testid="quotation-mark-sent">Mark sent</Button>}
          {!inv && ["draft", "sent", "expired"].includes(st) && perm("approve") && <><Button variant="outline" onClick={() => act("status", { status: "accepted" }, "Accepted")} data-testid="quotation-accept">Accept</Button>
            <Button variant="outline" onClick={() => act("status", { status: "rejected" }, "Rejected")} data-testid="quotation-reject">Reject</Button></>}
          {!inv && ["accepted", "converted"].includes(st) && perm("create") && <>
            <Button onClick={() => act("convert", { to: "invoice" }, "Draft invoice created", (d) => nav(`/erp/invoices/${d.invoice_id}`))} data-testid="quotation-convert-invoice">Convert to invoice</Button>
            {!doc.project_id && <Button variant="outline" onClick={() => act("convert", { to: "project" }, "Project created", (d) => nav(`/erp/projects/${d.project_id}`))} data-testid="quotation-convert-project">Create project</Button>}
            {!doc.sales_order_no && <Button variant="outline" onClick={() => act("convert", { to: "sales_order" }, "Sales order created")} data-testid="quotation-convert-so">Sales order</Button>}</>}
          {doc?.sales_order_no && <span className="self-center text-sm" data-testid="quotation-so-number">Sales order: <b>{doc.sales_order_no}</b></span>}
          {doc && <Button variant="outline" onClick={() => printNode(ref.current, preview.number || "Draft")} data-testid={`${kind}-print-button`}><Printer className="h-4 w-4 mr-1" /> Print / PDF</Button>}
          {doc && perm("create") && <Button variant="outline" onClick={() => act("duplicate", {}, "Duplicated as new draft", (d) => nav(`/erp/${base}/${d.id}`))} data-testid={`${kind}-duplicate-button`}><Copy className="h-4 w-4 mr-1" /> Duplicate</Button>}
          {doc && client?.mobile && st !== "draft" && <Button variant="outline" className="text-[#128C7E]" onClick={wa} data-testid={`${kind}-whatsapp-button`}><MessageCircle className="h-4 w-4 mr-1" /> WhatsApp</Button>}
          {inv && st === "finalized" && <Button variant="outline" onClick={() => act("email", {}, `Emailed to ${client?.email}`)} data-testid="invoice-email-button"><Mail className="h-4 w-4 mr-1" /> Email</Button>}
          {((inv && st === "finalized") || (!inv && !["cancelled", "converted", "new"].includes(st))) && perm("cancel") && <Button variant="outline" className="text-red-600" onClick={() => setCancelOpen(true)} data-testid={`${kind}-cancel-button`}><Ban className="h-4 w-4 mr-1" /> Cancel</Button>}
          {st === "draft" && perm("delete") && <Button variant="outline" className="text-red-600" onClick={async () => window.confirm("Delete this draft?") && (await run(() => api.delete(`/erp/${base}/${id}`), "Draft deleted")) && nav(`/erp/${base}`)} data-testid={`${kind}-delete-button`}><Trash2 className="h-4 w-4 mr-1" /> Delete draft</Button>}
        </div>
        {inv && doc?.status === "finalized" && <InvoiceSide doc={doc} reload={load} />}
        {inv && doc?.versions?.length > 0 && <div className="rounded-xl border bg-white p-4 text-sm" data-testid="invoice-versions"><b>Version history</b>
          {doc.versions.map((v) => <div key={v.version} className="border-t mt-2 pt-2">v{v.version} saved {dmyTime(v.saved_at)} by {v.by}: previous total ₹{amt(v.snapshot.totals?.net_payable)}</div>)}</div>}
        <ReasonDialog open={cancelOpen} onClose={() => setCancelOpen(false)} title={`Cancel ${preview.number || "document"}`}
          note={inv ? "The invoice number is never reused. The sales entry in Easy Books is cancelled too." : "The quotation stays on record as cancelled."}
          onOk={(reason) => act("cancel", { reason }, "Cancelled", () => { setCancelOpen(false); load(); })} />
      </div>
      <div className="space-y-3">
        <div className="flex flex-wrap gap-2 items-center no-print">
          <span className="text-xs uppercase tracking-wide text-slate-500">Live preview · format</span>
          {(inv ? INVOICE_TEMPLATES : TEMPLATES).map(([k, l]) => <button key={k} onClick={() => setF({ ...f, template: k })} className={`rounded-full border px-3 py-1 text-xs font-semibold ${f.template === k ? "bg-slate-900 text-white" : "bg-white"}`} data-testid={`${kind}-template-${k}`}>{l}</button>)}
        </div>
        <div className="rounded-xl border bg-slate-100 p-3 overflow-x-auto"><DocTemplate ref={ref} kind={kind} doc={preview} company={settings || {}} logo={logo} template={f.template} signatory={es.authorized_signatory} signature={sig} /></div>
      </div>
    </div>
  );
}
