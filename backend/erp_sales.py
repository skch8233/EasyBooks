import re
from datetime import date as _date
from decimal import Decimal
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from accounting import D, Item, VoucherIn, Entry
from db import db, NO_ID, new_id, now_iso, audit, clean
from emailer import send_email
from erp_core import erp, erp_settings, get_party, get_project, next_seq
from routes_vouchers import cancel_voucher, create_voucher, update_voucher, CancelIn

router = APIRouter(prefix="/api/erp")
Template = Literal["classic", "modern", "detailed", "gst_goods", "gst_service"]


class Line(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    hsn: str = ""
    unit: str = ""
    qty: float = Field(1, gt=0)
    rate: float = Field(0, ge=0)
    discount: float = Field(0, ge=0, le=100)
    gst_rate: float = Field(18, ge=0, le=100)


def compute(lines: List[Line], gst_type: str) -> tuple:
    items, t = [], {k: D(0) for k in ("gross", "discount", "taxable", "cgst", "sgst", "igst")}
    for ln in lines:
        gross = D(Decimal(str(ln.qty)) * Decimal(str(ln.rate)))
        net_rate = D(Decimal(str(ln.rate)) * (100 - Decimal(str(ln.discount))) / 100)
        amt = D(Decimal(str(ln.qty)) * net_rate)
        tax = D(amt * Decimal(str(ln.gst_rate)) / 100) if gst_type != "none" else D(0)
        c = D(tax / 2) if gst_type == "intra" else D(0)
        s = tax - c if gst_type == "intra" else D(0)
        i = tax if gst_type == "inter" else D(0)
        for k, v in (("gross", gross), ("discount", gross - amt), ("taxable", amt), ("cgst", c), ("sgst", s), ("igst", i)):
            t[k] += v
        items.append({**ln.model_dump(), "net_rate": float(net_rate), "amount": float(amt), "cgst": float(c), "sgst": float(s), "igst": float(i),
                      "total": float(amt + tax)})
    t["total"] = t["taxable"] + t["cgst"] + t["sgst"] + t["igst"]
    return items, {k: float(v) for k, v in t.items()}


async def _gst_type(client: dict, bid: str, override: Optional[str]) -> str:
    if override:
        return override
    s = await db.settings.find_one({"business_id": bid}, NO_ID) or {}
    a, b = (s.get("state") or "").strip().lower(), (client.get("state") or "").strip().lower()
    return "inter" if a and b and a != b else "intra"


def _fy_name(d: str) -> str:
    y, m = int(d[:4]), int(d[5:7])
    y = y if m >= 4 else y - 1
    return f"{y}-{str(y + 1)[2:]}"


def _today() -> str:
    return _date.today().isoformat()


DATE = r"^\d{4}-\d{2}-\d{2}$"


# ================= Quotations =================
class QuoteIn(BaseModel):
    number: str = ""
    date: str = Field(pattern=DATE)
    valid_until: str = ""
    client_id: str
    project_id: Optional[str] = None
    template: Template = "classic"
    gst_type: Optional[Literal["intra", "inter", "none"]] = None
    subject: str = ""
    items: List[Line] = Field(min_length=1)
    scope_of_work: str = ""
    delivery_terms: str = ""
    payment_terms: str = ""
    notes: str = ""


async def _quote_doc(q: QuoteIn, bid: str) -> dict:
    client = await get_party(q.client_id, bid)
    if client["kind"] != "client":
        raise HTTPException(400, "Select a client")
    proj = await get_project(q.project_id, bid) if q.project_id else None
    if proj and proj["client_id"] != q.client_id:
        raise HTTPException(400, "The project belongs to a different client")
    gt = await _gst_type(client, bid, q.gst_type)
    items, totals = compute(q.items, gt)
    return {**q.model_dump(exclude={"number"}), "gst_type": gt, "items": items, "totals": totals, "client_name": client["company_name"],
            "client": {k: client.get(k, "") for k in ("company_name", "gstin", "pan", "address", "state", "contact_person", "mobile", "email")},
            "project_name": proj["name"] if proj else "", "project_code": proj["code"] if proj else ""}


def _quote_view(q: dict) -> dict:
    q = clean(q)
    if q["status"] == "sent" and q.get("valid_until") and q["valid_until"] < _today():
        q["status"] = "expired"
    return q


async def _quote(qid: str, bid: str) -> dict:
    q = await db.erp_quotations.find_one({"id": qid, "business_id": bid}, NO_ID)
    if not q:
        raise HTTPException(404, "Quotation not found")
    return q


async def _quote_number(bid: str, manual: str, d: str, exclude: str = "") -> str:
    if manual.strip():
        n = manual.strip()
        if await db.erp_quotations.find_one({"business_id": bid, "number": n, "id": {"$ne": exclude}}):
            raise HTTPException(400, f"Quotation number {n} is already used")
        return n
    s = await erp_settings(bid)
    while True:
        n = f"{s['quotation_prefix']}/{_fy_name(d)}/{await next_seq(bid, 'quote:' + _fy_name(d)):04d}"
        if not await db.erp_quotations.find_one({"business_id": bid, "number": n}):
            return n


@router.get("/quotations")
async def list_quotes(status: Optional[str] = None, project_id: Optional[str] = None, client_id: Optional[str] = None,
                      q: Optional[str] = None, user=Depends(erp())):
    query = {"business_id": user["business_id"], **({"project_id": project_id} if project_id else {}), **({"client_id": client_id} if client_id else {})}
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        query["$or"] = [{"number": rx}, {"client_name": rx}, {"project_name": rx}, {"subject": rx}]
    rows = [_quote_view(r) for r in await db.erp_quotations.find(query, NO_ID).sort("created_at", -1).to_list(5000)]
    return [r for r in rows if not status or r["status"] == status]


@router.get("/quotations/{qid}")
async def get_quote(qid: str, user=Depends(erp())):
    return _quote_view(await _quote(qid, user["business_id"]))


@router.post("/quotations")
async def create_quote(q: QuoteIn, user=Depends(erp("create"))):
    bid = user["business_id"]
    doc = {**(await _quote_doc(q, bid)), "id": new_id(), "business_id": bid, "number": await _quote_number(bid, q.number, q.date),
           "status": "draft", "created_by": user["name"], "created_at": now_iso()}
    await db.erp_quotations.insert_one({**doc})
    await audit("erp_quotation", doc["id"], "create", user, note=doc["number"])
    return clean(doc)


@router.put("/quotations/{qid}")
async def update_quote(qid: str, q: QuoteIn, user=Depends(erp("edit"))):
    bid = user["business_id"]
    before = await _quote(qid, bid)
    if before["status"] not in ("draft", "sent"):
        raise HTTPException(400, f"A {before['status']} quotation cannot be edited. Duplicate it instead.")
    num = await _quote_number(bid, q.number, q.date, qid) if q.number.strip() and q.number.strip() != before["number"] else before["number"]
    upd = {**(await _quote_doc(q, bid)), "number": num, "updated_at": now_iso()}
    await db.erp_quotations.update_one({"id": qid}, {"$set": upd})
    await audit("erp_quotation", qid, "update", user, note=num)
    return _quote_view(await _quote(qid, bid))


class StatusIn(BaseModel):
    status: Literal["sent", "accepted", "rejected"]


@router.post("/quotations/{qid}/status")
async def quote_status(qid: str, body: StatusIn, user=Depends(erp("edit"))):
    bid = user["business_id"]
    q = _quote_view(await _quote(qid, bid))
    if body.status in ("accepted", "rejected"):
        await erp("approve").__call__(user)
    allowed = {"draft": ["sent", "accepted", "rejected"], "sent": ["accepted", "rejected"], "expired": ["accepted", "rejected"]}
    if body.status not in allowed.get(q["status"], []):
        raise HTTPException(400, f"Cannot mark a {q['status']} quotation as {body.status}")
    await db.erp_quotations.update_one({"id": qid}, {"$set": {"status": body.status, f"{body.status}_at": now_iso()}})
    await audit("erp_quotation", qid, body.status, user, note=q["number"])
    return _quote_view(await _quote(qid, bid))


class ReasonIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


@router.post("/quotations/{qid}/cancel")
async def cancel_quote(qid: str, body: ReasonIn, user=Depends(erp("cancel"))):
    q = await _quote(qid, user["business_id"])
    if q["status"] in ("cancelled", "converted"):
        raise HTTPException(400, f"Quotation is already {q['status']}")
    await db.erp_quotations.update_one({"id": qid}, {"$set": {"status": "cancelled", "cancel_reason": body.reason, "cancelled_at": now_iso()}})
    await audit("erp_quotation", qid, "cancel", user, note=body.reason)
    return {"ok": True}


@router.post("/quotations/{qid}/duplicate")
async def duplicate_quote(qid: str, user=Depends(erp("create"))):
    bid = user["business_id"]
    q = await _quote(qid, bid)
    doc = {**{k: v for k, v in q.items() if k not in ("id", "number", "status", "created_at", "cancel_reason", "converted_to", "sales_order_no", "sales_order_date", "duplicated_from")},
           "id": new_id(), "date": _today(), "number": await _quote_number(bid, "", _today()), "status": "draft",
           "created_by": user["name"], "created_at": now_iso(), "duplicated_from": q["number"]}
    for k in [k for k in doc if k.endswith("_at") and k != "created_at"]:
        doc.pop(k)
    await db.erp_quotations.insert_one({**doc})
    await audit("erp_quotation", doc["id"], "duplicate", user, note=f"from {q['number']}")
    return clean(doc)


@router.delete("/quotations/{qid}")
async def delete_quote(qid: str, user=Depends(erp("delete"))):
    q = await _quote(qid, user["business_id"])
    if q["status"] != "draft":
        raise HTTPException(400, "Only draft quotations can be deleted. Cancel it instead.")
    await db.erp_quotations.delete_one({"id": qid})
    await audit("erp_quotation", qid, "delete", user, note=q["number"])
    return {"ok": True}


class ConvertIn(BaseModel):
    to: Literal["invoice", "project", "sales_order"]
    project_name: str = ""


@router.post("/quotations/{qid}/convert")
async def convert_quote(qid: str, body: ConvertIn, user=Depends(erp("create"))):
    bid = user["business_id"]
    q = _quote_view(await _quote(qid, bid))
    if q["status"] not in ("accepted", "converted"):
        raise HTTPException(400, "Only accepted quotations can be converted")
    from erp_core import ProjectIn, create_project
    out = {}
    if body.to == "sales_order":
        if q.get("sales_order_no"):
            raise HTTPException(400, f"Already converted to sales order {q['sales_order_no']}")
        so = f"SO/{_fy_name(_today())}/{await next_seq(bid, 'so:' + _fy_name(_today())):04d}"
        await db.erp_quotations.update_one({"id": qid}, {"$set": {"sales_order_no": so, "sales_order_date": _today()}})
        out = {"sales_order_no": so}
    pid = q.get("project_id")
    if body.to == "project" or (body.to == "invoice" and not pid):
        if pid:
            raise HTTPException(400, "This quotation is already linked to a project")
        proj = await create_project(ProjectIn(name=body.project_name or q.get("subject") or f"Project for {q['client_name']}", client_id=q["client_id"],
                                              contract_value=q["totals"]["taxable"], start_date=_today(), status="Planning",
                                              description=q.get("scope_of_work", "")), user=user)
        pid = proj["id"]
        await db.erp_quotations.update_one({"id": qid}, {"$set": {"project_id": pid, "project_name": proj["name"], "project_code": proj["code"]}})
        out["project_id"] = pid
    if body.to == "invoice":
        inv = await create_invoice(InvoiceIn(date=_today(), client_id=q["client_id"], project_id=pid, template=q["template"], gst_type=q["gst_type"],
                                             items=[Line(**{k: it[k] for k in Line.model_fields}) for it in q["items"]], quotation_id=qid,
                                             notes=q.get("payment_terms", "")), user=user)
        out["invoice_id"] = inv["id"]
    await db.erp_quotations.update_one({"id": qid}, {"$set": {"status": "converted"}, "$push": {"converted_to": {"to": body.to, **out, "at": now_iso()}}})
    await audit("erp_quotation", qid, "convert", user, note=f"to {body.to}")
    return out


# ================= Invoices =================
class InvoiceIn(BaseModel):
    number: str = ""
    date: str = Field(pattern=DATE)
    due_date: str = ""
    client_id: str
    project_id: str
    quotation_id: Optional[str] = None
    template: Template = "classic"
    gst_type: Optional[Literal["intra", "inter", "none"]] = None
    items: List[Line] = Field(min_length=1)
    retention_pct: float = Field(0, ge=0, le=100)
    advance_adjust: float = Field(0, ge=0)
    deductions: float = Field(0, ge=0)
    deduction_note: str = ""
    po_reference: str = ""
    notes: str = ""
    terms: str = ""
    gst_meta: dict = {}


async def _previous_billing(bid: str, pid: str, exclude: str, before_iso: str | None) -> float:
    q = {"business_id": bid, "project_id": pid, "status": "finalized", "id": {"$ne": exclude}}
    if before_iso:
        q["finalized_at"] = {"$lt": before_iso}
    rows = await db.erp_invoices.find(q, {"totals": 1}).to_list(5000)
    return round(sum(r["totals"]["total"] for r in rows), 2)


async def _inv_doc(i: InvoiceIn, bid: str, inv_id: str = "", finalized_at: str | None = None) -> dict:
    client = await get_party(i.client_id, bid)
    if client["kind"] != "client":
        raise HTTPException(400, "Select a client")
    proj = await get_project(i.project_id, bid)
    if proj["client_id"] != i.client_id:
        raise HTTPException(400, "The project belongs to a different client")
    gt = await _gst_type(client, bid, i.gst_type)
    items, t = compute(i.items, gt)
    retention = float(D(Decimal(str(t["total"])) * Decimal(str(i.retention_pct)) / 100))
    net = round(t["total"] - retention - i.advance_adjust - i.deductions, 2)
    if net < 0:
        raise HTTPException(400, "Retention, advance and deductions are more than the invoice total")
    prev = await _previous_billing(bid, i.project_id, inv_id, finalized_at)
    due = i.due_date or i.date
    return {**i.model_dump(exclude={"number"}), "due_date": due, "gst_type": gt, "items": items,
            "totals": {**t, "retention": retention, "advance_adjust": i.advance_adjust, "deductions": i.deductions, "net_payable": net},
            "billing": {"previous": prev, "current": t["total"], "cumulative": round(prev + t["total"], 2), "contract_value": proj["contract_value"]},
            "client_name": client["company_name"], "client_ledger_id": client["ledger_id"],
            "client": {k: client.get(k, "") for k in ("company_name", "gstin", "pan", "address", "state", "contact_person", "mobile", "email")},
            "project_name": proj["name"], "project_code": proj["code"], "project_location": proj.get("location", "")}


def _inv_view(i: dict) -> dict:
    i = clean(i)
    i.pop("versions", None)
    if i["status"] == "finalized":
        bal = round(i["totals"]["net_payable"] - i.get("paid", 0) - i.get("credit_total", 0) + i.get("debit_total", 0), 2)
        i["balance"] = bal
        i["pay_status"] = "paid" if bal <= 0.005 else "partial" if i.get("paid", 0) > 0 else "unpaid"
        i["overdue"] = bal > 0.005 and i["due_date"] < _today()
    return i


async def _inv(iid: str, bid: str) -> dict:
    i = await db.erp_invoices.find_one({"id": iid, "business_id": bid}, NO_ID)
    if not i:
        raise HTTPException(404, "Invoice not found")
    return i


async def _refresh_balance(iid: str):
    i = await db.erp_invoices.find_one({"id": iid}, NO_ID)
    v = _inv_view(i)
    await db.erp_invoices.update_one({"id": iid}, {"$set": {"balance": v.get("balance", 0)}})


@router.get("/invoices")
async def list_invoices(status: Optional[str] = None, project_id: Optional[str] = None, client_id: Optional[str] = None,
                        q: Optional[str] = None, overdue: bool = False, user=Depends(erp())):
    query = {"business_id": user["business_id"], **({"project_id": project_id} if project_id else {}), **({"client_id": client_id} if client_id else {}),
             **({"status": status} if status else {})}
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        query["$or"] = [{"number": rx}, {"client_name": rx}, {"project_name": rx}, {"project_code": rx}]
    rows = [_inv_view(r) for r in await db.erp_invoices.find(query, {**NO_ID, "versions": 0}).sort("created_at", -1).to_list(5000)]
    return [r for r in rows if r.get("overdue")] if overdue else rows


@router.get("/invoices/{iid}")
async def get_invoice(iid: str, user=Depends(erp())):
    i = await _inv(iid, user["business_id"])
    notes = await db.erp_notes.find({"invoice_id": iid}, NO_ID).sort("created_at", 1).to_list(200)
    return {**_inv_view(i), "versions": clean(i.get("versions", [])), "notes_list": clean(notes)}


@router.post("/invoices")
async def create_invoice(i: InvoiceIn, user=Depends(erp("create"))):
    bid = user["business_id"]
    if i.number.strip() and await _number_used(bid, i.number.strip()):
        raise HTTPException(400, f"Invoice number {i.number.strip()} is already used")
    doc = {**(await _inv_doc(i, bid)), "id": new_id(), "business_id": bid, "number": None, "manual_number": i.number.strip(),
           "status": "draft", "paid": 0, "payments": [], "created_by": user["name"], "created_at": now_iso()}
    await db.erp_invoices.insert_one({**doc})
    await audit("erp_invoice", doc["id"], "create", user, note="draft")
    return _inv_view(doc)


async def _number_used(bid: str, n: str) -> bool:
    return bool(await db.erp_invoices.find_one({"business_id": bid, "number": n}) or await db.erp_used_numbers.find_one({"business_id": bid, "number": n}))


def _voucher_in(inv: dict, sales_ledger: str, vtype: str = "sales", lines: list | None = None, ref: str = "") -> VoucherIn:
    lines = lines if lines is not None else inv["items"]
    return VoucherIn(voucher_type=vtype, date=inv["date"], reference_no=ref or inv["number"], party_ledger_id=inv["client_ledger_id"],
                     account_ledger_id=sales_ledger, gst_type=inv["gst_type"], project_id=inv["project_id"],
                     invoice_format="service" if inv.get("template") == "gst_service" else "goods", gst_meta=inv.get("gst_meta") or {},
                     narration=f"ERP {inv['number']} · {inv['project_code']} {inv['project_name']}"[:250],
                     items=[Item(description=x["description"][:200], hsn=x.get("hsn", ""), qty=x["qty"], rate=x["net_rate"],
                                 gst_rate=x["gst_rate"] if inv["gst_type"] != "none" else 0) for x in lines])


async def _sales_ledger(bid: str) -> str:
    led = await db.ledgers.find_one({"business_id": bid, "system_key": "sales", "active": True}, NO_ID) \
        or await db.ledgers.find_one({"business_id": bid, "group": "sales", "active": True}, NO_ID)
    if not led:
        raise HTTPException(400, "No Sales ledger found in Easy Books. Create one under Sales Accounts.")
    return led["id"]


@router.put("/invoices/{iid}")
async def update_invoice(iid: str, i: InvoiceIn, user=Depends(erp("edit"))):
    bid = user["business_id"]
    before = await _inv(iid, bid)
    if before["status"] == "cancelled":
        raise HTTPException(400, "Cancelled invoices cannot be edited")
    if before["status"] == "finalized":
        await erp("edit_finalized").__call__(user)
        doc = await _inv_doc(i, bid, iid, before.get("finalized_at"))
        if before.get("paid", 0) > doc["totals"]["net_payable"] + 0.005:
            raise HTTPException(400, "New net payable is less than the payments already received")
        tmp = {**before, **doc}
        await update_voucher(before["voucher_id"], _voucher_in(tmp, await _sales_ledger(bid)), user=user)
        version = {"version": len(before.get("versions", [])) + 1, "saved_at": now_iso(), "by": user["name"],
                   "snapshot": {k: before[k] for k in ("date", "due_date", "items", "totals", "billing", "gst_type", "template") if k in before}}
        await db.erp_invoices.update_one({"id": iid}, {"$set": {**doc, "updated_at": now_iso(), "revision": version["version"]}, "$push": {"versions": version}})
        await _refresh_balance(iid)
        await audit("erp_invoice", iid, "edit_finalized", user, note=f"{before['number']} v{version['version']}")
    else:
        if i.number.strip() and i.number.strip() != before.get("manual_number") and await _number_used(bid, i.number.strip()):
            raise HTTPException(400, f"Invoice number {i.number.strip()} is already used")
        doc = await _inv_doc(i, bid, iid)
        await db.erp_invoices.update_one({"id": iid}, {"$set": {**doc, "manual_number": i.number.strip(), "updated_at": now_iso()}})
        await audit("erp_invoice", iid, "update", user, note="draft")
    return _inv_view(await _inv(iid, bid))


@router.post("/invoices/{iid}/finalize")
async def finalize_invoice(iid: str, user=Depends(erp("finalize"))):
    bid = user["business_id"]
    inv = await _inv(iid, bid)
    if inv["status"] != "draft":
        raise HTTPException(400, "Only drafts can be finalized")
    payload = InvoiceIn(**{k: inv.get(k) for k in InvoiceIn.model_fields if k not in ("number", "items")},
                        items=[Line(**{k: it[k] for k in Line.model_fields}) for it in inv["items"]])
    fin_at = now_iso()
    doc = await _inv_doc(payload, bid, iid, fin_at)
    if inv.get("manual_number"):
        number = inv["manual_number"]
        if await _number_used(bid, number):
            raise HTTPException(400, f"Invoice number {number} is already used")
    else:
        s = await erp_settings(bid)
        while True:
            number = f"{s['invoice_prefix']}/{_fy_name(inv['date'])}/{await next_seq(bid, 'inv:' + _fy_name(inv['date'])):04d}"
            if not await _number_used(bid, number):
                break
    v = await create_voucher(_voucher_in({**inv, **doc, "number": number}, await _sales_ledger(bid)), user=user)
    try:
        await db.erp_used_numbers.insert_one({"business_id": bid, "number": number, "invoice_id": iid, "at": fin_at})
    except Exception:
        await cancel_voucher(v["id"], CancelIn(reason=f"ERP finalize clash on {number}"), user=user)
        raise HTTPException(409, f"Invoice number {number} was just used by another invoice. Try again.")
    await db.erp_invoices.update_one({"id": iid}, {"$set": {**doc, "number": number, "status": "finalized", "finalized_at": fin_at,
                                                           "finalized_by": user["name"], "voucher_id": v["id"], "voucher_no": v["voucher_no"], "revision": 0}})
    await _refresh_balance(iid)
    if inv.get("quotation_id"):
        await db.erp_quotations.update_one({"id": inv["quotation_id"]}, {"$set": {"status": "converted"}})
    await audit("erp_invoice", iid, "finalize", user, note=f"{number} posted as {v['voucher_no']}")
    return _inv_view(await _inv(iid, bid))


@router.post("/invoices/{iid}/cancel")
async def cancel_inv(iid: str, body: ReasonIn, user=Depends(erp("cancel"))):
    bid = user["business_id"]
    inv = await _inv(iid, bid)
    if inv["status"] != "finalized":
        raise HTTPException(400, "Only finalized invoices can be cancelled. Delete drafts instead.")
    if inv.get("paid", 0) > 0 or inv.get("credit_total", 0) or inv.get("debit_total", 0):
        raise HTTPException(400, "This invoice has payments or notes. Cancel those first, or issue a credit note.")
    await cancel_voucher(inv["voucher_id"], CancelIn(reason=f"ERP invoice {inv['number']} cancelled: {body.reason}"), user=user)
    await db.erp_invoices.update_one({"id": iid}, {"$set": {"status": "cancelled", "cancel_reason": body.reason, "cancelled_by": user["name"],
                                                           "cancelled_at": now_iso(), "balance": 0}})
    await audit("erp_invoice", iid, "cancel", user, note=f"{inv['number']}: {body.reason}")
    return {"ok": True}


@router.delete("/invoices/{iid}")
async def delete_inv(iid: str, user=Depends(erp("delete"))):
    inv = await _inv(iid, user["business_id"])
    if inv["status"] != "draft":
        raise HTTPException(400, "Finalized invoices cannot be deleted. Cancel with a reason instead.")
    await db.erp_invoices.delete_one({"id": iid})
    await audit("erp_invoice", iid, "delete", user, note="draft deleted")
    return {"ok": True}


@router.post("/invoices/{iid}/duplicate")
async def duplicate_inv(iid: str, user=Depends(erp("create"))):
    bid = user["business_id"]
    inv = await _inv(iid, bid)
    payload = InvoiceIn(**{k: inv.get(k) for k in InvoiceIn.model_fields if k not in ("number", "items", "date", "due_date", "quotation_id")},
                        date=_today(), items=[Line(**{k: it[k] for k in Line.model_fields}) for it in inv["items"]])
    new = await create_invoice(payload, user=user)
    await db.erp_invoices.update_one({"id": new["id"]}, {"$set": {"duplicated_from": inv.get("number") or "draft"}})
    return new


class PaymentIn(BaseModel):
    date: str = Field(pattern=DATE)
    amount: float = Field(gt=0)
    ledger_id: str
    reference: str = ""


@router.post("/invoices/{iid}/payments")
async def add_payment(iid: str, p: PaymentIn, user=Depends(erp("finalize"))):
    bid = user["business_id"]
    inv = _inv_view(await _inv(iid, bid))
    if inv["status"] != "finalized":
        raise HTTPException(400, "Payments can only be recorded on finalized invoices")
    if p.amount > inv["balance"] + 0.005:
        raise HTTPException(400, f"Amount is more than the balance due (₹{inv['balance']:,.2f})")
    led = await db.ledgers.find_one({"id": p.ledger_id, "business_id": bid, "group": {"$in": ["cash", "bank"]}, "active": True}, NO_ID)
    if not led:
        raise HTTPException(400, "Select a Cash or Bank ledger")
    v = await create_voucher(VoucherIn(voucher_type="receipt", date=p.date, reference_no=p.reference or inv["number"], project_id=inv["project_id"],
                                       narration=f"Payment for {inv['number']} · {inv['project_code']}",
                                       entries=[Entry(ledger_id=led["id"], debit=p.amount), Entry(ledger_id=inv["client_ledger_id"], credit=p.amount)]), user=user)
    pay = {"id": new_id(), **p.model_dump(), "mode": led["name"], "voucher_id": v["id"], "voucher_no": v["voucher_no"], "by": user["name"], "at": now_iso()}
    await db.erp_invoices.update_one({"id": iid}, {"$inc": {"paid": p.amount}, "$push": {"payments": pay}})
    await _refresh_balance(iid)
    await audit("erp_invoice", iid, "payment", user, note=f"₹{p.amount:,.2f} via {led['name']} ({v['voucher_no']})")
    return _inv_view(await _inv(iid, bid))


class NoteIn(BaseModel):
    kind: Literal["credit", "debit"]
    date: str = Field(pattern=DATE)
    reason: str = Field(min_length=3, max_length=300)
    items: List[Line] = Field(min_length=1)


@router.post("/invoices/{iid}/notes")
async def add_note(iid: str, n: NoteIn, user=Depends(erp("finalize"))):
    bid = user["business_id"]
    inv = _inv_view(await _inv(iid, bid))
    if inv["status"] != "finalized":
        raise HTTPException(400, "Notes can only be issued against finalized invoices")
    items, totals = compute(n.items, inv["gst_type"])
    if n.kind == "credit" and totals["total"] > inv["balance"] + 0.005:
        raise HTTPException(400, f"Credit note is more than the balance due (₹{inv['balance']:,.2f})")
    pre = "ECN" if n.kind == "credit" else "EDN"
    number = f"{pre}/{_fy_name(n.date)}/{await next_seq(bid, pre + ':' + _fy_name(n.date)):04d}"
    v = await create_voucher(_voucher_in({**inv, "date": n.date}, await _sales_ledger(bid), "credit_note" if n.kind == "credit" else "sales",
                                         items, ref=f"{number} against {inv['number']}"), user=user)
    doc = {"id": new_id(), "business_id": bid, "invoice_id": iid, "invoice_number": inv["number"], "project_id": inv["project_id"], "client_id": inv["client_id"],
           "kind": n.kind, "number": number, "date": n.date, "reason": n.reason, "items": items, "totals": totals, "status": "active",
           "voucher_id": v["id"], "voucher_no": v["voucher_no"], "created_by": user["name"], "created_at": now_iso()}
    await db.erp_notes.insert_one({**doc})
    await db.erp_invoices.update_one({"id": iid}, {"$inc": {f"{n.kind}_total": totals["total"]}})
    await _refresh_balance(iid)
    await audit("erp_invoice", iid, f"{n.kind}_note", user, note=f"{number} ₹{totals['total']:,.2f}: {n.reason}")
    return clean(doc)


@router.post("/invoices/{iid}/email")
async def email_invoice(iid: str, user=Depends(erp("edit"))):
    from html import escape
    bid = user["business_id"]
    inv = _inv_view(await _inv(iid, bid))
    if inv["status"] != "finalized":
        raise HTTPException(400, "Finalize the invoice before sending it")
    to = inv["client"].get("email")
    if not to:
        raise HTTPException(400, "This client has no email address. Add it in Clients & Vendors.")
    s = await db.settings.find_one({"business_id": bid}, NO_ID) or {}
    co = escape(s.get("company_name", ""))
    rows = "".join(f'<tr><td style="padding:6px;border:1px solid #e2e8f0">{escape(x["description"])}</td><td style="padding:6px;border:1px solid #e2e8f0;text-align:right">{x["qty"]:g}</td>'
                   f'<td style="padding:6px;border:1px solid #e2e8f0;text-align:right">₹{x["total"]:,.2f}</td></tr>' for x in inv["items"])
    html = (f'<table role="presentation" width="100%"><tr><td style="padding:24px;font-family:Arial,sans-serif;color:#0f172a;font-size:14px">'
            f'<p>Dear {escape(inv["client_name"])},</p><p>Please find the details of invoice <b>{escape(inv["number"])}</b> dated {escape(inv["date"])} '
            f'for project <b>{escape(inv["project_code"])} {escape(inv["project_name"])}</b>.</p>'
            f'<table style="border-collapse:collapse;width:100%">{rows}</table>'
            f'<p>Invoice total: <b>₹{inv["totals"]["total"]:,.2f}</b><br>Net payable: <b>₹{inv["totals"]["net_payable"]:,.2f}</b><br>'
            f'Balance due: <b>₹{inv["balance"]:,.2f}</b> by {escape(inv["due_date"])}</p>'
            f'<p>Regards,<br>{co}</p><p style="font-size:12px;color:#64748b">Sent from {co} using Easy Books by Hannusoft. '
            f'We never ask for your password or payment details by email.</p></td></tr></table>')
    eid = await send_email(to=to, subject=f"Invoice {inv['number']} from {s.get('company_name', '')}", html=html)
    await db.erp_invoices.update_one({"id": iid}, {"$push": {"emails": {"to": to, "id": eid, "at": now_iso()}}})
    await audit("erp_invoice", iid, "email", user, note=to)
    return {"ok": True, "to": to}
