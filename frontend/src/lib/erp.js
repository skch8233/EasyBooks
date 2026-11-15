import { api } from "@/lib/api";

export const r2 = (n) => Math.round((Number(n || 0) + Number.EPSILON) * 100) / 100;
export const BLANK_LINE = { description: "", hsn: "", unit: "", qty: 1, rate: 0, discount: 0, gst_rate: 18 };
export const TEMPLATES = [["classic", "Classic Professional"], ["modern", "Modern Corporate"], ["detailed", "Detailed Project"]];
export const INVOICE_TEMPLATES = [["gst_goods", "GST Goods Format"], ["gst_service", "GST Service Format"], ...TEMPLATES];
export const PROJECT_STATUSES = ["Planning", "Running", "On Hold", "Completed", "Cancelled"];

export function computeLines(lines, gstType) {
  const t = { gross: 0, discount: 0, taxable: 0, cgst: 0, sgst: 0, igst: 0 };
  const items = lines.map((ln) => {
    const qty = Number(ln.qty || 0), rate = Number(ln.rate || 0), g = Number(ln.gst_rate || 0);
    const gross = r2(qty * rate), netRate = r2((rate * (100 - Number(ln.discount || 0))) / 100), amount = r2(qty * netRate);
    const tax = gstType === "none" ? 0 : r2((amount * g) / 100);
    const c = gstType === "intra" ? r2(tax / 2) : 0, s = gstType === "intra" ? r2(tax - c) : 0, i = gstType === "inter" ? tax : 0;
    t.gross += gross; t.discount += gross - amount; t.taxable += amount; t.cgst += c; t.sgst += s; t.igst += i;
    return { ...ln, net_rate: netRate, amount, cgst: c, sgst: s, igst: i, total: r2(amount + tax) };
  });
  Object.keys(t).forEach((k) => { t[k] = r2(t[k]); });
  t.total = r2(t.taxable + t.cgst + t.sgst + t.igst);
  return { items, totals: t };
}

export function invoiceTotals(totals, f) {
  const retention = r2((totals.total * Number(f.retention_pct || 0)) / 100);
  const adv = Number(f.advance_adjust || 0), ded = Number(f.deductions || 0);
  return { ...totals, retention, advance_adjust: adv, deductions: ded, net_payable: r2(totals.total - retention - adv - ded) };
}

export function guessGst(companyState, clientState) {
  const a = (companyState || "").trim().toLowerCase(), b = (clientState || "").trim().toLowerCase();
  return a && b && a !== b ? "inter" : "intra";
}

export function printNode(node, title) {
  const w = window.open("", "_blank");
  if (!w) return;
  const styles = [...document.querySelectorAll("style, link[rel=stylesheet]")].map((s) => s.outerHTML).join("");
  w.document.write(`<html><head><title>${title}</title>${styles}<style>@page{size:A4;margin:10mm}body{background:#fff;-webkit-print-color-adjust:exact;print-color-adjust:exact}</style></head><body>${node.outerHTML}</body></html>`);
  w.document.close();
  setTimeout(() => { w.focus(); w.print(); }, 600);
}

export const loadLogo = async (s) => {
  if (!s?.logo_path) return null;
  try {
    const r = await api.get("/settings/logo", { responseType: "blob" });
    return await new Promise((res) => { const fr = new FileReader(); fr.onload = () => res(fr.result); fr.readAsDataURL(r.data); });
  } catch { return null; }
};

export const loadSignature = async (es) => {
  if (!es?.signature_path) return null;
  try {
    const r = await api.get("/erp/settings/signature", { responseType: "blob" });
    return await new Promise((res) => { const fr = new FileReader(); fr.onload = () => res(fr.result); fr.readAsDataURL(r.data); });
  } catch { return null; }
};

export const TONE = {
  draft: "bg-slate-100 text-slate-700", sent: "bg-sky-100 text-sky-800", accepted: "bg-emerald-100 text-emerald-800", converted: "bg-indigo-100 text-indigo-800",
  rejected: "bg-rose-100 text-rose-800", expired: "bg-amber-100 text-amber-800", cancelled: "bg-red-100 text-red-700", finalized: "bg-emerald-100 text-emerald-800",
  paid: "bg-emerald-100 text-emerald-800", partial: "bg-amber-100 text-amber-800", unpaid: "bg-slate-100 text-slate-700", overdue: "bg-red-100 text-red-700",
  Planning: "bg-slate-100 text-slate-700", Running: "bg-sky-100 text-sky-800", "On Hold": "bg-amber-100 text-amber-800", Completed: "bg-emerald-100 text-emerald-800", Cancelled: "bg-red-100 text-red-700",
};
