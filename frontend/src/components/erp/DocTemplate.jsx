import { forwardRef } from "react";
import { amt, dmy } from "@/lib/format";
import { inWords } from "@/lib/invoice";
import { fromErp, renderGstBody } from "@/lib/gstInvoice";

const THEMES = {
  classic: { wrap: "font-serif", head: "border-b-4 border-double border-slate-800 pb-4", title: "text-slate-900", th: "bg-slate-100 text-slate-800", accent: "text-slate-900" },
  modern: { wrap: "font-sans", head: "bg-emerald-700 text-white -mx-8 -mt-8 px-8 py-6 mb-2", title: "text-white", th: "bg-emerald-700 text-white", accent: "text-emerald-700" },
  detailed: { wrap: "font-sans", head: "border-b-2 border-indigo-800 pb-4", title: "text-indigo-900", th: "bg-indigo-50 text-indigo-900", accent: "text-indigo-900" },
};

const Row = ({ l, v, b }) => <tr className={b ? "font-bold" : ""}><td className="py-1 pr-4">{l}</td><td className="py-1 text-right font-mono">{v}</td></tr>;

const Party = ({ c, label }) => (
  <div className="text-sm">
    <div className="text-[10px] uppercase tracking-wider text-slate-500">{label}</div>
    <div className="font-semibold">{c?.company_name}</div>
    <div className="whitespace-pre-line">{c?.address}</div>
    {c?.state && <div>State: {c.state}</div>}
    {c?.gstin && <div>GSTIN: {c.gstin}</div>}
    {c?.contact_person && <div>Attn: {c.contact_person}{c.mobile ? ` · ${c.mobile}` : ""}</div>}
  </div>
);

export const DocTemplate = forwardRef(({ kind, doc, company = {}, logo, template = "classic", signatory, signature }, ref) => {
  if (kind === "invoice" && template?.startsWith("gst_")) {
    const html = renderGstBody(fromErp({ ...doc, template }, company, { logo, signature, signatory }));
    return <div ref={ref} className="w-full max-w-[860px] mx-auto shadow-sm bg-white" data-testid={`invoice-preview-${template}`} dangerouslySetInnerHTML={{ __html: html }} />;
  }
  const t = THEMES[template] || THEMES.classic;
  const inv = kind === "invoice";
  const T = doc.totals || {};
  const detailed = template === "detailed";
  const net = inv ? T.net_payable : T.total;
  return (
    <div ref={ref} className={`bg-white text-slate-900 p-8 text-[13px] leading-relaxed w-full max-w-[820px] mx-auto shadow-sm ${t.wrap}`} data-testid={`${kind}-preview-${template}`}>
      <div className={`flex items-start gap-4 ${t.head}`}>
        {logo && <img src={logo} alt="logo" className="h-16 w-16 object-contain bg-white rounded" />}
        <div className="flex-1">
          <div className={`text-2xl font-bold ${t.title}`}>{company.company_name}</div>
          <div className="whitespace-pre-line text-xs opacity-90">{company.address}</div>
          <div className="text-xs opacity-90">{[company.gstin && `GSTIN: ${company.gstin}`, company.pan && `PAN: ${company.pan}`, company.phone, company.email].filter(Boolean).join(" · ")}</div>
        </div>
        <div className="text-right">
          <div className={`text-xl font-extrabold uppercase tracking-wide ${t.title}`}>{{ invoice: "Tax Invoice", quotation: "Quotation", po: "Purchase Order" }[kind]}</div>
          <div>No: <b data-testid={`${kind}-preview-number`}>{doc.number || "DRAFT"}</b></div>
          <div>Date: {dmy(doc.date)}</div>
          {inv ? <div>Due: {dmy(doc.due_date)}</div> : kind === "po" ? doc.delivery_date && <div>Delivery by: {dmy(doc.delivery_date)}</div> : doc.valid_until && <div>Valid till: {dmy(doc.valid_until)}</div>}
          {doc.status === "cancelled" && <div className="inline-block mt-1 rounded bg-red-600 px-2 py-0.5 text-xs font-bold text-white" data-testid={`${kind}-preview-cancelled`}>CANCELLED</div>}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-6 my-4">
        <Party c={doc.client} label={{ invoice: "Bill to", quotation: "Quotation for", po: "Vendor" }[kind]} />
        <div className="text-sm">
          {doc.project_code && <><div className="text-[10px] uppercase tracking-wider text-slate-500">Project</div>
            <div className="font-semibold">{doc.project_code} · {doc.project_name}</div>{doc.project_location && <div>{doc.project_location}</div>}</>}
          {doc.subject && <div className="mt-1"><b>Subject:</b> {doc.subject}</div>}
          {doc.po_reference && <div><b>PO / WO ref:</b> {doc.po_reference}</div>}
          {kind === "po" && doc.delivery_address && <div><b>Deliver to:</b> <span className="whitespace-pre-line">{doc.delivery_address}</span></div>}
          <div>Place of supply: {doc.gst_type === "inter" ? "Inter-state (IGST)" : doc.gst_type === "none" ? "Without GST" : "Intra-state (CGST + SGST)"}</div>
        </div>
      </div>
      {!inv && doc.scope_of_work && <div className="mb-3"><div className={`font-semibold ${t.accent}`}>Scope of work</div><div className="whitespace-pre-line">{doc.scope_of_work}</div></div>}
      <table className="w-full border-collapse text-[12px]">
        <thead><tr className={t.th}>
          <th className="border px-2 py-1 text-left">#</th><th className="border px-2 py-1 text-left">Description</th>
          {(detailed || inv) && <th className="border px-2 py-1">HSN/SAC</th>}
          <th className="border px-2 py-1 text-right">Qty</th><th className="border px-2 py-1 text-right">Rate</th><th className="border px-2 py-1 text-right">Disc %</th>
          <th className="border px-2 py-1 text-right">Taxable</th><th className="border px-2 py-1 text-right">GST %</th>
          {detailed && <th className="border px-2 py-1 text-right">GST ₹</th>}<th className="border px-2 py-1 text-right">Amount</th>
        </tr></thead>
        <tbody>
          {(doc.items || []).map((it, i) => (
            <tr key={i}><td className="border px-2 py-1">{i + 1}</td><td className="border px-2 py-1 whitespace-pre-line">{it.description}</td>
              {(detailed || inv) && <td className="border px-2 py-1 text-center">{it.hsn}</td>}
              <td className="border px-2 py-1 text-right">{Number(it.qty)} {it.unit}</td><td className="border px-2 py-1 text-right">{amt(it.rate)}</td>
              <td className="border px-2 py-1 text-right">{Number(it.discount || 0)}</td><td className="border px-2 py-1 text-right">{amt(it.amount)}</td>
              <td className="border px-2 py-1 text-right">{doc.gst_type === "none" ? 0 : it.gst_rate}</td>
              {detailed && <td className="border px-2 py-1 text-right">{amt(it.cgst + it.sgst + it.igst)}</td>}<td className="border px-2 py-1 text-right">{amt(it.total)}</td></tr>
          ))}
        </tbody>
      </table>
      <div className="flex gap-6 mt-4">
        <div className="flex-1 space-y-3">
          {inv && doc.billing && (
            <table className="text-[12px] border-collapse w-full" data-testid="invoice-preview-billing">
              <thead><tr className={t.th}><th className="border px-2 py-1 text-left">Billing summary</th><th className="border px-2 py-1 text-right">Amount (₹)</th></tr></thead>
              <tbody>
                {doc.billing.contract_value > 0 && <tr><td className="border px-2 py-1">Contract value</td><td className="border px-2 py-1 text-right">{amt(doc.billing.contract_value)}</td></tr>}
                <tr><td className="border px-2 py-1">Previous billing</td><td className="border px-2 py-1 text-right">{amt(doc.billing.previous)}</td></tr>
                <tr><td className="border px-2 py-1">Current billing</td><td className="border px-2 py-1 text-right">{amt(T.total)}</td></tr>
                <tr className="font-semibold"><td className="border px-2 py-1">Cumulative billing</td><td className="border px-2 py-1 text-right">{amt((doc.billing.previous || 0) + (T.total || 0))}</td></tr>
              </tbody>
            </table>
          )}
          <div className="text-[12px]"><b>Amount in words:</b> <span data-testid={`${kind}-preview-words`}>{inWords(net || 0)}</span></div>
          {!inv && (doc.delivery_terms || doc.payment_terms) && <div className="text-[12px]" data-testid={`${kind}-preview-terms`}>
            {doc.delivery_terms && <div><b>Delivery:</b> <span className="whitespace-pre-line">{doc.delivery_terms}</span></div>}
            {doc.payment_terms && <div><b>Payment terms:</b> <span className="whitespace-pre-line">{doc.payment_terms}</span></div>}</div>}
          {inv && (company.bank_name || company.bank_account) && <div className="text-[12px]"><b>Bank details:</b> {company.bank_name} · A/c {company.bank_account} · IFSC {company.bank_ifsc}{company.upi_id ? ` · UPI ${company.upi_id}` : ""}</div>}
          {(doc.terms || doc.notes || (inv && company.invoice_terms)) && <div className="text-[11px] text-slate-600 whitespace-pre-line"><b>Terms:</b> {doc.terms || doc.notes || company.invoice_terms}</div>}
        </div>
        <table className="w-64 text-[12px]">
          <tbody>
            {T.discount > 0 && <Row l="Gross" v={amt(T.gross)} />}{T.discount > 0 && <Row l="Discount" v={`- ${amt(T.discount)}`} />}
            <Row l="Taxable value" v={amt(T.taxable)} />
            {T.cgst > 0 && <Row l="CGST" v={amt(T.cgst)} />}{T.sgst > 0 && <Row l="SGST" v={amt(T.sgst)} />}{T.igst > 0 && <Row l="IGST" v={amt(T.igst)} />}
            <Row l={inv ? "Invoice total" : "Total (₹)"} v={amt(T.total)} b />
            {inv && T.retention > 0 && <Row l={`Retention (${doc.retention_pct}%)`} v={`- ${amt(T.retention)}`} />}
            {inv && T.advance_adjust > 0 && <Row l="Advance adjusted" v={`- ${amt(T.advance_adjust)}`} />}
            {inv && T.deductions > 0 && <Row l={`Deductions${doc.deduction_note ? ` (${doc.deduction_note})` : ""}`} v={`- ${amt(T.deductions)}`} />}
            {inv && <tr className={`font-extrabold text-[14px] ${t.accent}`}><td className="pt-2">Net payable</td><td className="pt-2 text-right font-mono" data-testid="invoice-preview-net">₹{amt(T.net_payable)}</td></tr>}
          </tbody>
        </table>
      </div>
      <div className="flex justify-end mt-10 text-right text-[12px]">
        <div>{signature ? <img src={signature} alt="signature" className="h-12 ml-auto object-contain" data-testid="doc-signature" /> : <div className="h-12" />}<div className="border-t border-slate-400 pt-1">For {company.company_name}<br />{signatory || "Authorised Signatory"}</div></div>
      </div>
    </div>
  );
});
DocTemplate.displayName = "DocTemplate";
