import { amt, dmy } from "@/lib/format";

const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function open(html, width) {
  const w = window.open("", "_blank", `width=${width},height=700`);
  if (!w) return;
  w.document.write(`<html><head><title>Receipt</title><style>body{font-family:Arial,sans-serif;color:#0F172A;margin:16px}table{width:100%;border-collapse:collapse}td,th{padding:4px 6px;font-size:12px;text-align:left}.r{text-align:right}.b{font-weight:bold}.h{border-bottom:1px solid #0F172A}.t td{border-top:1px solid #0F172A;font-weight:bold}h2,h3,p{margin:4px 0}.c{text-align:center}</style></head><body>${html}<script>window.onload=()=>{window.print()}</script></body></html>`);
  w.document.close();
}
const head = (s, title) => `<div class="c"><h2>${esc(s?.company_name)}</h2><p style="font-size:11px">${esc(s?.address)}${s?.gstin ? `<br>GSTIN: ${esc(s.gstin)}` : ""}${s?.phone ? ` · Ph: ${esc(s.phone)}` : ""}</p><h3 style="margin-top:8px">${title}</h3></div>`;

export function printThermal(s, v, cart, paid) {
  const rows = cart.map((c) => `<tr><td>${esc(c.name)}<br><small>${c.qty} x ${amt(c.rate)}${c.mrp ? ` (MRP ${amt(c.mrp)})` : ""}</small></td><td class="r">${amt(c.qty * c.rate * (1 + c.gst_rate / 100))}</td></tr>`).join("");
  const t = v.totals || {};
  open(`<div style="width:58mm;font-size:11px">${head(s, "Cash Memo / GST Receipt")}<p>Bill: ${esc(v.voucher_no)}<br>Date: ${dmy(v.date)}</p><table><tr class="h"><th>Item</th><th class="r">Amt</th></tr>${rows}
    <tr class="t"><td>Taxable</td><td class="r">${amt(t.taxable)}</td></tr><tr><td>GST</td><td class="r">${amt((t.cgst || 0) + (t.sgst || 0) + (t.igst || 0))}</td></tr><tr class="t"><td>TOTAL</td><td class="r">${amt(t.total ?? v.amount)}</td></tr>
    <tr><td>Paid by</td><td class="r">${esc(paid)}</td></tr></table><p class="c" style="margin-top:8px">Thank you! Visit again.</p></div>`, 320);
}

export function printFeeReceipt(s, r, st) {
  const sched = (st?.schedule || []).map((i) => `<tr><td>${esc(i.label || "Installment")}</td><td>${dmy(i.due_date)}</td><td class="r">${amt(i.amount)}</td><td class="r">${amt(i.paid)}</td><td class="r">${amt(i.due)}</td></tr>`).join("");
  open(`${head(s, "FEE RECEIPT")}<table style="margin:10px 0"><tr><td><b>Receipt No:</b> ${esc(r.receipt_no)}</td><td class="r"><b>Date:</b> ${dmy(r.date)}</td></tr>
    <tr><td><b>Student:</b> ${esc(r.student)}</td><td class="r"><b>Roll No:</b> ${esc(r.roll_no || "-")}</td></tr><tr><td><b>Course:</b> ${esc(r.course || "-")}</td><td class="r"><b>Batch:</b> ${esc(r.batch || "-")}</td></tr></table>
    <table><tr class="h"><th>Particulars</th><th class="r">Amount (₹)</th></tr><tr><td>Tuition / course fee ${esc(r.note)}</td><td class="r">${amt(r.amount)}</td></tr><tr><td>Late fine</td><td class="r">${amt(r.fine)}</td></tr><tr class="t"><td>Total received</td><td class="r">${amt(r.total)}</td></tr></table>
    ${sched ? `<h3 style="margin-top:14px">Installment breakdown</h3><table><tr class="h"><th>Installment</th><th>Due date</th><th class="r">Amount</th><th class="r">Paid</th><th class="r">Balance</th></tr>${sched}</table>` : ""}
    <p style="margin-top:10px"><b>Balance fee after this receipt: ₹${amt(r.balance_after)}</b></p><p style="margin-top:40px" class="r">Authorised signatory</p>`, 800);
}

const KIND = { opd: "OPD CONSULTATION RECEIPT", ipd: "IPD BILL / RECEIPT", lab: "LABORATORY RECEIPT", pharmacy: "PHARMACY RECEIPT" };
export function printHospitalReceipt(s, b) {
  const rows = b.lines.map((l, i) => `<tr><td>${i + 1}</td><td>${esc(l.description)}</td><td class="r">${l.qty}</td><td class="r">${amt(l.rate)}</td><td class="r">${amt(l.amount)}</td></tr>`).join("");
  open(`${head(s, KIND[b.kind])}<table style="margin:10px 0"><tr><td><b>Bill No:</b> ${esc(b.bill_no)}</td><td class="r"><b>Date:</b> ${dmy(b.date)}</td></tr>
    <tr><td><b>Patient:</b> ${esc(b.patient)} (${esc(b.reg_no)})</td><td class="r"><b>Age/Sex:</b> ${esc(b.age || "-")}/${esc(b.gender || "-")}</td></tr>
    <tr><td><b>Doctor:</b> ${esc(b.doctor || "-")}</td><td class="r">${b.kind === "ipd" ? `<b>Admit:</b> ${dmy(b.admission_date)} <b>Discharge:</b> ${dmy(b.discharge_date)}` : ""}</td></tr></table>
    <table><tr class="h"><th>#</th><th>Particulars</th><th class="r">Qty</th><th class="r">Rate</th><th class="r">Amount</th></tr>${rows}<tr class="t"><td></td><td>Total</td><td></td><td></td><td class="r">₹${amt(b.total)}</td></tr></table>
    <p style="margin-top:40px" class="r">Authorised signatory</p>`, 800);
}

export function printPayslip(s, run, p) {
  open(`${head(s, `PAYSLIP - ${esc(run.month)}`)}<table style="margin:10px 0"><tr><td><b>Employee:</b> ${esc(p.name)}</td><td class="r"><b>Designation:</b> ${esc(p.designation || "-")}</td></tr><tr><td><b>Paid on:</b> ${dmy(run.date)}</td><td class="r"><b>Voucher:</b> ${esc(run.voucher_no)}</td></tr></table>
    <table><tr class="h"><th>Earnings</th><th class="r">₹</th><th>Deductions</th><th class="r">₹</th></tr><tr><td>Basic</td><td class="r">${amt(p.basic)}</td><td>PF / ESI / TDS</td><td class="r">${amt(p.deductions)}</td></tr><tr><td>Allowances</td><td class="r">${amt(p.allowances)}</td><td></td><td></td></tr>
    <tr class="t"><td>Gross</td><td class="r">${amt(p.gross)}</td><td>Total deductions</td><td class="r">${amt(p.deductions)}</td></tr></table><h3 style="margin-top:12px">Net pay: ₹${amt(p.net)}</h3><p style="margin-top:40px" class="r">Authorised signatory</p>`, 800);
}
