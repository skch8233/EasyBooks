from datetime import date as _d
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from db import db, NO_ID
from erp_core import erp
from erp_purchase import _po_view

router = APIRouter(prefix="/api/erp/reports")


class F(BaseModel):
    from_date: str = ""
    to_date: str = ""
    project_id: str = ""
    client_id: str = ""
    vendor_id: str = ""
    status: str = ""


def C(*cols):
    return [{"key": c[0], "label": c[1], "num": len(c) > 2, "sum": len(c) > 2 and c[2] != 2} for c in cols]


def r2(x):
    return round(x or 0, 2)


def q(bid: str, f: F, date_field: str = "date", party: Optional[str] = None, status: bool = True) -> dict:
    m = {"business_id": bid}
    if f.from_date or f.to_date:
        m[date_field] = {**({"$gte": f.from_date} if f.from_date else {}), **({"$lte": f.to_date} if f.to_date else {})}
    if f.project_id:
        m["project_id"] = f.project_id
    if party == "client_id" and f.client_id:
        m["client_id"] = f.client_id
    if party == "vendor_id" and f.vendor_id:
        m["vendor_id"] = f.vendor_id
    if status and f.status:
        m["status"] = f.status
    return m


async def find(coll: str, m: dict, sort: str = "date"):
    return await db[coll].find(m, {**NO_ID, "versions": 0}).sort(sort, 1).to_list(20000)


def today() -> str:
    return _d.today().isoformat()


def sums(rows, cols, key=""):
    live = rows if key == "cancelled_invoices" else [r for r in rows if r.get("status") not in ("cancelled", "draft")]
    return {c["key"]: r2(sum(r.get(c["key"]) or 0 for r in live)) for c in cols if c["sum"] and not c["key"].endswith(("_pct", "days", "rate"))}


async def _project_money(bid: str, f: F):
    projects = await db.erp_projects.find({"business_id": bid, **({"id": f.project_id} if f.project_id else {}),
                                           **({"client_id": f.client_id} if f.client_id else {}), **({"status": f.status} if f.status else {})}, NO_ID).sort("code", 1).to_list(5000)
    g = F(**{**f.model_dump(), "status": "", "client_id": "", "project_id": ""})
    inv = await find("erp_invoices", {**q(bid, g), "status": "finalized"})
    notes = await find("erp_notes", {**q(bid, g), "status": "active"})
    bills = await find("erp_bills", {**q(bid, g, "vendor_invoice_date"), "status": "posted"})
    exps = await find("erp_expenses", {**q(bid, g), "status": "posted"})
    out = []
    for p in projects:
        pid = p["id"]
        income = sum(i["totals"]["taxable"] for i in inv if i["project_id"] == pid)
        income += sum(n["totals"]["taxable"] * (1 if n["kind"] == "debit" else -1) for n in notes if n["project_id"] == pid)
        pur = sum(b["totals"]["taxable"] for b in bills if b["project_id"] == pid)
        ex = sum(e["totals"]["taxable"] for e in exps if e["project_id"] == pid)
        out.append({"id": pid, "code": p["code"], "project": p["name"], "client": p.get("client_name", ""), "status": p["status"], "contract_value": r2(p["contract_value"]),
                    "billed": r2(sum(i["totals"]["total"] for i in inv if i["project_id"] == pid)), "received": r2(sum(i.get("paid", 0) for i in inv if i["project_id"] == pid)),
                    "outstanding": r2(sum(i.get("balance", 0) for i in inv if i["project_id"] == pid)),
                    "income": r2(income), "purchases": r2(pur), "expenses": r2(ex), "cost": r2(pur + ex), "profit": r2(income - pur - ex),
                    "margin_pct": r2((income - pur - ex) / income * 100) if income else 0})
    return out


async def project_income_expense(bid, f):
    cols = C(("code", "Project code"), ("project", "Project"), ("client", "Client"), ("income", "Income (net of notes)", 1), ("purchases", "Purchase bills", 1),
             ("expenses", "Expenses", 1), ("cost", "Total cost", 1), ("profit", "Net", 1))
    return cols, await _project_money(bid, f)


async def project_profitability(bid, f):
    cols = C(("code", "Project code"), ("project", "Project"), ("status", "Status"), ("contract_value", "Contract value", 1), ("billed", "Billed (incl GST)", 1),
             ("received", "Received", 1), ("outstanding", "Outstanding", 1), ("income", "Income (taxable)", 1), ("cost", "Cost", 1), ("profit", "Profit", 1), ("margin_pct", "Margin %", 1))
    return cols, await _project_money(bid, f)


async def clients(bid, f):
    ids = {"$in": [p["client_id"] for p in await db.erp_projects.find({"business_id": bid, "id": f.project_id}, {"client_id": 1}).to_list(5)]} if f.project_id else None
    parties = await db.erp_parties.find({"business_id": bid, "kind": "client", **({"id": f.client_id} if f.client_id else {"id": ids} if ids else {})}, NO_ID).sort("name_lower", 1).to_list(5000)
    g = F(**{**f.model_dump(), "status": ""})
    inv = await find("erp_invoices", {**q(bid, g, party="client_id"), "status": "finalized"})
    quotes = await find("erp_quotations", {**q(bid, g, party="client_id"), "status": {"$ne": "cancelled"}})
    notes = await find("erp_notes", {**q(bid, g, party="client_id"), "status": "active"})
    projects = await db.erp_projects.find({"business_id": bid, **({"id": f.project_id} if f.project_id else {})}, {"client_id": 1}).to_list(5000)
    rows = []
    for p in parties:
        i = [x for x in inv if x["client_id"] == p["id"]]
        rows.append({"party": p["company_name"], "gstin": p.get("gstin", ""), "state": p.get("state", ""), "mobile": p.get("mobile", ""),
                     "projects": sum(1 for x in projects if x.get("client_id") == p["id"]), "quoted": r2(sum(x["totals"]["total"] for x in quotes if x["client_id"] == p["id"])),
                     "invoiced": r2(sum(x["totals"]["total"] for x in i)), "credit_notes": r2(sum(n["totals"]["total"] for n in notes if n["client_id"] == p["id"] and n["kind"] == "credit")),
                     "received": r2(sum(x.get("paid", 0) for x in i)), "outstanding": r2(sum(x.get("balance", 0) for x in i))})
    cols = C(("party", "Client"), ("gstin", "GSTIN"), ("state", "State"), ("mobile", "Mobile"), ("projects", "Projects", 1), ("quoted", "Quoted", 1), ("invoiced", "Invoiced", 1),
             ("credit_notes", "Credit notes", 1), ("received", "Received", 1), ("outstanding", "Outstanding", 1))
    return cols, rows


async def vendors(bid, f):
    parties = await db.erp_parties.find({"business_id": bid, "kind": "vendor", **({"id": f.vendor_id} if f.vendor_id else {})}, NO_ID).sort("name_lower", 1).to_list(5000)
    g = F(**{**f.model_dump(), "status": ""})
    pos = await find("erp_pos", {**q(bid, g, party="vendor_id"), "status": {"$in": ["approved", "closed"]}})
    grns = await find("erp_grns", {**q(bid, g, party="vendor_id"), "status": "posted"})
    bills = await find("erp_bills", {**q(bid, g, "vendor_invoice_date", "vendor_id"), "status": "posted"})
    today_ = today()
    rows = []
    for p in parties:
        b = [x for x in bills if x["vendor_id"] == p["id"]]
        bal = sum(x["totals"]["total"] - x.get("paid", 0) for x in b)
        rows.append({"party": p["company_name"], "gstin": p.get("gstin", ""), "state": p.get("state", ""), "mobile": p.get("mobile", ""),
                     "pos": sum(1 for x in pos if x["vendor_id"] == p["id"]), "po_value": r2(sum(x["totals"]["total"] for x in pos if x["vendor_id"] == p["id"])),
                     "received": r2(sum(x.get("accepted_value", 0) for x in grns if x["vendor_id"] == p["id"])), "billed": r2(sum(x["totals"]["total"] for x in b)),
                     "paid": r2(sum(x.get("paid", 0) for x in b)), "balance": r2(bal),
                     "overdue": r2(sum(x["totals"]["total"] - x.get("paid", 0) for x in b if x.get("due_date") and x["due_date"] < today_))})
    cols = C(("party", "Vendor"), ("gstin", "GSTIN"), ("state", "State"), ("mobile", "Mobile"), ("pos", "POs", 1), ("po_value", "PO value", 1), ("received", "Material received", 1),
             ("billed", "Billed", 1), ("paid", "Paid", 1), ("balance", "Payable", 1), ("overdue", "Overdue", 1))
    return cols, rows


async def quotations(bid, f):
    t = today()
    g = F(**{**f.model_dump(), "status": "" if f.status == "expired" else f.status})
    rows = []
    for x in await find("erp_quotations", q(bid, g, party="client_id")):
        st = "expired" if x["status"] == "sent" and x.get("valid_until") and x["valid_until"] < t else x["status"]
        if f.status == "expired" and st != "expired":
            continue
        rows.append({"number": x["number"], "date": x["date"], "valid_until": x.get("valid_until", ""), "project": f"{x['project_code']} {x['project_name']}", "client": x["client_name"],
                     "taxable": x["totals"]["taxable"], "gst": r2(x["totals"]["total"] - x["totals"]["taxable"]), "total": x["totals"]["total"], "status": st})
    return C(("number", "Number"), ("date", "Date"), ("valid_until", "Valid until"), ("project", "Project"), ("client", "Client"), ("taxable", "Taxable", 1),
             ("gst", "GST", 1), ("total", "Total", 1), ("status", "Status")), rows


def _inv_row(x, t):
    return {"number": x["number"], "date": x["date"], "due_date": x.get("due_date", ""), "project": f"{x['project_code']} {x['project_name']}", "client": x["client_name"],
            "taxable": x["totals"]["taxable"], "gst": r2(x["totals"].get("cgst", 0) + x["totals"].get("sgst", 0) + x["totals"].get("igst", 0)), "total": x["totals"]["total"],
            "paid": r2(x.get("paid", 0)), "balance": r2(x.get("balance", 0)) if x["status"] == "finalized" else 0,
            "status": "overdue" if x["status"] == "finalized" and x.get("balance", 0) > 0.005 and x.get("due_date", "9") < t else x["status"]}


async def invoices(bid, f):
    t = today()
    g = F(**{**f.model_dump(), "status": "finalized" if f.status == "overdue" else f.status})
    rows = [r for r in (_inv_row(x, t) for x in await find("erp_invoices", q(bid, g, party="client_id"))) if f.status != "overdue" or r["status"] == "overdue"]
    return C(("number", "Number"), ("date", "Date"), ("due_date", "Due"), ("project", "Project"), ("client", "Client"), ("taxable", "Taxable", 1), ("gst", "GST", 1),
             ("total", "Total", 1), ("paid", "Received", 1), ("balance", "Balance", 1), ("status", "Status")), rows


async def cancelled_invoices(bid, f):
    rows = [{"number": x["number"], "date": x["date"], "project": f"{x['project_code']} {x['project_name']}", "client": x["client_name"], "total": x["totals"]["total"],
             "cancelled_at": (x.get("cancelled_at") or "")[:10], "cancelled_by": x.get("cancelled_by", ""), "reason": x.get("cancel_reason", ""), "voucher": x.get("voucher_no", "")}
            for x in await find("erp_invoices", {**q(bid, f, party="client_id", status=False), "status": "cancelled"})]
    return C(("number", "Number"), ("date", "Invoice date"), ("project", "Project"), ("client", "Client"), ("total", "Total", 1), ("cancelled_at", "Cancelled on"),
             ("cancelled_by", "Cancelled by"), ("reason", "Reason"), ("voucher", "Accounting voucher")), rows


async def outstanding_invoices(bid, f):
    t = today()
    rows = []
    for x in await find("erp_invoices", {**q(bid, f, party="client_id", status=False), "status": "finalized", "balance": {"$gt": 0.005}}, "due_date"):
        days = (_d.fromisoformat(t) - _d.fromisoformat(x["due_date"])).days if x.get("due_date") else 0
        r = {**_inv_row(x, t), "overdue_days": max(days, 0), "bucket": "Not due" if days <= 0 else "1-30" if days <= 30 else "31-60" if days <= 60 else "61-90" if days <= 90 else "90+"}
        if not f.status or f.status == r["status"]:
            rows.append(r)
    return C(("number", "Number"), ("date", "Date"), ("due_date", "Due"), ("project", "Project"), ("client", "Client"), ("total", "Total", 1), ("paid", "Received", 1),
             ("balance", "Balance", 1), ("overdue_days", "Days overdue", 1), ("bucket", "Ageing"), ("status", "Status")), rows


async def prs(bid, f):
    rows = [{"number": x["number"], "date": x["date"], "project": f"{x['project_code']} {x['project_name']}", "required_by": x.get("required_by", ""),
             "items": "; ".join(f"{i['description']} x {i['qty']:g} {i.get('unit', '')}".strip() for i in x["items"]), "requested_by": x.get("requested_by", ""),
             "approved_by": x.get("approved_by", ""), "rfqs": ", ".join(r.get("number", "") for r in x.get("rfqs", []) if isinstance(r, dict)), "status": x["status"]}
            for x in await find("erp_prs", q(bid, f))]
    return C(("number", "Number"), ("date", "Date"), ("project", "Project"), ("required_by", "Required by"), ("items", "Items"), ("requested_by", "Requested by"),
             ("approved_by", "Approved by"), ("status", "Status")), rows


async def vendor_comparison(bid, f):
    rfqs = await find("erp_rfqs", q(bid, f))
    rows = []
    for r in rfqs:
        quotes = await db.erp_vendor_quotes.find({"rfq_id": r["id"], **({"vendor_id": f.vendor_id} if f.vendor_id else {})}, NO_ID).to_list(100)
        low = min((x["totals"]["total"] for x in quotes), default=0)
        for x in sorted(quotes, key=lambda x: x["totals"]["total"]):
            rows.append({"rfq": r["number"], "date": r["date"], "project": f"{r['project_code']} {r['project_name']}", "vendor": x["vendor_name"], "quote_ref": x.get("quote_ref", ""),
                         "taxable": x["totals"]["taxable"], "total": x["totals"]["total"], "diff": r2(x["totals"]["total"] - low), "delivery_days": x.get("delivery_days", 0),
                         "payment_terms": x.get("payment_terms", ""), "lowest": "Yes" if x["totals"]["total"] == low else "",
                         "selected": "Selected" if r.get("selected_quote_id") == x["id"] else "", "status": r["status"]})
    return C(("rfq", "RFQ"), ("date", "Date"), ("project", "Project"), ("vendor", "Vendor"), ("quote_ref", "Quote ref"), ("taxable", "Taxable", 2), ("total", "Total", 2),
             ("diff", "Above lowest", 2), ("delivery_days", "Delivery days", 1), ("payment_terms", "Payment terms"), ("lowest", "Lowest"), ("selected", "Selected"), ("status", "RFQ status")), rows


async def _pos(bid, f, extra=None):
    return [await _po_view(p) for p in await find("erp_pos", {**q(bid, f, party="vendor_id"), **(extra or {})})]


async def pos(bid, f):
    rows = [{"number": p["number"], "date": p["date"], "delivery_date": p.get("delivery_date", ""), "project": f"{p['project_code']} {p['project_name']}", "vendor": p["vendor_name"],
             "taxable": p["totals"]["taxable"], "total": p["totals"]["total"], "received": r2(p.get("received_value", 0)),
             "billed": r2(sum(b["totals"]["total"] for b in p.get("bills", []) if b["status"] == "posted")), "receipt": p.get("receipt_status", "").replace("_", " "), "status": p["status"]}
            for p in await _pos(bid, f)]
    return C(("number", "Number"), ("date", "Date"), ("delivery_date", "Delivery"), ("project", "Project"), ("vendor", "Vendor"), ("taxable", "Taxable", 1),
             ("total", "Total", 1), ("received", "Received value", 1), ("billed", "Billed", 1), ("receipt", "Receipt"), ("status", "Status")), rows


async def pending_delivery(bid, f):
    g = F(**{**f.model_dump(), "status": ""})
    t, rows = today(), []
    for p in await _pos(bid, g, {"status": "approved"}):
        for it in p["items"]:
            if it["pending"] > 0.0001:
                late = bool(p.get("delivery_date")) and p["delivery_date"] < t
                if f.status and f.status != ("late" if late else "on time"):
                    continue
                rows.append({"po": p["number"], "date": p["date"], "delivery_date": p.get("delivery_date", ""), "project": f"{p['project_code']} {p['project_name']}",
                             "vendor": p["vendor_name"], "item": it["description"], "unit": it.get("unit", ""), "ordered": it["qty"], "accepted": it["accepted"],
                             "rejected": it["rejected"], "pending": it["pending"], "pending_value": r2(it["pending"] * it["net_rate"]), "status": "late" if late else "on time"})
    return C(("po", "PO"), ("date", "PO date"), ("delivery_date", "Delivery due"), ("project", "Project"), ("vendor", "Vendor"), ("item", "Item"), ("unit", "Unit"),
             ("ordered", "Ordered", 2), ("accepted", "Accepted", 2), ("rejected", "Rejected", 2), ("pending", "Pending", 2), ("pending_value", "Pending value", 1), ("status", "Status")), rows


async def grns(bid, f):
    rows = []
    for g in await find("erp_grns", q(bid, f, party="vendor_id")):
        for ln in g["lines"]:
            rows.append({"number": g["number"], "date": g["date"], "po": g["po_number"], "project": g["project_code"], "vendor": g["vendor_name"], "challan": g.get("challan_no", ""),
                         "item": ln["description"], "received": ln["received"], "accepted": ln["accepted"], "rejected": ln["rejected"],
                         "value": r2(ln["accepted"] * ln["net_rate"]), "status": g["status"]})
    return C(("number", "GRN"), ("date", "Date"), ("po", "PO"), ("project", "Project"), ("vendor", "Vendor"), ("challan", "Challan"), ("item", "Item"),
             ("received", "Received", 2), ("accepted", "Accepted", 2), ("rejected", "Rejected", 2), ("value", "Accepted value", 1), ("status", "Status")), rows


async def bills(bid, f):
    t, rows = today(), []
    for b in await find("erp_bills", q(bid, f, "vendor_invoice_date", "vendor_id"), "vendor_invoice_date"):
        bal = r2(b["totals"]["total"] - b.get("paid", 0)) if b["status"] == "posted" else 0
        rows.append({"number": b["number"], "vendor_invoice": b["vendor_invoice_no"], "date": b["vendor_invoice_date"], "due_date": b.get("due_date", ""), "project": b["project_code"],
                     "vendor": b["vendor_name"], "po": b.get("po_number", ""), "taxable": b["totals"]["taxable"], "gst": r2(b["totals"]["total"] - b["totals"]["taxable"]),
                     "total": b["totals"]["total"], "paid": r2(b.get("paid", 0)), "balance": bal, "voucher": b.get("voucher_no", ""),
                     "status": "overdue" if bal > 0.005 and b.get("due_date") and b["due_date"] < t else b["status"]})
    return C(("number", "Number"), ("vendor_invoice", "Vendor invoice"), ("date", "Invoice date"), ("due_date", "Due"), ("project", "Project"), ("vendor", "Vendor"),
             ("po", "PO"), ("taxable", "Taxable", 1), ("gst", "GST", 1), ("total", "Total", 1), ("paid", "Paid", 1), ("balance", "Balance", 1), ("voucher", "Voucher"), ("status", "Status")), rows


async def reconciliation(bid, f):
    g = F(**{**f.model_dump(), "status": ""})
    rows = []
    for p in await _pos(bid, g, {"status": {"$in": ["approved", "closed"]}}):
        for it in p["items"]:
            st = "matched" if abs(it["qty"] - it["accepted"]) < 0.0001 and abs(it["accepted"] - it["billed_qty"]) < 0.0001 else \
                "to receive" if it["accepted"] < it["qty"] - 0.0001 and p["status"] == "approved" else "to bill" if it["billed_qty"] < it["accepted"] - 0.0001 else "short closed"
            if f.status and f.status != st:
                continue
            rows.append({"po": p["number"], "project": p["project_code"], "vendor": p["vendor_name"], "item": it["description"], "rate": it["net_rate"],
                         "ordered": it["qty"], "received": it["accepted"], "billed": it["billed_qty"], "po_value": r2(it["qty"] * it["net_rate"]),
                         "received_value": r2(it["accepted"] * it["net_rate"]), "billed_value": r2(it["billed_qty"] * it["net_rate"]),
                         "unbilled_value": r2((it["accepted"] - it["billed_qty"]) * it["net_rate"]), "status": st})
    return C(("po", "PO"), ("project", "Project"), ("vendor", "Vendor"), ("item", "Item"), ("rate", "Net rate", 2), ("ordered", "PO qty", 2), ("received", "GRN accepted", 2),
             ("billed", "Billed qty", 2), ("po_value", "PO value", 1), ("received_value", "Received value", 1), ("billed_value", "Billed value", 1),
             ("unbilled_value", "Received not billed", 1), ("status", "Status")), rows


async def expenses(bid, f):
    rows = [{"number": e["number"], "date": e["date"], "project": e["project_code"], "category": e["category"], "paid_to": e["paid_to"], "mode": e.get("payment_mode", ""),
             "reference": e.get("reference", ""), "amount": e["totals"]["taxable"], "gst": r2(e["totals"]["total"] - e["totals"]["taxable"]), "total": e["totals"]["total"],
             "voucher": e.get("voucher_no", ""), "status": e["status"]}
            for e in await find("erp_expenses", {**q(bid, f), **({"vendor_id": f.vendor_id} if f.vendor_id else {})})]
    return C(("number", "Number"), ("date", "Date"), ("project", "Project"), ("category", "Category"), ("paid_to", "Paid to"), ("mode", "Mode"), ("reference", "Bill no"),
             ("amount", "Amount", 1), ("gst", "GST", 1), ("total", "Total", 1), ("voucher", "Voucher"), ("status", "Status")), rows


P, CL, V = "project_id", "client_id", "vendor_id"
REPORTS = {
    "project_income_expense": ("Project-wise income and expenses", project_income_expense, [P, CL], ["Planning", "Running", "On Hold", "Completed", "Cancelled"]),
    "project_profitability": ("Project profitability", project_profitability, [P, CL], ["Planning", "Running", "On Hold", "Completed", "Cancelled"]),
    "clients": ("Client report", clients, [P, CL], []),
    "vendors": ("Vendor report", vendors, [P, V], []),
    "quotations": ("Quotation register", quotations, [P, CL], ["draft", "sent", "accepted", "rejected", "expired", "converted", "cancelled"]),
    "invoices": ("Invoice register", invoices, [P, CL], ["draft", "finalized", "overdue", "cancelled"]),
    "cancelled_invoices": ("Cancelled invoice report", cancelled_invoices, [P, CL], []),
    "outstanding_invoices": ("Outstanding invoices", outstanding_invoices, [P, CL], ["finalized", "overdue"]),
    "prs": ("Purchase requisition register", prs, [P], ["draft", "submitted", "approved", "rejected", "rfq", "closed", "cancelled"]),
    "vendor_comparison": ("Vendor comparison report", vendor_comparison, [P, V], ["open", "selected", "ordered", "cancelled"]),
    "pos": ("Purchase order register", pos, [P, V], ["draft", "approved", "closed", "cancelled"]),
    "pending_delivery": ("Pending delivery report", pending_delivery, [P, V], ["on time", "late"]),
    "grns": ("GRN register", grns, [P, V], ["posted", "cancelled"]),
    "bills": ("Purchase bill register", bills, [P, V], ["draft", "posted", "cancelled"]),
    "reconciliation": ("PO vs GRN vs bill reconciliation", reconciliation, [P, V], ["matched", "to receive", "to bill", "short closed"]),
    "expenses": ("Expense report", expenses, [P, V], ["draft", "posted", "cancelled"]),
}


@router.get("")
async def list_reports(user=Depends(erp())):
    return [{"key": k, "title": t, "filters": fl, "statuses": st} for k, (t, _, fl, st) in REPORTS.items()]


@router.get("/{key}")
async def run_report(key: str, f: F = Depends(), user=Depends(erp())):
    if key not in REPORTS:
        raise HTTPException(404, "Report not found")
    title, fn, _, _ = REPORTS[key]
    cols, rows = await fn(user["business_id"], f)
    return {"key": key, "title": title, "columns": cols, "rows": rows, "footer": sums(rows, cols, key), "count": len(rows)}
