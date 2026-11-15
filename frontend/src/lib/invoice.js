import QRCode from "qrcode";
import { api } from "@/lib/api";
import { renderGstPage, fromVoucher } from "@/lib/gstInvoice";

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

export const upiQr = (s, v) => {
  const total = v.totals?.total || v.amount;
  return s.upi_id
    ? QRCode.toDataURL(`upi://pay?pa=${encodeURIComponent(s.upi_id)}&pn=${encodeURIComponent(s.company_name || "")}&am=${total.toFixed(2)}&cu=INR&tn=${encodeURIComponent(v.voucher_no)}`, { width: 180, margin: 1 })
    : Promise.resolve(null);
};

async function assets(v, s) {
  const [ledgers, logo, qr] = await Promise.all([
    api.get("/ledgers", { params: { include_inactive: true } }).then((r) => r.data).catch(() => []),
    s.logo_path ? api.get("/settings/logo", { responseType: "blob" }).then((r) => blobToData(r.data)).catch(() => null) : null,
    upiQr(s, v),
  ]);
  return { party: ledgers.find((l) => l.id === v.party_ledger_id) || {}, logo, qr };
}

const CSS = `body{font-family:Arial,sans-serif;padding:28px;color:#0f172a;font-size:12px}table{width:100%;border-collapse:collapse}
th,td{border:1px solid #cbd5e1;padding:6px 8px;text-align:left;vertical-align:top}th{background:#1e3a8a;color:#fff;font-size:11px}
.r{text-align:right}.hd{display:flex;gap:16px;align-items:center;border-bottom:3px solid #1e3a8a;padding-bottom:12px}
.hd img{max-height:70px;max-width:160px;object-fit:contain}.muted{color:#475569}.box{border:1px solid #cbd5e1;padding:10px;border-radius:6px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:14px 0}.tot td{border:none;padding:3px 8px}.big{font-size:15px;font-weight:bold}
.foot{display:grid;grid-template-columns:1fr 200px;gap:16px;margin-top:16px}.qr{text-align:center}.qr img{width:150px}
.tw{overflow-x:auto}@media (max-width:640px){body{padding:12px;font-size:11px}.hd{flex-wrap:wrap}.grid,.foot{grid-template-columns:1fr}
th,td{padding:4px 5px}.tw table{min-width:620px}}`;

export const blobToDataUrl = (b) => blobToData(b);

export function renderInvoice({ v, s, party = {}, logo, qr }) {
  return renderGstPage(fromVoucher(v, s || {}, party, { logo, qr }));
}

export async function printInvoice(v, s = {}) {
  const w = window.open("", "_blank");
  if (!w) return;
  w.document.write("<p style='font-family:Arial;padding:24px'>Preparing invoice...</p>");
  const html = renderInvoice({ v, s, ...(await assets(v, s)) });
  w.document.open();
  w.document.write(html);
  w.document.close();
  w.focus();
  setTimeout(() => w.print(), 500);
}
