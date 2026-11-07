import { round2 } from "@/lib/format";

export const SIMPLE = {
  payment: { a: "Paid from (Cash / Bank)", b: "Paid to (Account)", aSide: "credit", aGroups: ["cash", "bank"], bGroups: null },
  receipt: { a: "Received into (Cash / Bank)", b: "Received from (Account)", aSide: "debit", aGroups: ["cash", "bank"], bGroups: null },
  contra: { a: "From account (Cr)", b: "To account (Dr)", aSide: "credit", aGroups: ["cash", "bank"], bGroups: ["cash", "bank"] },
};

export const PARTY_GROUPS = ["sundry_debtors", "sundry_creditors", "cash", "bank"];

export const emptyItem = (rate = 18) => ({ description: "", hsn: "", qty: 1, rate: "", gst_rate: rate });
export const emptyLine = () => ({ ledger_id: "", debit: "", credit: "" });

export function computeItems(items, gstType) {
  let taxable = 0, cgst = 0, sgst = 0, igst = 0;
  const lines = items.map((it) => {
    const amount = round2((Number(it.qty) || 0) * (Number(it.rate) || 0));
    const tax = gstType === "none" ? 0 : round2((amount * (Number(it.gst_rate) || 0)) / 100);
    let c = 0, s = 0, i = 0;
    if (gstType === "intra") { c = round2(tax / 2); s = round2(tax - c); } else if (gstType === "inter") i = tax;
    taxable += amount; cgst += c; sgst += s; igst += i;
    return { amount, tax, total: round2(amount + tax) };
  });
  taxable = round2(taxable); cgst = round2(cgst); sgst = round2(sgst); igst = round2(igst);
  return { lines, taxable, cgst, sgst, igst, total: round2(taxable + cgst + sgst + igst) };
}

export function linesTotals(lines) {
  const dr = round2(lines.reduce((s, l) => s + (Number(l.debit) || 0), 0));
  const cr = round2(lines.reduce((s, l) => s + (Number(l.credit) || 0), 0));
  return { dr, cr, diff: round2(dr - cr) };
}

export function fromVoucher(v) {
  const base = { date: v.date, narration: v.narration || "", reference_no: v.reference_no || "" };
  if (v.items?.length) {
    return { ...base, party: v.party_ledger_id, account: v.account_ledger_id, gstType: v.gst_type,
      items: v.items.map((i) => ({ description: i.description, hsn: i.hsn, qty: i.qty, rate: i.rate, gst_rate: i.gst_rate })) };
  }
  const cfg = SIMPLE[v.voucher_type];
  if (cfg && v.entries.length === 2) {
    const a = v.entries.find((e) => e[cfg.aSide] > 0);
    const b = v.entries.find((e) => e !== a);
    if (a && b) return { ...base, simple: { a: a.ledger_id, b: b.ledger_id, amount: a[cfg.aSide] }, advanced: false };
  }
  return { ...base, advanced: true, lines: v.entries.map((e) => ({ ledger_id: e.ledger_id, debit: e.debit || "", credit: e.credit || "" })) };
}
