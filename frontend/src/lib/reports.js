import { api } from "@/lib/api";
import { dmy, drcr, VT } from "@/lib/format";

const N = (key, label) => ({ key, label, num: true });
const C = (key, label) => ({ key, label });

const statement = async (p) => {
  if (!p.ledger) return { sections: [], note: "Select a ledger to view its statement." };
  const { data: d } = await api.get("/reports/ledger-statement", { params: { ledger_id: p.ledger, from_date: p.from, to_date: p.to } });
  const rows = [
    { date: dmy(p.from), particulars: "Opening Balance", debit: d.opening > 0 ? d.opening : "", credit: d.opening < 0 ? -d.opening : "", balance: drcr(d.opening), _bold: true },
    ...d.rows.map((r) => ({ ...r, date: dmy(r.date), type: VT[r.voucher_type]?.label, debit: r.debit || "", credit: r.credit || "", balance: drcr(r.balance) })),
  ];
  return {
    note: `${d.ledger.name} · ${d.ledger.group_name}`,
    sections: [{
      columns: [C("date", "Date"), C("voucher_no", "Voucher No"), C("type", "Type"), C("particulars", "Particulars"), N("debit", "Debit"), N("credit", "Credit"), C("balance", "Balance")],
      rows, footer: { particulars: "Total / Closing", debit: d.total_debit, credit: d.total_credit, balance: drcr(d.closing) },
    }],
  };
};

const register = (voucher_type) => async (p) => {
  const { data } = await api.get("/reports/register", { params: { voucher_type, from_date: p.from, to_date: p.to } });
  return { sections: [{
    columns: [C("date", "Date"), C("voucher_no", "Voucher No"), C("party", "Party"), C("gstin", "GSTIN"), N("taxable", "Taxable"), N("cgst", "CGST"), N("sgst", "SGST"), N("igst", "IGST"), N("total", "Total")],
    rows: data.rows.map((r) => ({ ...r, date: dmy(r.date) })), footer: { party: "Total", ...data.totals },
  }] };
};

const outstanding = (kind) => async (p) => {
  const { data } = await api.get("/reports/outstanding", { params: { kind, to_date: p.to } });
  return { sections: [{ columns: [C("ledger", kind === "receivables" ? "Customer" : "Supplier"), C("gstin", "GSTIN"), C("phone", "Phone"), N("amount", "Outstanding")],
    rows: data.rows, footer: { ledger: "Total", amount: data.total } }] };
};

const plRows = (d, keys, names) => keys.flatMap((k, i) => (d.sections[k]?.length ? [{ particulars: names[i], amount: d.totals[k], _bold: true }, ...d.sections[k].map((r) => ({ particulars: `    ${r.ledger}`, amount: r.amount }))] : []));

const gstCols = [N("taxable", "Taxable"), N("igst", "IGST"), N("cgst", "CGST"), N("sgst", "SGST")];

const gstr1 = async (p) => {
  const { data: d } = await api.get("/reports/gstr1", { params: { month: p.month } });
  const s = d.summary;
  const inv = [C("gstin", "GSTIN"), C("party", "Party"), C("voucher_no", "Invoice No"), C("date", "Date"), C("place_of_supply", "Place of Supply"), N("rate", "Rate %"), ...gstCols];
  const fix = (rows) => rows.map((r) => ({ ...r, date: dmy(r.date) }));
  return { note: d.gstin ? `GSTIN ${d.gstin}` : "Set your GSTIN in Settings", sections: [
    { title: "Summary", columns: [C("section", "Section"), C("count", "Docs"), ...gstCols], rows: [
      { section: "4A - B2B invoices (registered)", count: String(s.b2b_count), ...s.b2b },
      { section: "7 - B2C supplies (unregistered)", count: String(s.b2c_count), ...s.b2c },
      { section: "9B - Credit notes (less)", count: String(s.note_count), ...s.cdn },
    ], footer: { section: "Net outward supplies", count: String(s.invoice_count), ...s.net } },
    { title: "B2B Invoices", columns: inv, rows: fix(d.b2b), footer: { gstin: "Total", ...s.b2b } },
    { title: "B2C Summary (by place of supply & rate)", columns: [C("place_of_supply", "Place of Supply"), N("rate", "Rate %"), ...gstCols], rows: d.b2c, footer: { place_of_supply: "Total", ...s.b2c } },
    { title: "Credit / Debit Notes", columns: inv, rows: fix(d.cdn), footer: { gstin: "Total", ...s.cdn } },
    { title: "HSN-wise Summary", columns: [C("hsn", "HSN/SAC"), N("rate", "Rate %"), N("qty", "Qty"), ...gstCols, N("total", "Total Value")], rows: d.hsn },
  ] };
};

const gstr3b = async (p) => {
  const { data: d } = await api.get("/reports/gstr3b", { params: { month: p.month } });
  const heads = [["igst", "Integrated Tax (IGST)"], ["cgst", "Central Tax (CGST)"], ["sgst", "State/UT Tax (SGST)"]];
  return { note: d.gstin ? `GSTIN ${d.gstin}` : "Set your GSTIN in Settings", sections: [
    { title: "3.1 Outward supplies", columns: [C("nature", "Nature of supplies"), ...gstCols], rows: [
      { nature: "(a) Outward taxable supplies (net of credit notes)", ...d.outward_taxable },
      { nature: "(c) Nil rated / exempted", ...d.outward_nil },
    ] },
    { title: "4 Eligible ITC (purchases net of debit notes)", columns: [C("nature", "Details"), ...gstCols], rows: [
      { nature: "(A)(5) All other ITC", ...d.itc }, { nature: "Nil rated / exempt inward supplies", ...d.inward_nil },
    ] },
    { title: "6.1 Payment of tax", columns: [C("head", "Tax head"), N("liability", "Tax payable"), N("itc", "Paid through ITC"), N("cash", "Paid in cash"), N("carry", "ITC carried forward")],
      rows: heads.map(([k, l]) => ({ head: l, liability: d.outward_taxable[k], itc: d.itc_utilised[k], cash: d.cash_payable[k], carry: d.itc_carry_forward[k] })),
      footer: { head: "Total cash payable", cash: d.total_cash_payable } },
  ] };
};

export const REPORTS = [
  { id: "day-book", label: "Day Book", filter: "range", load: async (p) => {
    const { data } = await api.get("/vouchers", { params: { from_date: p.from, to_date: p.to, status: "active", limit: 5000 } });
    const rows = [...data].reverse().map((v) => ({ ...v, date: dmy(v.date), type: VT[v.voucher_type]?.label }));
    return { sections: [{ columns: [C("date", "Date"), C("voucher_no", "Voucher No"), C("type", "Type"), C("party_name", "Particulars"), C("narration", "Narration"), N("amount", "Amount")],
      rows, footer: { party_name: `${rows.length} vouchers`, amount: rows.reduce((s, r) => s + r.amount, 0) } }] };
  } },
  { id: "cash-book", label: "Cash Book", filter: "ledger", groups: ["cash"], load: statement },
  { id: "bank-book", label: "Bank Book", filter: "ledger", groups: ["bank"], load: statement },
  { id: "ledger", label: "Ledger Statement", filter: "ledger", load: statement },
  { id: "trial-balance", label: "Trial Balance", filter: "asof", load: async (p) => {
    const { data } = await api.get("/reports/trial-balance", { params: { to_date: p.to } });
    return { balanced: data.balanced, sections: [{ columns: [C("ledger", "Ledger"), C("group", "Group"), N("debit", "Debit"), N("credit", "Credit")],
      rows: data.rows.map((r) => ({ ...r, debit: r.debit || "", credit: r.credit || "" })), footer: { ledger: "Grand Total", debit: data.total_debit, credit: data.total_credit } }] };
  } },
  { id: "profit-loss", label: "Profit & Loss", filter: "range", load: async (p) => {
    const { data: d } = await api.get("/reports/profit-loss", { params: { from_date: p.from, to_date: p.to } });
    const cols = [C("particulars", "Particulars"), N("amount", "Amount")];
    const inc = plRows(d, ["sales", "direct_income", "indirect_income"], ["Sales Accounts", "Direct Incomes", "Indirect Incomes"]);
    const exp = plRows(d, ["purchase", "direct_expense", "indirect_expense"], ["Purchase Accounts", "Direct Expenses", "Indirect Expenses"]);
    const sumOf = (ks) => ks.reduce((s, k) => s + (d.totals[k] || 0), 0);
    return { side: true, sections: [
      { title: "Income", columns: cols, rows: inc, footer: { particulars: "Total Income", amount: sumOf(["sales", "direct_income", "indirect_income"]) } },
      { title: "Expenses", columns: cols, rows: exp, footer: { particulars: "Total Expenses", amount: sumOf(["purchase", "direct_expense", "indirect_expense"]) } },
      { title: "Result", columns: cols, rows: [{ particulars: "Gross Profit", amount: d.gross_profit, _bold: true }], footer: { particulars: d.net_profit >= 0 ? "Net Profit" : "Net Loss", amount: d.net_profit } },
    ] };
  } },
  { id: "balance-sheet", label: "Balance Sheet", filter: "asof", load: async (p) => {
    const { data: d } = await api.get("/reports/balance-sheet", { params: { to_date: p.to } });
    const cols = [C("particulars", "Particulars"), N("amount", "Amount")];
    const flat = (gs) => gs.flatMap((g) => [{ particulars: g.group, amount: g.total, _bold: true }, ...g.rows.map((r) => ({ particulars: `    ${r.ledger}`, amount: r.amount }))]);
    const liab = [...flat(d.liabilities), { particulars: "Profit & Loss A/c", amount: d.profit_loss, _bold: true }];
    if (d.opening_difference) liab.push({ particulars: "Difference in Opening Balances", amount: d.opening_difference, _bold: true });
    return { side: true, balanced: d.balanced, sections: [
      { title: "Liabilities & Capital", columns: cols, rows: liab, footer: { particulars: "Total", amount: d.total_liabilities } },
      { title: "Assets", columns: cols, rows: flat(d.assets), footer: { particulars: "Total", amount: d.total_assets } },
    ] };
  } },
  { id: "receivables", label: "Receivables", filter: "asof", load: outstanding("receivables") },
  { id: "payables", label: "Payables", filter: "asof", load: outstanding("payables") },
  { id: "sales-register", label: "Sales Register", filter: "range", load: register("sales") },
  { id: "purchase-register", label: "Purchase Register", filter: "range", load: register("purchase") },
  { id: "stock-summary", label: "Stock Summary", filter: "asof", load: async (p) => {
    const { data } = await api.get("/stock-items", { params: { to_date: p.to } });
    return { sections: [{ columns: [C("name", "Item"), C("hsn", "HSN"), C("unit", "Unit"), N("purchased_qty", "Purchased"), N("sold_qty", "Sold"), N("on_hand", "On hand"), N("avg_cost", "Avg cost"), N("value", "Value")],
      rows: data.items.map((s) => ({ ...s, _bold: s.low || s.negative })), footer: { name: "Total stock value", value: data.total_value } }] };
  } },
  { id: "gstr-1", label: "GSTR-1", filter: "month", load: gstr1 },
  { id: "gstr-3b", label: "GSTR-3B", filter: "month", load: gstr3b },
];
