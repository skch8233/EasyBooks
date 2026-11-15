import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Mail } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { amt, dmy, todayIso } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ReasonDialog } from "@/components/erp/InvoiceSide";
import { useErp, Badge } from "@/pages/erp/ErpShell";
import { ReqLines, Sel, SubNav, cleanReq, useProjects, useVendors } from "@/pages/erp/Purchases";

const NewRFQ = () => {
  const [sp] = useSearchParams();
  const nav = useNavigate();
  const projects = useProjects();
  const vendors = useVendors();
  const [f, setF] = useState({ project_id: "", pr_id: sp.get("pr") || null, date: todayIso(), due_date: "", vendor_ids: [], items: [{ description: "", unit: "", qty: 1, notes: "" }], terms: "" });
  useEffect(() => {
    if (f.pr_id) api.get(`/erp/prs/${f.pr_id}`).then((r) => setF((x) => ({ ...x, project_id: r.data.project_id, items: r.data.items.map((i) => ({ ...i, notes: i.notes || "" })) })));
  }, [f.pr_id]);
  const toggle = (id) => setF({ ...f, vendor_ids: f.vendor_ids.includes(id) ? f.vendor_ids.filter((x) => x !== id) : [...f.vendor_ids, id] });
  const save = async () => {
    try { const { data } = await api.post("/erp/rfqs", { ...f, items: cleanReq(f.items) }); toast.success(`${data.number} created`); nav(`/erp/purchases/rfqs/${data.id}`, { replace: true }); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div className="rounded-xl border bg-white p-5 grid gap-4 sm:grid-cols-3 max-w-4xl" data-testid="rfq-form">
      <div className="space-y-1"><Label>Project *</Label><Sel value={f.project_id} disabled={!!f.pr_id} onChange={(v) => setF({ ...f, project_id: v })} placeholder="Select project" opts={projects.map((p) => [p.id, `${p.code} · ${p.name}`])} testid="rfq-project-select" /></div>
      <div className="space-y-1"><Label>Date</Label><Input type="date" value={f.date} onChange={(e) => setF({ ...f, date: e.target.value })} data-testid="rfq-date-input" /></div>
      <div className="space-y-1"><Label>Quotes due by</Label><Input type="date" value={f.due_date} onChange={(e) => setF({ ...f, due_date: e.target.value })} data-testid="rfq-due-input" /></div>
      <div className="sm:col-span-3 space-y-1"><Label>Invite vendors * ({f.vendor_ids.length} selected)</Label>
        <div className="flex flex-wrap gap-2">{vendors.map((v) => <button key={v.id} type="button" onClick={() => toggle(v.id)} data-testid={`rfq-vendor-${v.id}`}
          className={`rounded-full border px-3 py-1.5 text-sm ${f.vendor_ids.includes(v.id) ? "bg-emerald-700 text-white" : "bg-white"}`}>{v.company_name}</button>)}
          {vendors.length === 0 && <span className="text-sm text-amber-700">Add vendors in Clients & Vendors first.</span>}</div></div>
      <div className="sm:col-span-3"><ReqLines lines={f.items} setLines={(items) => setF({ ...f, items })} prefix="rfq-line" /></div>
      <div className="sm:col-span-3 space-y-1"><Label>Terms / instructions</Label><Input value={f.terms} onChange={(e) => setF({ ...f, terms: e.target.value })} data-testid="rfq-terms-input" /></div>
      <div className="sm:col-span-3"><Button onClick={save} data-testid="rfq-save-button">Create RFQ</Button></div>
    </div>
  );
};

const QuoteDialog = ({ rfq, vendor, existing, onClose, onSaved }) => {
  const [f, setF] = useState({ quote_ref: existing?.quote_ref || "", date: existing?.date || todayIso(), delivery_days: existing?.delivery_days || 0, payment_terms: existing?.payment_terms || "",
    lines: rfq.items.map((_, i) => ({ rate: existing?.items[i]?.rate ?? "", discount: existing?.items[i]?.discount ?? 0, gst_rate: existing?.items[i]?.gst_rate ?? 18 })) });
  const setL = (i, k, v) => setF({ ...f, lines: f.lines.map((l, n) => (n === i ? { ...l, [k]: v } : l)) });
  const save = async () => {
    try {
      await api.post(`/erp/rfqs/${rfq.id}/quotes`, { ...f, vendor_id: vendor.id, delivery_days: Number(f.delivery_days || 0), lines: f.lines.map((l) => ({ rate: Number(l.rate || 0), discount: Number(l.discount || 0), gst_rate: Number(l.gst_rate || 0) })) });
      toast.success("Vendor quotation saved"); onSaved(); onClose();
    } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}><DialogContent className="max-w-3xl"><DialogHeader><DialogTitle>Quotation from {vendor.company_name}</DialogTitle></DialogHeader>
      <div className="grid gap-3 sm:grid-cols-4">
        {[["quote_ref", "Vendor quote ref", "text"], ["date", "Date", "date"], ["delivery_days", "Delivery (days)", "number"], ["payment_terms", "Payment terms", "text"]].map(([k, l, t]) =>
          <div key={k} className="space-y-1"><Label>{l}</Label><Input type={t} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} data-testid={`vq-${k}-input`} /></div>)}
      </div>
      <table className="w-full eb-table"><thead><tr><th>Item</th><th>Qty</th><th>Rate</th><th>Disc %</th><th>GST %</th></tr></thead>
        <tbody>{rfq.items.map((it, i) => <tr key={i}><td>{it.description}</td><td>{it.qty} {it.unit}</td>
          {["rate", "discount", "gst_rate"].map((k) => <td key={k}><Input type="number" step="any" className="h-9 w-28 font-mono" value={f.lines[i][k]} onChange={(e) => setL(i, k, e.target.value)} data-testid={`vq-${i}-${k}`} /></td>)}</tr>)}</tbody></table>
      <div className="flex justify-end"><Button onClick={save} data-testid="vq-save-button">Save quotation</Button></div>
    </DialogContent></Dialog>
  );
};

export default function RfqView() {
  const { id } = useParams();
  const nav = useNavigate();
  const { perm } = useErp();
  const [r, setR] = useState(null);
  const [qv, setQv] = useState(null);
  const [cancel, setCancel] = useState(false);
  const load = useCallback(() => api.get(`/erp/rfqs/${id}`).then((x) => setR(x.data)), [id]);
  useEffect(() => { if (id !== "new") load(); }, [id, load]);
  if (id === "new") return <div className="space-y-4"><SubNav /><h2 className="font-heading text-xl font-bold">New request for quotation</h2><NewRFQ /></div>;
  if (!r) return <div className="text-slate-500">Loading...</div>;
  const cmp = r.comparison;
  const run = async (fn, msg) => { try { const x = await fn(); toast.success(msg); return x; } catch (e) { toast.error(errMsg(e)); return null; } };
  const select = async (q) => {
    const reason = q.quote_id === cmp.lowest_quote_id ? "" : window.prompt("This is not the lowest quotation. Reason for selecting it?") || "";
    if (await run(() => api.post(`/erp/rfqs/${id}/select`, { quote_id: q.quote_id, reason }), `${q.vendor_name} selected`)) load();
  };
  return (
    <div className="space-y-4" data-testid="rfq-view">
      <SubNav />
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="font-heading text-xl font-bold" data-testid="rfq-number">{r.number}</h2><Badge s={r.status} testid="rfq-status" />
        <span className="text-sm text-slate-600">{r.project_code} {r.project_name}{r.pr_number && ` · from ${r.pr_number}`}{r.due_date && ` · quotes due ${dmy(r.due_date)}`}</span>
        <div className="ml-auto flex gap-2">
          {r.status === "open" && <Button variant="outline" onClick={() => run(() => api.post(`/erp/rfqs/${id}/send`), "RFQ emailed to vendors").then(load)} data-testid="rfq-send-button"><Mail className="h-4 w-4 mr-1" /> Email vendors</Button>}
          {r.status === "selected" && perm("create") && <Button onClick={async () => { const x = await run(() => api.post(`/erp/rfqs/${id}/create-po`), "Draft purchase order created"); if (x) nav(`/erp/purchases/pos/${x.data.id}`); }} data-testid="rfq-create-po">Create purchase order</Button>}
          {r.po_number && <Button variant="outline" onClick={() => nav(`/erp/purchases/pos/${r.po_id}`)} data-testid="rfq-open-po">{r.po_number}</Button>}
          {["open", "selected"].includes(r.status) && perm("cancel") && <Button variant="outline" className="text-red-600" onClick={() => setCancel(true)} data-testid="rfq-cancel-button">Cancel</Button>}
        </div>
      </div>
      {r.sent_to?.length > 0 && <div className="text-xs text-slate-500">Emailed to: {r.sent_to.join(", ")}</div>}
      <div className="rounded-xl border bg-white p-4 flex flex-wrap gap-2" data-testid="rfq-vendors">
        <b className="w-full text-sm">Vendor quotations</b>
        {r.vendors.map((v) => { const q = r.quotes.find((x) => x.vendor_id === v.id); return (
          <Button key={v.id} size="sm" variant={q ? "default" : "outline"} disabled={r.status !== "open" || !perm("create")} onClick={() => setQv({ vendor: v, existing: q })} data-testid={`rfq-enter-quote-${v.id}`}>
            {v.company_name}{q ? ` · ₹${amt(q.totals.total)}` : " · enter quote"}</Button>); })}
      </div>
      <div className="rounded-xl border bg-white overflow-x-auto" data-testid="comparative-statement">
        <div className="px-4 py-3 font-semibold">Comparative statement <span className="text-xs font-normal text-slate-500">(lowest highlighted in green)</span></div>
        {cmp.vendors.length === 0 ? <div className="p-6 text-sm text-slate-500">Enter at least one vendor quotation to compare.</div> :
          <table className="w-full eb-table min-w-[720px]">
            <thead><tr><th>Item</th><th>Qty</th>{cmp.vendors.map((v) => <th key={v.vendor_id} className="text-right">{v.vendor_name}</th>)}</tr></thead>
            <tbody>
              {cmp.rows.map((row, i) => <tr key={i}><td>{row.description}</td><td>{row.qty} {row.unit}</td>
                {cmp.vendors.map((v) => { const c = row.quotes.find((x) => x.vendor_id === v.vendor_id); return <td key={v.vendor_id} className={`text-right font-mono ${row.lowest_vendor_id === v.vendor_id ? "bg-emerald-50 text-emerald-800 font-bold" : ""}`} data-testid={`cmp-${i}-${v.vendor_id}`}>
                  {c ? <>{amt(c.net_rate)}{c.discount > 0 && <span className="text-[10px] text-slate-500"> (−{c.discount}%)</span>}<div className="text-[10px] text-slate-500">GST {c.gst_rate}% · ₹{amt(c.total)}</div></> : "-"}</td>; })}</tr>)}
              {[["Taxable", "taxable"], ["Total incl GST", "total"]].map(([l, k]) => <tr key={k} className="font-semibold"><td colSpan={2}>{l}</td>{cmp.vendors.map((v) =>
                <td key={v.vendor_id} className={`text-right font-mono ${k === "total" && v.quote_id === cmp.lowest_quote_id ? "bg-emerald-100 text-emerald-900" : ""}`} data-testid={`cmp-${k}-${v.vendor_id}`}>{amt(v[k])}</td>)}</tr>)}
              <tr><td colSpan={2}>Delivery / payment</td>{cmp.vendors.map((v) => <td key={v.vendor_id} className="text-right text-xs">{[v.delivery_days ? `${v.delivery_days} days` : "", v.payment_terms].filter(Boolean).join(" · ") || "-"}</td>)}</tr>
              <tr><td colSpan={2}></td>{cmp.vendors.map((v) => <td key={v.vendor_id} className="text-right">
                {r.selected_quote_id === v.quote_id ? <Badge s="selected" testid="cmp-selected" /> : ["open", "selected"].includes(r.status) && perm("approve") &&
                  <Button size="sm" variant="outline" onClick={() => select(v)} data-testid={`cmp-select-${v.vendor_id}`}>Select</Button>}</td>)}</tr>
            </tbody>
          </table>}
        {r.selection_reason && <div className="px-4 pb-3 text-sm">Selection reason: {r.selection_reason}</div>}
      </div>
      {qv && <QuoteDialog rfq={r} vendor={qv.vendor} existing={qv.existing} onClose={() => setQv(null)} onSaved={load} />}
      <ReasonDialog open={cancel} onClose={() => setCancel(false)} title={`Cancel ${r.number}`} note="Vendor quotations stay on record."
        onOk={async (reason) => { if (await run(() => api.post(`/erp/rfqs/${id}/cancel`, { reason }), "Cancelled")) { setCancel(false); load(); } }} />
    </div>
  );
}
