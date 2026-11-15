import re
from contextlib import asynccontextmanager
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from accounting import Entry, Item, VoucherIn
from db import db, NO_ID, new_id, now_iso, audit, clean
from emailer import send_email
from erp_core import erp, erp_settings, get_party, get_project, next_seq
from erp_sales import DATE, Line, ReasonIn, Template, _fy_name, _gst_type, _today, compute
from routes_vouchers import CancelIn, cancel_voucher, create_voucher

router = APIRouter(prefix="/api/erp")
COLL = {"pr": "erp_prs", "rfq": "erp_rfqs", "po": "erp_pos", "grn": "erp_grns", "bill": "erp_bills", "expense": "erp_expenses"}
PREFIX = {"pr": "PR", "rfq": "RFQ", "po": "PO", "grn": "GRN", "bill": "PB", "expense": "EXP"}
EXPENSE_CATEGORIES = ["Labour", "Site Expenses", "Transport", "Travel", "Food & Lodging", "Equipment Hire", "Subcontract", "Consumables",
                      "Fuel", "Professional Fees", "Office", "Miscellaneous"]


def col(kind: str):
    return db[COLL[kind]]


@asynccontextmanager
async def busy(kind: str, did: str):
    if not await col(kind).find_one_and_update({"id": did, "busy": {"$ne": True}}, {"$set": {"busy": True}}):
        raise HTTPException(409, "This document is already being processed. Please wait a moment.")
    try:
        yield
    finally:
        await col(kind).update_one({"id": did}, {"$unset": {"busy": ""}})


async def auto_no(bid: str, kind: str, d: str, manual: str = "", exclude: str = "") -> str:
    if manual.strip():
        n = manual.strip()
        if await col(kind).find_one({"business_id": bid, "number": n, "id": {"$ne": exclude}}):
            raise HTTPException(400, f"Number {n} is already used")
        return n
    while True:
        n = f"{PREFIX[kind]}/{_fy_name(d)}/{await next_seq(bid, kind + ':' + _fy_name(d)):04d}"
        if not await col(kind).find_one({"business_id": bid, "number": n}):
            return n


async def get_doc(kind: str, did: str, bid: str) -> dict:
    d = await col(kind).find_one({"id": did, "business_id": bid}, NO_ID)
    if not d:
        raise HTTPException(404, "Document not found")
    return d


async def _vendor(vid: str, bid: str) -> dict:
    v = await get_party(vid, bid)
    if v["kind"] != "vendor":
        raise HTTPException(400, "Select a vendor")
    return v


def _party_snap(p: dict) -> dict:
    return {k: p.get(k, "") for k in ("company_name", "gstin", "pan", "address", "state", "contact_person", "mobile", "email")}


async def _list(kind: str, user: dict, status, project_id, q, extra=None):
    query = {"business_id": user["business_id"], **({"status": status} if status else {}), **({"project_id": project_id} if project_id else {}), **(extra or {})}
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        query["$or"] = [{"number": rx}, {"project_name": rx}, {"project_code": rx}, {"vendor_name": rx}, {"vendor_invoice_no": rx}, {"paid_to": rx}, {"category": rx}]
    return clean(await col(kind).find(query, NO_ID).sort("created_at", -1).to_list(5000))


async def _set_status(kind: str, did: str, user: dict, status: str, note: str = "", **extra):
    await col(kind).update_one({"id": did}, {"$set": {"status": status, f"{status}_at": now_iso(), f"{status}_by": user["name"], **extra}})
    await audit(f"erp_{kind}", did, status, user, note=note)


async def _proj_snap(pid: str, bid: str) -> dict:
    p = await get_project(pid, bid)
    return {"project_id": pid, "project_name": p["name"], "project_code": p["code"], "project_location": p.get("location", "")}


# ================= Purchase Requisition =================
class ReqLine(BaseModel):
    description: str = Field(min_length=1, max_length=300)
    unit: str = ""
    qty: float = Field(gt=0)
    notes: str = ""


class PRIn(BaseModel):
    project_id: str
    date: str = Field(pattern=DATE)
    required_by: str = ""
    items: List[ReqLine] = Field(min_length=1)
    remarks: str = ""


@router.get("/prs")
async def list_prs(status: Optional[str] = None, project_id: Optional[str] = None, q: Optional[str] = None, user=Depends(erp())):
    return await _list("pr", user, status, project_id, q)


@router.get("/prs/{did}")
async def get_pr(did: str, user=Depends(erp())):
    return clean(await get_doc("pr", did, user["business_id"]))


@router.post("/prs")
async def create_pr(b: PRIn, user=Depends(erp("create"))):
    bid = user["business_id"]
    doc = {**b.model_dump(), **(await _proj_snap(b.project_id, bid)), "id": new_id(), "business_id": bid, "number": await auto_no(bid, "pr", b.date),
           "status": "draft", "requested_by": user["name"], "created_at": now_iso()}
    await col("pr").insert_one({**doc})
    await audit("erp_pr", doc["id"], "create", user, note=doc["number"])
    return clean(doc)


@router.put("/prs/{did}")
async def update_pr(did: str, b: PRIn, user=Depends(erp("edit"))):
    bid = user["business_id"]
    d = await get_doc("pr", did, bid)
    if d["status"] not in ("draft", "rejected"):
        raise HTTPException(400, f"A {d['status']} requisition cannot be edited")
    await col("pr").update_one({"id": did}, {"$set": {**b.model_dump(), **(await _proj_snap(b.project_id, bid)), "status": "draft", "updated_at": now_iso()}})
    await audit("erp_pr", did, "update", user, note=d["number"])
    return clean(await get_doc("pr", did, bid))


class PRAction(BaseModel):
    action: Literal["submit", "approve", "reject", "close"]
    note: str = ""


@router.post("/prs/{did}/action")
async def pr_action(did: str, b: PRAction, user=Depends(erp("edit"))):
    d = await get_doc("pr", did, user["business_id"])
    if b.action in ("approve", "reject"):
        await erp("approve")(user)
    flow = {"submit": (["draft"], "submitted"), "approve": (["submitted"], "approved"), "reject": (["submitted"], "rejected"), "close": (["approved", "rfq"], "closed")}
    allowed, new = flow[b.action]
    if d["status"] not in allowed:
        raise HTTPException(400, f"Cannot {b.action} a {d['status']} requisition")
    await _set_status("pr", did, user, new, b.note, approval_note=b.note)
    return clean(await get_doc("pr", did, user["business_id"]))


@router.post("/prs/{did}/cancel")
async def cancel_pr(did: str, b: ReasonIn, user=Depends(erp("cancel"))):
    d = await get_doc("pr", did, user["business_id"])
    if d["status"] in ("cancelled", "closed"):
        raise HTTPException(400, f"Requisition is already {d['status']}")
    await _set_status("pr", did, user, "cancelled", b.reason, cancel_reason=b.reason)
    return {"ok": True}


@router.delete("/prs/{did}")
async def delete_pr(did: str, user=Depends(erp("delete"))):
    d = await get_doc("pr", did, user["business_id"])
    if d["status"] != "draft":
        raise HTTPException(400, "Only drafts can be deleted. Cancel it instead.")
    await col("pr").delete_one({"id": did})
    await audit("erp_pr", did, "delete", user, note=d["number"])
    return {"ok": True}


# ================= RFQ, vendor quotations, comparative statement =================
class RFQIn(BaseModel):
    project_id: str
    pr_id: Optional[str] = None
    date: str = Field(pattern=DATE)
    due_date: str = ""
    vendor_ids: List[str] = Field(min_length=1)
    items: List[ReqLine] = Field(min_length=1)
    terms: str = ""


@router.get("/rfqs")
async def list_rfqs(status: Optional[str] = None, project_id: Optional[str] = None, q: Optional[str] = None, user=Depends(erp())):
    return await _list("rfq", user, status, project_id, q)


@router.post("/rfqs")
async def create_rfq(b: RFQIn, user=Depends(erp("create"))):
    bid = user["business_id"]
    if b.pr_id:
        pr = await get_doc("pr", b.pr_id, bid)
        if pr["status"] not in ("approved", "rfq"):
            raise HTTPException(400, "The requisition must be approved before sending an RFQ")
        if pr["project_id"] != b.project_id:
            raise HTTPException(400, "The requisition belongs to a different project")
    vendors = [await _vendor(v, bid) for v in dict.fromkeys(b.vendor_ids)]
    doc = {**b.model_dump(), **(await _proj_snap(b.project_id, bid)), "id": new_id(), "business_id": bid, "number": await auto_no(bid, "rfq", b.date),
           "vendor_ids": [v["id"] for v in vendors], "vendors": [{"id": v["id"], "company_name": v["company_name"], "email": v.get("email", ""), "mobile": v.get("mobile", "")} for v in vendors],
           "pr_number": pr["number"] if b.pr_id else "", "status": "open", "created_by": user["name"], "created_at": now_iso()}
    await col("rfq").insert_one({**doc})
    if b.pr_id:
        await col("pr").update_one({"id": b.pr_id}, {"$set": {"status": "rfq"}, "$push": {"rfqs": doc["number"]}})
    await audit("erp_rfq", doc["id"], "create", user, note=doc["number"])
    return clean(doc)


def _compare(rfq: dict, quotes: list) -> dict:
    rows = []
    for i, it in enumerate(rfq["items"]):
        cells = [{"vendor_id": q["vendor_id"], "vendor_name": q["vendor_name"], **q["items"][i]} for q in quotes]
        best = min(cells, key=lambda c: c["net_rate"]) if cells else None
        rows.append({**it, "quotes": cells, "lowest_vendor_id": best["vendor_id"] if best else None})
    totals = sorted([{"quote_id": q["id"], "vendor_id": q["vendor_id"], "vendor_name": q["vendor_name"], "taxable": q["totals"]["taxable"], "total": q["totals"]["total"],
                      "delivery_days": q.get("delivery_days"), "payment_terms": q.get("payment_terms", "")} for q in quotes], key=lambda x: x["total"])
    return {"rows": rows, "vendors": totals, "lowest_quote_id": totals[0]["quote_id"] if totals else None}


@router.get("/rfqs/{did}")
async def get_rfq(did: str, user=Depends(erp())):
    rfq = await get_doc("rfq", did, user["business_id"])
    quotes = clean(await db.erp_vendor_quotes.find({"rfq_id": did}, NO_ID).sort("totals.total", 1).to_list(100))
    return {**clean(rfq), "quotes": quotes, "comparison": _compare(rfq, quotes)}


class QuoteLine(BaseModel):
    rate: float = Field(ge=0)
    discount: float = Field(0, ge=0, le=100)
    gst_rate: float = Field(18, ge=0, le=100)


class VQuoteIn(BaseModel):
    vendor_id: str
    quote_ref: str = ""
    date: str = Field(pattern=DATE)
    lines: List[QuoteLine]
    delivery_days: int = Field(0, ge=0, le=3650)
    payment_terms: str = ""
    notes: str = ""


@router.post("/rfqs/{did}/quotes")
async def add_vendor_quote(did: str, b: VQuoteIn, user=Depends(erp("create"))):
    bid = user["business_id"]
    rfq = await get_doc("rfq", did, bid)
    if rfq["status"] != "open":
        raise HTTPException(400, f"RFQ is {rfq['status']}; vendor quotations can no longer be changed")
    if b.vendor_id not in rfq["vendor_ids"]:
        raise HTTPException(400, "This vendor was not invited in the RFQ")
    if len(b.lines) != len(rfq["items"]):
        raise HTTPException(400, "Enter a rate for every RFQ item")
    v = await _vendor(b.vendor_id, bid)
    lines = [Line(description=it["description"], unit=it.get("unit", ""), qty=it["qty"], rate=ln.rate, discount=ln.discount, gst_rate=ln.gst_rate)
             for it, ln in zip(rfq["items"], b.lines)]
    gt = await _gst_type(v, bid, None)
    items, totals = compute(lines, gt)
    doc = {**b.model_dump(exclude={"lines"}), "rfq_id": did, "business_id": bid, "vendor_name": v["company_name"], "gst_type": gt, "items": items, "totals": totals,
           "updated_at": now_iso(), "by": user["name"]}
    await db.erp_vendor_quotes.update_one({"rfq_id": did, "vendor_id": b.vendor_id}, {"$set": doc, "$setOnInsert": {"id": new_id()}}, upsert=True)
    await audit("erp_rfq", did, "vendor_quote", user, note=f"{v['company_name']} ₹{totals['total']:,.2f}")
    return await get_rfq(did, user=user)


class SelectIn(BaseModel):
    quote_id: str
    reason: str = ""


@router.post("/rfqs/{did}/select")
async def select_vendor(did: str, b: SelectIn, user=Depends(erp("approve"))):
    rfq = await get_doc("rfq", did, user["business_id"])
    q = await db.erp_vendor_quotes.find_one({"id": b.quote_id, "rfq_id": did}, NO_ID)
    if not q:
        raise HTTPException(404, "Vendor quotation not found")
    if rfq["status"] not in ("open", "selected"):
        raise HTTPException(400, f"RFQ is {rfq['status']}")
    cmp = _compare(rfq, await db.erp_vendor_quotes.find({"rfq_id": did}, NO_ID).to_list(100))
    if cmp["lowest_quote_id"] != b.quote_id and len(b.reason.strip()) < 3:
        raise HTTPException(400, "This is not the lowest quotation. Enter a reason for selecting it.")
    await _set_status("rfq", did, user, "selected", f"{q['vendor_name']} {b.reason}".strip(), selected_quote_id=b.quote_id,
                      selected_vendor_id=q["vendor_id"], selected_vendor_name=q["vendor_name"], selection_reason=b.reason, lowest=cmp["lowest_quote_id"] == b.quote_id)
    return await get_rfq(did, user=user)


@router.post("/rfqs/{did}/send")
async def send_rfq(did: str, user=Depends(erp("edit"))):
    from html import escape
    bid = user["business_id"]
    rfq = await get_doc("rfq", did, bid)
    s = await db.settings.find_one({"business_id": bid}, NO_ID) or {}
    co = escape(s.get("company_name", ""))
    rows = "".join(f'<tr><td style="padding:6px;border:1px solid #e2e8f0">{escape(i["description"])}</td><td style="padding:6px;border:1px solid #e2e8f0">{i["qty"]:g} {escape(i.get("unit", ""))}</td></tr>' for i in rfq["items"])
    sent = []
    for v in [v for v in rfq["vendors"] if v.get("email")]:
        html = (f'<table role="presentation" width="100%"><tr><td style="padding:24px;font-family:Arial,sans-serif;font-size:14px;color:#0f172a">'
                f'<p>Dear {escape(v["company_name"])},</p><p>Please send your best quotation for project <b>{escape(rfq["project_code"])} {escape(rfq["project_name"])}</b> '
                f'(RFQ {escape(rfq["number"])}) by {escape(rfq.get("due_date") or "the earliest")}, including rate, discount, GST, delivery time and payment terms.</p>'
                f'<table style="border-collapse:collapse">{rows}</table><p>{escape(rfq.get("terms", ""))}</p><p>Regards,<br>{co}</p>'
                f'<p style="font-size:12px;color:#64748b">Sent using Easy Books by Hannusoft. We never ask for your password or payment details by email.</p></td></tr></table>')
        await send_email(to=v["email"], subject=f"Request for quotation {rfq['number']} from {s.get('company_name', '')}", html=html)
        sent.append(v["email"])
    if not sent:
        raise HTTPException(400, "None of the invited vendors has an email address")
    await col("rfq").update_one({"id": did}, {"$set": {"sent_at": now_iso()}, "$push": {"sent_to": {"$each": sent}}})
    await audit("erp_rfq", did, "send", user, note=", ".join(sent))
    return {"sent": sent}


@router.post("/rfqs/{did}/cancel")
async def cancel_rfq(did: str, b: ReasonIn, user=Depends(erp("cancel"))):
    rfq = await get_doc("rfq", did, user["business_id"])
    if rfq["status"] in ("cancelled", "ordered"):
        raise HTTPException(400, f"RFQ is already {rfq['status']}")
    await _set_status("rfq", did, user, "cancelled", b.reason, cancel_reason=b.reason)
    return {"ok": True}


@router.post("/rfqs/{did}/create-po")
async def rfq_to_po(did: str, user=Depends(erp("create"))):
    async with busy("rfq", did):
        bid = user["business_id"]
        rfq = await get_doc("rfq", did, bid)
        if rfq["status"] != "selected":
            raise HTTPException(400, "Select a vendor in the comparative statement first")
        q = await db.erp_vendor_quotes.find_one({"id": rfq["selected_quote_id"]}, NO_ID)
        po = await create_po(POIn(date=_today(), project_id=rfq["project_id"], vendor_id=q["vendor_id"], rfq_id=did, gst_type=q["gst_type"],
                                  payment_terms=q.get("payment_terms", ""), delivery_date="",
                                  items=[Line(**{k: it[k] for k in Line.model_fields}) for it in q["items"]]), user=user)
        await col("rfq").update_one({"id": did}, {"$set": {"status": "ordered", "po_id": po["id"], "po_number": po["number"]}})
        await audit("erp_rfq", did, "ordered", user, note=po["number"])
        return po


# ================= Purchase Orders =================
class POIn(BaseModel):
    number: str = ""
    date: str = Field(pattern=DATE)
    project_id: str
    vendor_id: str
    rfq_id: Optional[str] = None
    delivery_date: str = ""
    delivery_address: str = ""
    template: Template = "classic"
    gst_type: Optional[Literal["intra", "inter", "none"]] = None
    items: List[Line] = Field(min_length=1)
    payment_terms: str = ""
    terms: str = ""


async def _po_doc(b: POIn, bid: str) -> dict:
    v = await _vendor(b.vendor_id, bid)
    gt = await _gst_type(v, bid, b.gst_type)
    items, totals = compute(b.items, gt)
    return {**b.model_dump(exclude={"number"}), **(await _proj_snap(b.project_id, bid)), "gst_type": gt, "items": items, "totals": totals,
            "vendor_name": v["company_name"], "client": _party_snap(v), "vendor": _party_snap(v)}


async def _po_view(po: dict) -> dict:
    grns = await col("grn").find({"po_id": po["id"], "status": "posted"}, NO_ID).to_list(500)
    bills = await col("bill").find({"po_id": po["id"], "status": {"$in": ["draft", "posted"]}}, NO_ID).to_list(500)
    for i, it in enumerate(po["items"]):
        acc = sum(ln["accepted"] for g in grns for ln in g["lines"] if ln["line"] == i)
        rej = sum(ln["rejected"] for g in grns for ln in g["lines"] if ln["line"] == i)
        billed = sum(ln["qty"] for b in bills for ln in b["items"] if ln.get("po_line") == i and b["status"] == "posted")
        it.update({"accepted": acc, "rejected": rej, "pending": round(it["qty"] - acc, 4), "billed_qty": billed})
    pend = sum(it["pending"] for it in po["items"])
    po["receipt_status"] = "not_received" if not grns else "received" if pend <= 0 else "partial"
    po["received_value"] = round(sum(it["accepted"] * it["net_rate"] for it in po["items"]), 2)
    return clean(po)


@router.get("/pos")
async def list_pos(status: Optional[str] = None, project_id: Optional[str] = None, q: Optional[str] = None, pending: bool = False, user=Depends(erp())):
    rows = [await _po_view(p) for p in await _list("po", user, status, project_id, q)]
    return [r for r in rows if r["status"] == "approved" and r["receipt_status"] != "received"] if pending else rows


@router.get("/pos/{did}")
async def get_po(did: str, user=Depends(erp())):
    bid = user["business_id"]
    po = await _po_view(await get_doc("po", did, bid))
    po["grns"] = clean(await col("grn").find({"po_id": did}, NO_ID).sort("created_at", 1).to_list(500))
    po["bills"] = clean(await col("bill").find({"po_id": did}, {**NO_ID, "items": 0}).sort("created_at", 1).to_list(500))
    return po


@router.post("/pos")
async def create_po(b: POIn, user=Depends(erp("create"))):
    bid = user["business_id"]
    doc = {**(await _po_doc(b, bid)), "id": new_id(), "business_id": bid, "number": await auto_no(bid, "po", b.date, b.number),
           "status": "draft", "created_by": user["name"], "created_at": now_iso()}
    await col("po").insert_one({**doc})
    await audit("erp_po", doc["id"], "create", user, note=doc["number"])
    return clean(doc)


@router.put("/pos/{did}")
async def update_po(did: str, b: POIn, user=Depends(erp("edit"))):
    bid = user["business_id"]
    d = await get_doc("po", did, bid)
    if d["status"] != "draft":
        raise HTTPException(400, "Only draft purchase orders can be edited. Duplicate it instead.")
    num = await auto_no(bid, "po", b.date, b.number, did) if b.number.strip() and b.number.strip() != d["number"] else d["number"]
    await col("po").update_one({"id": did}, {"$set": {**(await _po_doc(b, bid)), "number": num, "updated_at": now_iso()}})
    await audit("erp_po", did, "update", user, note=num)
    return await get_po(did, user=user)


@router.post("/pos/{did}/approve")
async def approve_po(did: str, user=Depends(erp("approve"))):
    async with busy("po", did):
        d = await get_doc("po", did, user["business_id"])
        if d["status"] != "draft":
            raise HTTPException(400, "Only drafts can be approved")
        await _set_status("po", did, user, "approved", d["number"])
        return await get_po(did, user=user)


@router.post("/pos/{did}/cancel")
async def cancel_po(did: str, b: ReasonIn, user=Depends(erp("cancel"))):
    d = await get_doc("po", did, user["business_id"])
    if d["status"] == "cancelled":
        raise HTTPException(400, "Already cancelled")
    if await col("grn").count_documents({"po_id": did, "status": "posted"}) or await col("bill").count_documents({"po_id": did, "status": {"$ne": "cancelled"}}):
        raise HTTPException(400, "Goods have been received or billed against this PO. Close it instead of cancelling.")
    await _set_status("po", did, user, "cancelled", b.reason, cancel_reason=b.reason)
    return {"ok": True}


@router.post("/pos/{did}/close")
async def close_po(did: str, user=Depends(erp("approve"))):
    d = await get_doc("po", did, user["business_id"])
    if d["status"] != "approved":
        raise HTTPException(400, "Only approved purchase orders can be closed")
    await _set_status("po", did, user, "closed", d["number"])
    return await get_po(did, user=user)


@router.post("/pos/{did}/duplicate")
async def duplicate_po(did: str, user=Depends(erp("create"))):
    d = await get_doc("po", did, user["business_id"])
    return await create_po(POIn(**{k: d.get(k) for k in POIn.model_fields if k not in ("number", "items", "date", "rfq_id")}, date=_today(),
                                items=[Line(**{k: it[k] for k in Line.model_fields}) for it in d["items"]]), user=user)


@router.delete("/pos/{did}")
async def delete_po(did: str, user=Depends(erp("delete"))):
    d = await get_doc("po", did, user["business_id"])
    if d["status"] != "draft":
        raise HTTPException(400, "Only drafts can be deleted. Cancel it instead.")
    await col("po").delete_one({"id": did})
    await audit("erp_po", did, "delete", user, note=d["number"])
    return {"ok": True}


# ================= GRN =================
class GRNLine(BaseModel):
    line: int = Field(ge=0)
    received: float = Field(ge=0)
    accepted: float = Field(ge=0)
    rejected: float = Field(0, ge=0)
    remarks: str = ""


class GRNIn(BaseModel):
    po_id: str
    date: str = Field(pattern=DATE)
    challan_no: str = ""
    vehicle_no: str = ""
    lines: List[GRNLine] = Field(min_length=1)
    notes: str = ""


@router.get("/grns")
async def list_grns(project_id: Optional[str] = None, q: Optional[str] = None, po_id: Optional[str] = None, user=Depends(erp())):
    return await _list("grn", user, None, project_id, q, {"po_id": po_id} if po_id else None)


@router.post("/grns")
async def create_grn(b: GRNIn, user=Depends(erp("create"))):
    async with busy("po", b.po_id):
        bid = user["business_id"]
        po = await _po_view(await get_doc("po", b.po_id, bid))
        if po["status"] != "approved":
            raise HTTPException(400, "Goods can only be received against an approved purchase order")
        lines = []
        for ln in b.lines:
            if ln.line >= len(po["items"]):
                raise HTTPException(400, "Invalid PO line")
            if abs(ln.accepted + ln.rejected - ln.received) > 0.0001:
                raise HTTPException(400, "Accepted + rejected must equal received quantity")
            it = po["items"][ln.line]
            if ln.received > it["pending"] + 0.0001:
                raise HTTPException(400, f"'{it['description']}': received {ln.received:g} is more than pending {it['pending']:g}")
            if ln.received > 0:
                lines.append({**ln.model_dump(), "description": it["description"], "unit": it.get("unit", ""), "ordered": it["qty"],
                              "pending_after": round(it["pending"] - ln.accepted, 4), "net_rate": it["net_rate"]})
        if not lines:
            raise HTTPException(400, "Enter the received quantity for at least one item")
        doc = {**b.model_dump(exclude={"lines"}), "id": new_id(), "business_id": bid, "number": await auto_no(bid, "grn", b.date), "lines": lines,
               "po_number": po["number"], "project_id": po["project_id"], "project_name": po["project_name"], "project_code": po["project_code"],
               "vendor_id": po["vendor_id"], "vendor_name": po["vendor_name"], "status": "posted", "created_by": user["name"], "created_at": now_iso(),
               "accepted_value": round(sum(ln["accepted"] * ln["net_rate"] for ln in lines), 2)}
        await col("grn").insert_one({**doc})
        await audit("erp_grn", doc["id"], "create", user, note=f"{doc['number']} against {po['number']}")
        await audit("erp_po", po["id"], "grn", user, note=doc["number"])
        return clean(doc)


@router.post("/grns/{did}/cancel")
async def cancel_grn(did: str, b: ReasonIn, user=Depends(erp("cancel"))):
    g = await get_doc("grn", did, user["business_id"])
    if g["status"] != "posted":
        raise HTTPException(400, "Already cancelled")
    po = await _po_view(await get_doc("po", g["po_id"], user["business_id"]))
    for ln in g["lines"]:
        it = po["items"][ln["line"]]
        if it["billed_qty"] > it["accepted"] - ln["accepted"] + 0.0001:
            raise HTTPException(400, "Items from this GRN are already billed. Cancel the purchase bill first.")
    await _set_status("grn", did, user, "cancelled", b.reason, cancel_reason=b.reason)
    return {"ok": True}


# ================= Purchase Bills =================
class BillLine(Line):
    po_line: Optional[int] = None


class BillIn(BaseModel):
    vendor_id: str
    project_id: str
    po_id: Optional[str] = None
    grn_ids: List[str] = []
    vendor_invoice_no: str = Field(max_length=40)
    vendor_invoice_date: str = Field(pattern=DATE)
    due_date: str = ""
    gst_type: Optional[Literal["intra", "inter", "none"]] = None
    items: List[BillLine] = Field(min_length=1)
    notes: str = ""


async def _bill_doc(b: BillIn, bid: str, exclude: str = "") -> dict:
    if not b.vendor_invoice_no.strip():
        raise HTTPException(400, "Vendor invoice number is required")
    v = await _vendor(b.vendor_id, bid)
    dup = await col("bill").find_one({"business_id": bid, "vendor_id": b.vendor_id, "status": {"$ne": "cancelled"}, "id": {"$ne": exclude},
                                      "vendor_invoice_lower": b.vendor_invoice_no.strip().lower()})
    if dup:
        raise HTTPException(400, f"Vendor invoice {b.vendor_invoice_no} from {v['company_name']} is already entered ({dup['number']})")
    po = None
    if b.po_id:
        po = await _po_view(await get_doc("po", b.po_id, bid))
        if po["vendor_id"] != b.vendor_id or po["project_id"] != b.project_id:
            raise HTTPException(400, "The purchase order is for a different vendor or project")
        if po["status"] not in ("approved", "closed"):
            raise HTTPException(400, "Bills can only be linked to an approved purchase order")
        others = await col("bill").find({"po_id": b.po_id, "status": {"$in": ["draft", "posted"]}, "id": {"$ne": exclude}}, NO_ID).to_list(500)
        for ln in b.items:
            if ln.po_line is None:
                continue
            if ln.po_line >= len(po["items"]):
                raise HTTPException(400, "Invalid PO line")
            it = po["items"][ln.po_line]
            already = sum(x["qty"] for o in others for x in o["items"] if x.get("po_line") == ln.po_line)
            if ln.qty + already > it["accepted"] + 0.0001:
                raise HTTPException(400, f"'{it['description']}': billing {ln.qty + already:g} but only {it['accepted']:g} accepted in GRNs")
    for g in b.grn_ids:
        grn = await get_doc("grn", g, bid)
        if grn["po_id"] != b.po_id:
            raise HTTPException(400, "GRN does not belong to the selected PO")
    gt = await _gst_type(v, bid, b.gst_type)
    items, totals = compute([Line(**ln.model_dump(exclude={"po_line"})) for ln in b.items], gt)
    for it, ln in zip(items, b.items):
        it["po_line"] = ln.po_line
    return {**b.model_dump(exclude={"items"}), **(await _proj_snap(b.project_id, bid)), "vendor_invoice_lower": b.vendor_invoice_no.strip().lower(),
            "due_date": b.due_date or b.vendor_invoice_date, "gst_type": gt, "items": items, "totals": totals, "vendor_name": v["company_name"],
            "vendor_ledger_id": v["ledger_id"], "vendor": _party_snap(v), "po_number": po["number"] if po else ""}


def _bill_view(b: dict) -> dict:
    b = clean(b)
    if b["status"] == "posted":
        b["balance"] = round(b["totals"]["total"] - b.get("paid", 0), 2)
        b["pay_status"] = "paid" if b["balance"] <= 0.005 else "partial" if b.get("paid", 0) else "unpaid"
        b["overdue"] = b["balance"] > 0.005 and b["due_date"] < _today()
    return b


@router.get("/bills")
async def list_bills(status: Optional[str] = None, project_id: Optional[str] = None, q: Optional[str] = None, pending: bool = False, user=Depends(erp())):
    rows = [_bill_view(b) for b in await _list("bill", user, status, project_id, q)]
    return [r for r in rows if r.get("balance", 0) > 0.005] if pending else rows


@router.get("/bills/{did}")
async def get_bill(did: str, user=Depends(erp())):
    return _bill_view(await get_doc("bill", did, user["business_id"]))


@router.post("/bills")
async def create_bill(b: BillIn, user=Depends(erp("create"))):
    bid = user["business_id"]
    doc = {**(await _bill_doc(b, bid)), "id": new_id(), "business_id": bid, "number": await auto_no(bid, "bill", b.vendor_invoice_date),
           "status": "draft", "paid": 0, "payments": [], "created_by": user["name"], "created_at": now_iso()}
    await col("bill").insert_one({**doc})
    await audit("erp_bill", doc["id"], "create", user, note=f"{doc['number']} ({b.vendor_invoice_no})")
    return _bill_view(doc)


@router.put("/bills/{did}")
async def update_bill(did: str, b: BillIn, user=Depends(erp("edit"))):
    bid = user["business_id"]
    d = await get_doc("bill", did, bid)
    if d["status"] != "draft":
        raise HTTPException(400, "Only draft bills can be edited")
    await col("bill").update_one({"id": did}, {"$set": {**(await _bill_doc(b, bid, did)), "updated_at": now_iso()}})
    await audit("erp_bill", did, "update", user, note=d["number"])
    return _bill_view(await get_doc("bill", did, bid))


async def _ledger(bid: str, key: str, group: str) -> str:
    led = await db.ledgers.find_one({"business_id": bid, "system_key": key, "active": True}, NO_ID) \
        or await db.ledgers.find_one({"business_id": bid, "group": group, "active": True}, NO_ID)
    if not led:
        raise HTTPException(400, f"No {group.replace('_', ' ')} ledger found in Easy Books. Create one first.")
    return led["id"]


@router.post("/bills/{did}/post")
async def post_bill(did: str, user=Depends(erp("finalize"))):
    async with busy("bill", did):
        bid = user["business_id"]
        d = await get_doc("bill", did, bid)
        if d["status"] != "draft":
            raise HTTPException(400, "Only drafts can be posted")
        fresh = await _bill_doc(BillIn(**{k: d.get(k) for k in BillIn.model_fields if k != "items"},
                                       items=[BillLine(**{k: it.get(k) for k in BillLine.model_fields}) for it in d["items"]]), bid, did)
        v = await create_voucher(VoucherIn(voucher_type="purchase", date=d["vendor_invoice_date"], reference_no=d["vendor_invoice_no"], party_ledger_id=d["vendor_ledger_id"],
                                           account_ledger_id=await _ledger(bid, "purchase", "purchase"), gst_type=fresh["gst_type"],
                                           narration=f"ERP bill {d['number']} · {d['project_code']} {d['project_name']}"[:250],
                                           items=[Item(description=x["description"][:200], hsn=x.get("hsn", ""), qty=x["qty"], rate=x["net_rate"],
                                                       gst_rate=x["gst_rate"] if fresh["gst_type"] != "none" else 0) for x in fresh["items"]]), user=user)
        await col("bill").update_one({"id": did}, {"$set": {**fresh, "status": "posted", "posted_at": now_iso(), "posted_by": user["name"], "voucher_id": v["id"], "voucher_no": v["voucher_no"]}})
        await audit("erp_bill", did, "post", user, note=f"{d['number']} posted as {v['voucher_no']}")
        return _bill_view(await get_doc("bill", did, bid))


class PayIn(BaseModel):
    date: str = Field(pattern=DATE)
    amount: float = Field(gt=0)
    ledger_id: str
    reference: str = ""


async def _cash_bank(bid: str, lid: str) -> dict:
    led = await db.ledgers.find_one({"id": lid, "business_id": bid, "group": {"$in": ["cash", "bank"]}, "active": True}, NO_ID)
    if not led:
        raise HTTPException(400, "Select a Cash or Bank ledger")
    return led


@router.post("/bills/{did}/payments")
async def pay_bill(did: str, p: PayIn, user=Depends(erp("finalize"))):
    async with busy("bill", did):
        bid = user["business_id"]
        b = _bill_view(await get_doc("bill", did, bid))
        if b["status"] != "posted":
            raise HTTPException(400, "Post the bill before recording payments")
        if p.amount > b["balance"] + 0.005:
            raise HTTPException(400, f"Amount is more than the balance due (₹{b['balance']:,.2f})")
        led = await _cash_bank(bid, p.ledger_id)
        v = await create_voucher(VoucherIn(voucher_type="payment", date=p.date, reference_no=p.reference or b["vendor_invoice_no"], narration=f"Payment for {b['number']} ({b['vendor_invoice_no']})",
                                           entries=[Entry(ledger_id=b["vendor_ledger_id"], debit=p.amount), Entry(ledger_id=led["id"], credit=p.amount)]), user=user)
        pay = {"id": new_id(), **p.model_dump(), "mode": led["name"], "voucher_id": v["id"], "voucher_no": v["voucher_no"], "by": user["name"], "at": now_iso()}
        await col("bill").update_one({"id": did}, {"$inc": {"paid": p.amount}, "$push": {"payments": pay}})
        await audit("erp_bill", did, "payment", user, note=f"₹{p.amount:,.2f} via {led['name']} ({v['voucher_no']})")
        return _bill_view(await get_doc("bill", did, bid))


@router.post("/bills/{did}/cancel")
async def cancel_bill(did: str, b: ReasonIn, user=Depends(erp("cancel"))):
    d = await get_doc("bill", did, user["business_id"])
    if d["status"] == "cancelled":
        raise HTTPException(400, "Already cancelled")
    if d.get("paid", 0) > 0:
        raise HTTPException(400, "This bill has payments. It cannot be cancelled.")
    if d.get("voucher_id"):
        await cancel_voucher(d["voucher_id"], CancelIn(reason=f"ERP bill {d['number']} cancelled: {b.reason}"), user=user)
    await _set_status("bill", did, user, "cancelled", b.reason, cancel_reason=b.reason)
    return {"ok": True}


@router.delete("/bills/{did}")
async def delete_bill(did: str, user=Depends(erp("delete"))):
    d = await get_doc("bill", did, user["business_id"])
    if d["status"] != "draft":
        raise HTTPException(400, "Only drafts can be deleted")
    await col("bill").delete_one({"id": did})
    await audit("erp_bill", did, "delete", user, note=d["number"])
    return {"ok": True}


# ================= Expenses =================
class ExpenseIn(BaseModel):
    project_id: str
    date: str = Field(pattern=DATE)
    category: str = Field(min_length=1, max_length=60)
    paid_to: str = Field(min_length=1, max_length=150)
    vendor_id: Optional[str] = None
    amount: float = Field(gt=0)
    gst_rate: float = Field(0, ge=0, le=100)
    gst_type: Literal["intra", "inter"] = "intra"
    payment_ledger_id: str
    reference: str = ""
    notes: str = ""


async def _exp_doc(b: ExpenseIn, bid: str) -> dict:
    led = await _cash_bank(bid, b.payment_ledger_id)
    if b.vendor_id:
        await _vendor(b.vendor_id, bid)
    _, t = compute([Line(description=b.category, qty=1, rate=b.amount, gst_rate=b.gst_rate)], b.gst_type)
    return {**b.model_dump(), **(await _proj_snap(b.project_id, bid)), "totals": t, "payment_mode": led["name"]}


@router.get("/expenses")
async def list_expenses(status: Optional[str] = None, project_id: Optional[str] = None, q: Optional[str] = None, category: Optional[str] = None, user=Depends(erp())):
    return await _list("expense", user, status, project_id, q, {"category": category} if category else None)


@router.get("/expense-categories")
async def categories(user=Depends(erp())):
    s = await erp_settings(user["business_id"])
    return s.get("expense_categories") or EXPENSE_CATEGORIES


@router.get("/expense-documents")
async def expense_docs(user=Depends(erp())):
    docs = await db.erp_documents.find({"business_id": user["business_id"], "is_deleted": False, "expense_id": {"$ne": None}}, NO_ID).to_list(2000)
    return [{k: v for k, v in d.items() if k != "_id"} for d in docs]


@router.post("/expenses")
async def create_expense(b: ExpenseIn, user=Depends(erp("create"))):
    bid = user["business_id"]
    doc = {**(await _exp_doc(b, bid)), "id": new_id(), "business_id": bid, "number": await auto_no(bid, "expense", b.date), "status": "draft",
           "created_by": user["name"], "created_at": now_iso()}
    await col("expense").insert_one({**doc})
    await audit("erp_expense", doc["id"], "create", user, note=f"{doc['number']} {b.category} ₹{doc['totals']['total']:,.2f}")
    return clean(doc)


@router.put("/expenses/{did}")
async def update_expense(did: str, b: ExpenseIn, user=Depends(erp("edit"))):
    bid = user["business_id"]
    d = await get_doc("expense", did, bid)
    if d["status"] != "draft":
        raise HTTPException(400, "Only draft expenses can be edited")
    await col("expense").update_one({"id": did}, {"$set": {**(await _exp_doc(b, bid)), "updated_at": now_iso()}})
    await audit("erp_expense", did, "update", user, note=d["number"])
    return clean(await get_doc("expense", did, bid))


async def _expense_ledger(bid: str, category: str) -> str:
    name = f"Project Expenses - {category}"
    led = await db.ledgers.find_one({"business_id": bid, "name_lower": name.lower(), "active": True}, NO_ID)
    if led:
        return led["id"]
    led = {"id": new_id(), "business_id": bid, "name": name, "name_lower": name.lower(), "group": "direct_expense", "opening_balance": 0, "opening_type": "Dr",
           "system_key": None, "gstin": "", "state": "", "phone": "", "email": "", "address": "", "active": True, "created_at": now_iso()}
    await db.ledgers.insert_one({**led})
    return led["id"]


@router.post("/expenses/{did}/post")
async def post_expense(did: str, user=Depends(erp("finalize"))):
    async with busy("expense", did):
        bid = user["business_id"]
        d = await get_doc("expense", did, bid)
        if d["status"] != "draft":
            raise HTTPException(400, "Only draft expenses can be posted")
        t = d["totals"]
        entries = [Entry(ledger_id=await _expense_ledger(bid, d["category"]), debit=t["taxable"])]
        for k in ("cgst", "sgst", "igst"):
            if t[k] > 0:
                entries.append(Entry(ledger_id=await _ledger(bid, k, "duties_taxes"), debit=t[k]))
        entries.append(Entry(ledger_id=d["payment_ledger_id"], credit=t["total"]))
        v = await create_voucher(VoucherIn(voucher_type="payment", date=d["date"], reference_no=d.get("reference") or d["number"],
                                           narration=f"ERP {d['number']} {d['category']} paid to {d['paid_to']} · {d['project_code']}"[:250], entries=entries), user=user)
        await _set_status("expense", did, user, "posted", f"{d['number']} as {v['voucher_no']}", voucher_id=v["id"], voucher_no=v["voucher_no"])
        return clean(await get_doc("expense", did, bid))


@router.post("/expenses/{did}/cancel")
async def cancel_expense(did: str, b: ReasonIn, user=Depends(erp("cancel"))):
    d = await get_doc("expense", did, user["business_id"])
    if d["status"] == "cancelled":
        raise HTTPException(400, "Already cancelled")
    if d.get("voucher_id"):
        await cancel_voucher(d["voucher_id"], CancelIn(reason=f"ERP expense {d['number']} cancelled: {b.reason}"), user=user)
    await _set_status("expense", did, user, "cancelled", b.reason, cancel_reason=b.reason)
    return {"ok": True}


@router.delete("/expenses/{did}")
async def delete_expense(did: str, user=Depends(erp("delete"))):
    d = await get_doc("expense", did, user["business_id"])
    if d["status"] != "draft":
        raise HTTPException(400, "Only drafts can be deleted")
    await col("expense").delete_one({"id": did})
    await audit("erp_expense", did, "delete", user, note=d["number"])
    return {"ok": True}


async def purchase_numbers(pid: str, bid: str) -> dict:
    pos = await col("po").find({"business_id": bid, "project_id": pid, "status": {"$in": ["approved", "closed"]}}, NO_ID).to_list(5000)
    grns = await col("grn").find({"business_id": bid, "project_id": pid, "status": "posted"}, {"accepted_value": 1}).to_list(5000)
    bills = await col("bill").find({"business_id": bid, "project_id": pid, "status": "posted"}, NO_ID).to_list(5000)
    exps = await col("expense").find({"business_id": bid, "project_id": pid, "status": "posted"}, NO_ID).to_list(5000)
    return {"purchase_orders": len(pos), "po_value": round(sum(p["totals"]["total"] for p in pos), 2),
            "material_received": round(sum(g.get("accepted_value", 0) for g in grns), 2), "purchase_bills": len(bills),
            "purchases": round(sum(b["totals"]["taxable"] for b in bills), 2), "bills_total": round(sum(b["totals"]["total"] for b in bills), 2),
            "payable": round(sum(b["totals"]["total"] - b.get("paid", 0) for b in bills), 2), "expenses": round(sum(e["totals"]["taxable"] for e in exps), 2),
            "pending_prs": await col("pr").count_documents({"business_id": bid, "project_id": pid, "status": {"$in": ["submitted"]}})}

