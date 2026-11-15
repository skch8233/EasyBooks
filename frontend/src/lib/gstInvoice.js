import { amt, dmy, STATES } from "@/lib/format";
import { inWords } from "@/lib/invoice";

const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const money = (n) => `₹ ${amt(n)}`;
export const stateLabel = (st) => {
  if (!st) return "";
  const hit = STATES.find((x) => x === st || x.slice(3).toLowerCase() === String(st).toLowerCase());
  return hit ? `${hit.slice(3)} (${hit.slice(0, 2)})` : st;
};
const words = (n) => `Rupees ${inWords(n).replace(/ Rupees/, "")}`;

const CSS = `.gi{font-family:Arial,Helvetica,sans-serif;color:#1f2937;font-size:11.5px;line-height:1.45;background:#fff;padding:28px 34px;max-width:820px;margin:0 auto}
.gi *{box-sizing:border-box}.gi table{width:100%;border-collapse:collapse}.gi .r{text-align:right}.gi .c{text-align:center}.gi b{font-weight:700}
.gi .box{border:1px solid #d5dbe5}.gi .sec{color:var(--ac);font-weight:700;font-size:10.5px;letter-spacing:.06em;text-transform:uppercase;padding-bottom:5px;border-bottom:1px solid #d5dbe5;margin-bottom:8px}
.gi .cell{padding:10px 12px}.gi .grid2{display:grid;grid-template-columns:1fr 1fr}.gi .grid2>div+div{border-left:1px solid #d5dbe5}
.gi .items th{background:var(--ac);color:#fff;font-size:10.5px;padding:8px 6px;text-align:left;font-weight:700}.gi .items td{padding:8px 6px;border-bottom:1px solid #e5e7eb;vertical-align:top;border-right:1px solid #eef0f4}
.gi .items tfoot td{background:#eef2f8;font-weight:700;border-bottom:1px solid #d5dbe5}.gi .words{background:#f3f5f9;padding:9px 12px;margin:14px 0;border:1px solid #e1e6ee}
.gi .sum td{padding:6px 0;border-bottom:1px solid #e5e7eb}.gi .grand td{font-weight:800;color:var(--ac);font-size:13px;border-top:2px solid var(--ac);border-bottom:none;padding-top:8px}
.gi .foot{display:flex;justify-content:space-between;color:#6b7280;font-size:9.5px;margin-top:26px}.gi .cxl{display:inline-block;background:#dc2626;color:#fff;font-weight:700;padding:2px 8px;border-radius:3px;margin-top:4px}
.gi .muted{color:#6b7280}.gi .sig{height:46px;object-fit:contain}.gi .pb{page-break-inside:avoid}
@media print{.gi{padding:0;max-width:none}}`;

const party = (p, label, more = "") => `<div class=cell><div class=sec>${label}</div><div style="font-weight:700;font-size:12.5px">${esc(p.name)}</div>
  ${p.address ? `<div>${esc(p.address)}</div>` : ""}${p.gstin ? `<div><b>GSTIN:</b> ${esc(p.gstin)}</div>` : ""}${p.state ? `<div><b>State Name &amp; Code:</b> ${esc(stateLabel(p.state))}</div>` : ""}${more}</div>`;

const rateBreak = (items, key) => {
  const by = {};
  items.forEach((i) => { const r = Number(i.gst_rate || 0); if (r) by[r] = (by[r] || 0) + i.taxable; });
  const k = Object.keys(by);
  return k.map((r) => `${key === "igst" ? r : Number(r) / 2}% on ₹${amt(by[r]).replace(".00", "")}`).join(" + ");
};

const extraRows = (d) => (d.extra || []).map(([l, v]) => `<tr><td>${esc(l)}</td><td class=r>${v < 0 ? "- " : ""}${money(Math.abs(v))}</td></tr>`).join("");

function goods(d) {
  const t = d.totals, intra = d.gst_type !== "inter";
  const c = d.company, totQty = d.items.reduce((s, i) => s + Number(i.qty || 0), 0);
  const rows = d.items.map((i, n) => `<tr><td class=c>${n + 1}</td><td>${esc(i.description)}</td><td class=c>${esc(i.hsn)}</td><td class=c>${Number(i.qty)}</td><td class=c>${esc((i.unit || "").toUpperCase())}</td>
    <td class=r>${amt(i.rate)}</td><td class=r>${amt(i.discount)}</td><td class=r>${amt(i.taxable)}</td><td class=c>${d.gst_type === "none" ? 0 : Number(i.gst_rate)}%</td><td class=r>${amt(i.total)}</td></tr>`).join("");
  const cons = d.consignee || d.buyer;
  return `<div style="--ac:#1d4e89">
  <div style="display:flex;justify-content:space-between;align-items:flex-end;border-bottom:2px solid #1d4e89;padding-bottom:8px">
    <div style="display:flex;gap:12px;align-items:center">${d.logo ? `<img src="${d.logo}" style="height:46px;max-width:120px;object-fit:contain"/>` : ""}<div><div style="font-size:26px;font-weight:800;color:#1d4e89;letter-spacing:.01em">TAX INVOICE</div>
    <div class=muted>Issued under Section 31 of CGST Act, 2017 &amp; Rule 46 of CGST Rules</div></div></div>
    <div class=r><div style="border:1px solid #c9d2df;background:#f3f5f9;padding:5px 12px;font-weight:700">${esc(d.copy || "Original for Recipient")}</div>${d.status === "cancelled" ? "<div class=cxl>CANCELLED</div>" : ""}</div>
  </div>
  <div class="box" style="margin-top:12px"><div class=grid2>
    <div class=cell><div class=sec>Supplier Details</div><div style="font-weight:700;font-size:12.5px">${esc(c.company_name)}</div><div>${esc(c.address)}</div>
      ${c.gstin ? `<div><b>GSTIN:</b> ${esc(c.gstin)}</div>` : ""}${c.state ? `<div><b>State Name &amp; Code:</b> ${esc(stateLabel(c.state))}</div>` : ""}
      ${c.phone || c.email ? `<div>${c.phone ? `<b>Phone:</b> ${esc(c.phone)}` : ""}${c.phone && c.email ? "  |  " : ""}${c.email ? `<b>Email:</b> ${esc(c.email)}` : ""}</div>` : ""}</div>
    <div class=cell><div class=sec>Invoice Particulars</div><div><b>Invoice No.:</b> ${esc(d.number || "DRAFT")}</div><div><b>Invoice Date:</b> ${dmy(d.date).replace(/-/g, "/")}</div>
      <div><b>Reverse Charge (RCM):</b> ${d.reverse_charge ? "Yes" : "No"}</div><div><b>Place of Supply:</b> ${esc(stateLabel(d.place_of_supply))}</div>
      ${d.transport_mode || d.eway_bill_no ? `<div><b>Transport Mode:</b> ${esc(d.transport_mode || "-")}${d.eway_bill_no ? ` (E-Way Bill: ${esc(d.eway_bill_no)})` : ""}</div>` : ""}
      ${d.vehicle_no ? `<div><b>Vehicle / LR No.:</b> ${esc(d.vehicle_no)}</div>` : ""}${d.due_date ? `<div><b>Due Date:</b> ${dmy(d.due_date).replace(/-/g, "/")}</div>` : ""}
      ${d.project ? `<div><b>Project:</b> ${esc(d.project)}</div>` : ""}${d.po_reference ? `<div><b>PO / WO Ref.:</b> ${esc(d.po_reference)}</div>` : ""}</div>
  </div><div class=grid2 style="border-top:1px solid #d5dbe5">${party(d.buyer, "Details of Receiver (Billed To)")}${party(cons, "Details of Consignee (Shipped To)")}</div></div>
  <table class=items style="margin-top:12px;border:1px solid #d5dbe5"><thead><tr><th class=c>S.No</th><th>Description of Goods / Services</th><th class=c>HSN/SAC</th><th class=c>Qty</th><th class=c>UQC</th><th class=r>Rate (₹)</th><th class=r>Disc. (₹)</th><th class=r>Taxable (₹)</th><th class=c>GST</th><th class=r>Total (₹)</th></tr></thead>
  <tbody>${rows}</tbody><tfoot><tr><td colspan=3>Total</td><td class=c>${totQty}</td><td></td><td></td><td class=r>${amt(t.discount)}</td><td class=r>${amt(t.taxable)}</td><td></td><td class=r>${amt(t.total)}</td></tr></tfoot></table>
  <div class=words><b>Total Invoice Value (in Words):</b> ${words(d.net)}.</div>
  <div class="box pb" style="display:grid;grid-template-columns:1.25fr 1fr">
    <div class=cell><div class=sec>Bank Details</div>${c.bank_name ? `<div><b>Bank Name:</b> ${esc(c.bank_name)}</div>` : ""}<div><b>Account Name:</b> ${esc(c.company_name)}</div>
      ${c.bank_account ? `<div><b>Account No.:</b> ${esc(c.bank_account)}</div>` : ""}${c.bank_ifsc ? `<div><b>IFSC Code:</b> ${esc(c.bank_ifsc)}${c.bank_branch ? `  |  <b>Branch:</b> ${esc(c.bank_branch)}` : ""}</div>` : ""}
      ${c.upi_id ? `<div><b>UPI:</b> ${esc(c.upi_id)}</div>` : ""}${d.qr ? `<div style="margin-top:6px;display:flex;gap:8px;align-items:center"><img src="${d.qr}" style="width:84px"/><span class=muted>Scan to pay via UPI</span></div>` : ""}
      <div class=sec style="margin-top:12px">Terms &amp; Conditions</div><div style="white-space:pre-line">${esc(d.terms || "1. Goods once sold will not be taken back or exchanged.\n2. Interest @ 18% p.a. will be charged on overdue payments.\n3. Subject to local jurisdiction.")}</div></div>
    <div class=cell style="border-left:1px solid #d5dbe5"><div class=sec>Tax &amp; Amount Summary</div><table class=sum>
      <tr><td>Total Taxable Value</td><td class=r>${money(t.taxable)}</td></tr>
      <tr><td>Add: CGST${intra && t.cgst ? ` (${rateBreak(d.items, "cgst")})` : " (0%)"}</td><td class=r>${money(t.cgst)}</td></tr>
      <tr><td>Add: SGST${intra && t.sgst ? ` (${rateBreak(d.items, "sgst")})` : " (0%)"}</td><td class=r>${money(t.sgst)}</td></tr>
      <tr><td>Add: IGST${!intra && t.igst ? ` (${rateBreak(d.items, "igst")})` : " (0%)"}</td><td class=r>${money(t.igst)}</td></tr>
      <tr><td>Round Off (+/-)</td><td class=r>${money(d.round_off || 0)}</td></tr>
      <tr class=grand><td>Grand Total</td><td class=r>${money(t.total)}</td></tr>${extraRows(d)}
      ${d.extra?.length ? `<tr class=grand><td>Net Payable</td><td class=r>${money(d.net)}</td></tr>` : ""}</table></div>
  </div>
  <div class="box pb" style="margin-top:14px;display:grid;grid-template-columns:1.25fr 1fr"><div class=cell><b>Declaration:</b><br/>We declare that this invoice shows the actual price of the goods and services described and that all particulars are true and correct.</div>
    <div class="cell r" style="border-left:1px solid #d5dbe5"><b>For ${esc(c.company_name)}</b><div style="height:52px;display:flex;justify-content:flex-end;align-items:center">${d.signature ? `<img class=sig src="${d.signature}"/>` : ""}</div>${esc(d.signatory || "Authorized Signatory")}</div></div>
  <div class=foot><span>Computer Generated Tax Invoice</span><span>${esc(d.number || "")}</span></div></div>`;
}

function service(d) {
  const t = d.totals, intra = d.gst_type !== "inter", c = d.company;
  const rows = d.items.map((i, n) => { const [head, ...rest] = String(i.description || "").split("\n");
    return `<tr><td class=c>${n + 1}</td><td><div style="font-weight:700">${esc(head)}</div>${rest.length ? `<div class=muted style="margin-top:3px">${esc(rest.join(" "))}</div>` : ""}</td><td>${esc(i.hsn)}</td>
      <td class=r>${amt(i.taxable)}</td><td class=c>${d.gst_type === "none" ? 0 : Number(i.gst_rate)}%</td><td class=r>${amt(i.total)}</td></tr>`; }).join("");
  const sac = {};
  d.items.forEach((i) => { const k = `${i.hsn || "-"}|${i.gst_rate}`; sac[k] = sac[k] || { hsn: i.hsn || "-", rate: Number(i.gst_rate || 0), taxable: 0, tax: 0 }; sac[k].taxable += i.taxable; sac[k].tax += i.total - i.taxable; });
  const sacRows = Object.values(sac).map((s) => intra
    ? `<tr><td>${esc(s.hsn)}</td><td class=r>${amt(s.taxable)}</td><td class=c>${s.rate / 2}%</td><td class=r>${amt(s.tax / 2)}</td><td class=c>${s.rate / 2}%</td><td class=r>${amt(s.tax / 2)}</td></tr>`
    : `<tr><td>${esc(s.hsn)}</td><td class=r>${amt(s.taxable)}</td><td class=c>${s.rate}%</td><td class=r>${amt(s.tax)}</td></tr>`).join("");
  const rate = d.items[0] ? Number(d.items[0].gst_rate || 0) : 0;
  const one = d.items.every((i) => Number(i.gst_rate) === rate);
  return `<div style="--ac:#2f2a7a">
  <div style="border-top:3px solid #2f2a7a;padding-top:10px;display:flex;justify-content:space-between;gap:18px">
    <div style="display:flex;gap:12px">${d.logo ? `<img src="${d.logo}" style="height:52px;max-width:110px;object-fit:contain"/>` : ""}<div><div style="font-family:Georgia,'Times New Roman',serif;font-size:21px;font-weight:700;color:#2f2a7a;text-transform:uppercase">${esc(c.company_name)}</div>
      <div>${esc(c.address)}</div><div>${[c.gstin && `<b>GSTIN:</b> ${esc(c.gstin)}`, c.state && `<b>State:</b> ${esc(stateLabel(c.state))}`, c.pan && `<b>PAN:</b> ${esc(c.pan)}`].filter(Boolean).join("  |  ")}</div>
      <div>${[c.email && `<b>Email:</b> ${esc(c.email)}`, c.phone && `<b>Phone:</b> ${esc(c.phone)}`].filter(Boolean).join("  |  ")}</div></div></div>
    <div class=r style="min-width:150px"><div style="font-family:Georgia,'Times New Roman',serif;font-size:22px;font-weight:700;color:#2f2a7a;line-height:1.05">TAX<br/>INVOICE</div>
      <div class=muted style="margin-top:4px">${esc(d.copy || "Original for Recipient")}</div><div><b>GST on Reverse Charge:</b> ${d.reverse_charge ? "Yes" : "No"}</div>${d.status === "cancelled" ? "<div class=cxl>CANCELLED</div>" : ""}</div>
  </div>
  <div class="box grid2" style="margin-top:16px">${party(d.buyer, "Billed To (Service Recipient)", `<div><b>Place of Supply:</b> ${esc(stateLabel(d.place_of_supply))}</div>`)}
    <div class=cell><div class=sec>Invoice &amp; Engagement Details</div><div><b>Invoice No.:</b> ${esc(d.number || "DRAFT")}</div><div><b>Invoice Date:</b> ${dmy(d.date).replace(/-/g, "/")}</div>
      ${d.due_date ? `<div><b>Due Date:</b> ${dmy(d.due_date).replace(/-/g, "/")}</div>` : ""}${d.contract_ref ? `<div><b>Contract / SOW Ref.:</b> ${esc(d.contract_ref)}</div>` : ""}
      ${d.billing_period ? `<div><b>Billing Period:</b> ${esc(d.billing_period)}</div>` : ""}${d.project ? `<div><b>Project:</b> ${esc(d.project)}</div>` : ""}${d.po_reference ? `<div><b>PO / WO Ref.:</b> ${esc(d.po_reference)}</div>` : ""}</div></div>
  <table class=items style="margin-top:16px;border:1px solid #d5dbe5"><thead><tr><th class=c style="width:42px">S.No</th><th>Description of Services</th><th style="width:70px">SAC Code</th><th class=r style="width:120px">Taxable Value (₹)</th><th class=c style="width:60px">GST %</th><th class=r style="width:110px">Total (₹)</th></tr></thead>
  <tbody>${rows}</tbody><tfoot><tr><td colspan=3>Total Service Value</td><td class=r>${amt(t.taxable)}</td><td></td><td class=r>${amt(t.total)}</td></tr></tfoot></table>
  <div class=words style="border-left:4px solid #2f2a7a"><b>Total Invoice Value (in Words):</b> ${words(d.net)}.</div>
  <div class="box pb" style="display:grid;grid-template-columns:1.3fr 1fr;margin-top:14px">
    <div class=cell><div class=sec>SAC-wise Tax Summary</div><table class=items style="border:1px solid #d5dbe5"><thead><tr style="--ac:#eef2f8"><th style="color:#1f2937">SAC</th><th class=r style="color:#1f2937">Taxable (₹)</th>
      ${intra ? `<th class=c style="color:#1f2937">CGST %</th><th class=r style="color:#1f2937">CGST (₹)</th><th class=c style="color:#1f2937">SGST %</th><th class=r style="color:#1f2937">SGST (₹)</th>` : `<th class=c style="color:#1f2937">IGST %</th><th class=r style="color:#1f2937">IGST Amt (₹)</th>`}</tr></thead><tbody>${sacRows}</tbody></table>
      <div class=sec style="margin-top:12px">Bank &amp; Remittance Details</div><div><b>Account Name:</b> ${esc(c.company_name)}</div>${c.bank_name ? `<div><b>Bank &amp; Branch:</b> ${esc(c.bank_name)}${c.bank_branch ? `, ${esc(c.bank_branch)}` : ""}</div>` : ""}
      ${c.bank_account ? `<div><b>Account No.:</b> ${esc(c.bank_account)}${c.bank_ifsc ? `  |  <b>IFSC:</b> ${esc(c.bank_ifsc)}` : ""}</div>` : ""}${c.upi_id ? `<div><b>UPI:</b> ${esc(c.upi_id)}</div>` : ""}${d.qr ? `<div style="margin-top:6px;display:flex;gap:8px;align-items:center"><img src="${d.qr}" style="width:84px"/><span class=muted>Scan to pay via UPI</span></div>` : ""}</div>
    <div class=cell style="border-left:1px solid #d5dbe5"><div class=sec>Tax &amp; Payment Summary</div><table class=sum>
      <tr><td>Total Taxable Value</td><td class=r>${money(t.taxable)}</td></tr>
      ${intra ? `<tr><td>Add: CGST${one && rate ? ` @ ${rate / 2}%` : ""}</td><td class=r>${money(t.cgst)}</td></tr><tr><td>Add: SGST${one && rate ? ` @ ${rate / 2}%` : ""}</td><td class=r>${money(t.sgst)}</td></tr><tr><td>Add: IGST (0%)</td><td class=r>${money(0)}</td></tr>`
        : `<tr><td>Add: IGST${one && rate ? ` @ ${rate}%` : ""}</td><td class=r>${money(t.igst)}</td></tr><tr><td>Add: CGST (0%)</td><td class=r>${money(0)}</td></tr><tr><td>Add: SGST (0%)</td><td class=r>${money(0)}</td></tr>`}
      <tr><td>Round Off (+/-)</td><td class=r>${money(d.round_off || 0)}</td></tr><tr class=grand><td>Total Invoice Amount</td><td class=r>${money(t.total)}</td></tr>${extraRows(d)}
      ${d.extra?.length ? `<tr class=grand><td>Net Payable</td><td class=r>${money(d.net)}</td></tr>` : ""}</table>
      <div class=muted style="font-style:italic;margin-top:8px">Note: Please quote Invoice No. <b>${esc(d.number || "")}</b> in all NEFT/RTGS payment advisories.</div></div>
  </div>
  <div class="box pb" style="margin-top:14px;display:grid;grid-template-columns:1.3fr 1fr"><div class=cell><b>Terms &amp; Declaration:</b><div style="white-space:pre-line">${esc(d.terms || `1. Payment is due by the due date mentioned above.\n2. Applicable TDS may be deducted on the taxable value (₹${amt(t.taxable)}) and TDS certificate furnished.`)}</div><div style="margin-top:6px"><b>Declaration:</b> We declare that this invoice shows the actual price of the services described and that all particulars are true and correct.</div></div>
    <div class="cell r" style="border-left:1px solid #d5dbe5"><b style="color:#2f2a7a">For ${esc(c.company_name)}</b><div style="height:52px;display:flex;justify-content:flex-end;align-items:center">${d.signature ? `<img class=sig src="${d.signature}"/>` : ""}</div>${esc(d.signatory || "Authorized Signatory")}</div></div>
  <div class=foot><span>Computer Generated Tax Invoice — Valid Without Physical Signature if Digitally Signed</span><span>${esc(d.number || "")}</span></div></div>`;
}

export const renderGstBody = (d) => `<style>${CSS}</style><div class=gi data-testid="gst-invoice-${d.fmt}">${d.fmt === "service" ? service(d) : goods(d)}</div>`;
export const renderGstPage = (d) => `<html><head><meta name="viewport" content="width=device-width,initial-scale=1"/><title>Invoice ${esc(d.number)}</title><style>@page{size:A4;margin:12mm}body{margin:0}</style></head><body>${renderGstBody(d)}</body></html>`;

const meta = (m = {}) => ({ reverse_charge: m.reverse_charge === "yes" || m.reverse_charge === true, transport_mode: m.transport_mode, eway_bill_no: m.eway_bill_no, vehicle_no: m.vehicle_no,
  contract_ref: m.contract_ref, billing_period: m.billing_period, consignee: m.ship_name ? { name: m.ship_name, address: m.ship_address, gstin: m.ship_gstin, state: m.ship_state } : null,
  place_of_supply: m.place_of_supply });

export function fromVoucher(v, s, p = {}, extra = {}) {
  const m = meta(v.gst_meta);
  const items = (v.items || []).map((i) => ({ ...i, unit: i.unit || "", discount: 0, taxable: i.amount, total: i.total }));
  const t = v.totals || { taxable: v.amount, cgst: 0, sgst: 0, igst: 0, total: v.amount };
  return { fmt: v.invoice_format || "goods", company: s || {}, number: v.voucher_no, date: v.date, status: v.status, gst_type: v.gst_type,
    buyer: { name: v.party_name, address: p.address, gstin: p.gstin, state: p.state }, ...m, place_of_supply: m.place_of_supply || p.state || s?.state,
    items, totals: { ...t, discount: 0 }, net: t.total, terms: s?.invoice_terms, project: v.project_code ? `${v.project_code} · ${v.project_name}` : "", po_reference: v.reference_no, ...extra };
}

export function fromErp(doc, company, extra = {}) {
  const m = meta(doc.gst_meta);
  const T = doc.totals || {};
  const cl = doc.client || {};
  const items = (doc.items || []).map((i) => ({ ...i, discount: Math.max(Number(i.qty || 0) * Number(i.rate || 0) - Number(i.amount || 0), 0), taxable: i.amount, total: i.total }));
  const ex = [T.retention > 0 && [`Less: Retention (${doc.retention_pct}%)`, -T.retention], T.advance_adjust > 0 && ["Less: Advance adjusted", -T.advance_adjust],
    T.deductions > 0 && [`Less: Deductions${doc.deduction_note ? ` (${doc.deduction_note})` : ""}`, -T.deductions]].filter(Boolean);
  return { fmt: doc.template === "gst_service" ? "service" : "goods", company, number: doc.number, date: doc.date, due_date: doc.due_date, status: doc.status, gst_type: doc.gst_type,
    buyer: { name: cl.company_name, address: cl.address, gstin: cl.gstin, state: cl.state }, ...m, place_of_supply: m.place_of_supply || cl.state || company?.state,
    items, totals: T, extra: ex, net: T.net_payable ?? T.total, terms: doc.terms || company?.invoice_terms, project: doc.project_code ? `${doc.project_code} · ${doc.project_name}` : "",
    po_reference: doc.po_reference, ...extra };
}
