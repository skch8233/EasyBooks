import { amt, dmy, VT } from "@/lib/format";

const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

export function printVoucher(v, s = {}) {
  const items = v.items?.length
    ? `<table><thead><tr><th>#</th><th>Item</th><th>HSN/SAC</th><th class=r>Qty</th><th class=r>Rate</th><th class=r>GST%</th><th class=r>Taxable</th><th class=r>Total</th></tr></thead><tbody>
      ${v.items.map((i, n) => `<tr><td>${n + 1}</td><td>${esc(i.description)}</td><td>${esc(i.hsn)}</td><td class=r>${i.qty}</td><td class=r>${amt(i.rate)}</td><td class=r>${i.gst_rate}</td><td class=r>${amt(i.amount)}</td><td class=r>${amt(i.total)}</td></tr>`).join("")}
      </tbody></table>
      <table class=sum><tr><td>Taxable</td><td class=r>${amt(v.totals.taxable)}</td></tr>
      ${v.totals.cgst ? `<tr><td>CGST</td><td class=r>${amt(v.totals.cgst)}</td></tr><tr><td>SGST</td><td class=r>${amt(v.totals.sgst)}</td></tr>` : ""}
      ${v.totals.igst ? `<tr><td>IGST</td><td class=r>${amt(v.totals.igst)}</td></tr>` : ""}
      <tr><th>Total (₹)</th><th class=r>${amt(v.totals.total)}</th></tr></table>`
    : "";
  const entries = `<table><thead><tr><th>Ledger</th><th class=r>Debit (₹)</th><th class=r>Credit (₹)</th></tr></thead><tbody>
    ${v.entries.map((e) => `<tr><td>${esc(e.ledger_name)}</td><td class=r>${e.debit ? amt(e.debit) : ""}</td><td class=r>${e.credit ? amt(e.credit) : ""}</td></tr>`).join("")}
    <tr><th>Total</th><th class=r>${amt(v.amount)}</th><th class=r>${amt(v.amount)}</th></tr></tbody></table>`;
  const html = `<html><head><title>${esc(v.voucher_no)}</title><style>
    body{font-family:Arial,sans-serif;padding:32px;color:#0f172a;font-size:13px}h1{margin:0;font-size:22px}
    table{width:100%;border-collapse:collapse;margin-top:16px}th,td{border:1px solid #cbd5e1;padding:6px 8px;text-align:left}
    th{background:#f1f5f9}.r{text-align:right}.sum{width:300px;margin-left:auto}.hd{display:flex;justify-content:space-between;border-bottom:2px solid #1e3a8a;padding-bottom:12px}
    .muted{color:#475569}</style></head><body>
    <div class=hd><div><h1>${esc(s.company_name || "")}</h1><div class=muted>${esc(s.address || "")}</div>
    ${s.gstin ? `<div>GSTIN: ${esc(s.gstin)}</div>` : ""}</div>
    <div style="text-align:right"><h1>${esc(VT[v.voucher_type]?.label)} ${v.items?.length && v.voucher_type === "sales" ? "Invoice" : "Voucher"}</h1>
    <div>No: <b>${esc(v.voucher_no)}</b></div><div>Date: ${dmy(v.date)}</div>${v.reference_no ? `<div>Ref: ${esc(v.reference_no)}</div>` : ""}
    ${v.status === "cancelled" ? `<div style="color:#dc2626;font-weight:bold">CANCELLED</div>` : ""}</div></div>
    <p><b>Party:</b> ${esc(v.party_name)}</p>${items}<h3 style="margin-top:24px">Accounting Entries</h3>${entries}
    ${v.narration ? `<p><b>Narration:</b> ${esc(v.narration)}</p>` : ""}
    <p style="margin-top:48px;text-align:right">Authorised Signatory</p></body></html>`;
  const w = window.open("", "_blank");
  if (!w) return;
  w.document.write(html);
  w.document.close();
  w.focus();
  setTimeout(() => w.print(), 300);
}
