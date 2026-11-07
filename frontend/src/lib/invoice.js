import QRCode from "qrcode";
import { api } from "@/lib/api";
import { amt, dmy } from "@/lib/format";

const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"];
const TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"];
const two = (n) => (n < 20 ? ONES[n] : `${TENS[Math.floor(n / 10)]} ${ONES[n % 10]}`.trim());
const three = (n) => [n >= 100 ? `${ONES[Math.floor(n / 100)]} Hundred` : "", two(n % 100)].filter(Boolean).join(" ");

export function inWords(num) {
  const n = Math.floor(num), paise = Math.round((num - n) * 100);
  const parts = [[10000000, "Crore"], [100000, "Lakh"], [1000, "Thousand"]];
  let rest = n, out = [];
  parts.forEach(([d, l]) => { const q = Math.floor(rest / d); if (q) { out.push(`${n >= d * 100 && l === "Crore" ? inWords(q).replace(" Rupees Only", "") : two(q) || three(q)} ${l}`); rest %= d; } });
  if (rest) out.push(three(rest));
  return `${out.join(" ") || "Zero"} Rupees${paise ? ` and ${two(paise)} Paise` : ""} Only`;
}

const blobToData = (b) => new Promise((res) => { const r = new FileReader(); r.onload = () => res(r.result); r.readAsDataURL(b); });

async function assets(v, s) {
  const [ledgers, logo] = await Promise.all([
    api.get("/ledgers", { params: { include_inactive: true } }).then((r) => r.data).catch(() => []),
    s.logo_path ? api.get("/settings/logo", { responseType: "blob" }).then((r) => blobToData(r.data)).catch(() => null) : null,
  ]);
  const total = v.totals?.total || v.amount;
  const qr = s.upi_id
    ? await QRCode.toDataURL(`upi://pay?pa=${encodeURIComponent(s.upi_id)}&pn=${encodeURIComponent(s.company_name || "")}&am=${total.toFixed(2)}&cu=INR&tn=${encodeURIComponent(v.voucher_no)}`, { width: 180, margin: 1 })
    : null;
  return { party: ledgers.find((l) => l.id === v.party_ledger_id) || {}, logo, qr, total };
}

const CSS = `body{font-family:Arial,sans-serif;padding:28px;color:#0f172a;font-size:12px}table{width:100%;border-collapse:collapse}
th,td{border:1px solid #cbd5e1;padding:6px 8px;text-align:left;vertical-align:top}th{background:#1e3a8a;color:#fff;font-size:11px}
.r{text-align:right}.hd{display:flex;gap:16px;align-items:center;border-bottom:3px solid #1e3a8a;padding-bottom:12px}
.hd img{max-height:70px;max-width:160px;object-fit:contain}.muted{color:#475569}.box{border:1px solid #cbd5e1;padding:10px;border-radius:6px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:14px 0}.tot td{border:none;padding:3px 8px}.big{font-size:15px;font-weight:bold}
.foot{display:grid;grid-template-columns:1fr 200px;gap:16px;margin-top:16px}.qr{text-align:center}.qr img{width:150px}`;

export async function printInvoice(v, s = {}) {
  const w = window.open("", "_blank");
  if (!w) return;
  w.document.write("<p style='font-family:Arial;padding:24px'>Preparing invoice...</p>");
  const { party, logo, qr, total } = await assets(v, s);
  const t = v.totals || {};
  const intra = v.gst_type === "intra";
  const rows = v.items.map((i, n) => `<tr><td>${n + 1}</td><td>${esc(i.description)}</td><td>${esc(i.hsn)}</td><td class=r>${i.qty}</td><td class=r>${amt(i.rate)}</td>
    <td class=r>${amt(i.amount)}</td><td class=r>${i.gst_rate}%</td>${intra ? `<td class=r>${amt(i.cgst)}</td><td class=r>${amt(i.sgst)}</td>` : `<td class=r>${amt(i.igst)}</td>`}<td class=r>${amt(i.total)}</td></tr>`).join("");
  const html = `<html><head><title>Invoice ${esc(v.voucher_no)}</title><style>${CSS}</style></head><body>
    <div class=hd>${logo ? `<img src="${logo}" alt="logo"/>` : ""}<div style="flex:1"><div style="font-size:22px;font-weight:bold">${esc(s.company_name)}</div>
    <div class=muted>${esc(s.address)}</div><div class=muted>${s.phone ? `Ph: ${esc(s.phone)}` : ""} ${s.email ? `· ${esc(s.email)}` : ""}</div>
    ${s.gstin ? `<div><b>GSTIN: ${esc(s.gstin)}</b></div>` : ""}${s.state ? `<div class=muted>State: ${esc(s.state)}</div>` : ""}</div>
    <div style="text-align:right"><div style="font-size:20px;font-weight:bold;color:#1e3a8a">TAX INVOICE</div>
    <div>Invoice No: <b>${esc(v.voucher_no)}</b></div><div>Date: <b>${dmy(v.date)}</b></div>${v.reference_no ? `<div>Ref: ${esc(v.reference_no)}</div>` : ""}
    ${v.status === "cancelled" ? `<div style="color:#dc2626;font-weight:bold">CANCELLED</div>` : ""}</div></div>
    <div class=grid><div class=box><div class=muted>Bill To</div><div class=big>${esc(v.party_name)}</div><div>${esc(party.address)}</div>
    ${party.gstin ? `<div>GSTIN: <b>${esc(party.gstin)}</b></div>` : ""}${party.phone ? `<div>Ph: ${esc(party.phone)}</div>` : ""}</div>
    <div class=box><div class=muted>Place of Supply</div><div class=big>${esc(party.state || s.state || "-")}</div><div>${intra ? "Intra-state (CGST + SGST)" : v.gst_type === "inter" ? "Inter-state (IGST)" : "No GST"}</div></div></div>
    <table><thead><tr><th>#</th><th>Item</th><th>HSN/SAC</th><th class=r>Qty</th><th class=r>Rate</th><th class=r>Taxable</th><th class=r>GST</th>
    ${intra ? "<th class=r>CGST</th><th class=r>SGST</th>" : "<th class=r>IGST</th>"}<th class=r>Total</th></tr></thead><tbody>${rows}</tbody></table>
    <div class=foot><div><div class=box><b>Amount in words:</b> ${inWords(total)}</div>
    ${s.bank_name || s.bank_account ? `<div class=box style="margin-top:10px"><b>Bank details</b><br/>${esc(s.bank_name)}<br/>A/c: ${esc(s.bank_account)} · IFSC: ${esc(s.bank_ifsc)}</div>` : ""}
    ${s.invoice_terms ? `<div class=muted style="margin-top:10px"><b>Terms:</b> ${esc(s.invoice_terms)}</div>` : ""}
    ${v.narration ? `<div class=muted style="margin-top:6px">${esc(v.narration)}</div>` : ""}</div>
    <div><table class=tot><tr><td>Taxable value</td><td class=r>${amt(t.taxable)}</td></tr>
    ${t.cgst ? `<tr><td>CGST</td><td class=r>${amt(t.cgst)}</td></tr><tr><td>SGST</td><td class=r>${amt(t.sgst)}</td></tr>` : ""}${t.igst ? `<tr><td>IGST</td><td class=r>${amt(t.igst)}</td></tr>` : ""}
    <tr><td class=big>Total ₹</td><td class="r big">${amt(total)}</td></tr></table>
    ${qr ? `<div class=qr><img src="${qr}" alt="UPI QR"/><div><b>Scan to pay via UPI</b></div><div class=muted>${esc(s.upi_id)}</div></div>` : ""}</div></div>
    <div style="margin-top:40px;text-align:right">For <b>${esc(s.company_name)}</b><br/><br/><br/>Authorised Signatory</div></body></html>`;
  w.document.open();
  w.document.write(html);
  w.document.close();
  w.focus();
  setTimeout(() => w.print(), 500);
}
