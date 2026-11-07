import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pymongo import ReturnDocument

from accounting import VoucherIn, VoucherType, VOUCHER_TYPES, ITEM_TYPES, CASH_BANK, D, build_item_entries, validate_entries
from auth import ANY, WRITE
from db import db, NO_ID, new_id, now_iso, audit, clean

router = APIRouter(prefix="/api/vouchers")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class CancelIn(BaseModel):
    reason: str = ""


async def _fy_for(date: str, bid: str) -> dict:
    if not DATE_RE.match(date):
        raise HTTPException(400, "Invalid date")
    fy = await db.financial_years.find_one({"business_id": bid, "start_date": {"$lte": date}, "end_date": {"$gte": date}}, NO_ID)
    if not fy:
        raise HTTPException(400, "No financial year found for this date. Create it in Settings.")
    if fy.get("locked"):
        raise HTTPException(400, f"Financial year {fy['name']} is locked")
    return fy


async def _prepare(v: VoucherIn, bid: str) -> dict:
    ids = {e.ledger_id for e in v.entries} | {v.party_ledger_id, v.account_ledger_id} - {None}
    ledgers = {l["id"]: l for l in await db.ledgers.find({"business_id": bid, "active": True}, NO_ID).to_list(10000) if l["id"] in ids or l.get("system_key") in ("cgst", "sgst", "igst")}
    gst = {l["system_key"]: l["id"] for l in ledgers.values() if l.get("system_key") in ("cgst", "sgst", "igst")}
    items, totals = [], {}
    entries = v.entries
    if v.voucher_type in ITEM_TYPES:
        entries, items, totals = build_item_entries(v, ledgers, gst)
    amount = validate_entries(v.voucher_type, entries, ledgers)
    party_id = v.party_ledger_id if v.voucher_type in ITEM_TYPES else None
    if not party_id:
        non_cash = [e.ledger_id for e in entries if ledgers[e.ledger_id]["group"] not in CASH_BANK]
        party_id = (non_cash or [entries[0].ledger_id])[0]
    return {
        "voucher_type": v.voucher_type, "date": v.date, "narration": v.narration.strip(),
        "reference_no": v.reference_no.strip(), "gst_type": v.gst_type if v.voucher_type in ITEM_TYPES else "none",
        "party_ledger_id": party_id, "party_name": ledgers[party_id]["name"],
        "account_ledger_id": v.account_ledger_id if v.voucher_type in ITEM_TYPES else None,
        "items": items, "totals": totals, "amount": amount,
        "entries": [{"ledger_id": e.ledger_id, "ledger_name": ledgers[e.ledger_id]["name"],
                     "debit": float(D(e.debit)), "credit": float(D(e.credit))} for e in entries],
    }


@router.get("/next-number")
async def next_number(voucher_type: VoucherType, date: str, user=Depends(ANY)):
    fy = await _fy_for(date, user["business_id"])
    c = await db.counters.find_one({"_id": f"{fy['id']}:{voucher_type}"})
    seq = (c["seq"] if c else 0) + 1
    return {"voucher_no": f"{VOUCHER_TYPES[voucher_type]}/{fy['name']}/{seq:04d}"}


@router.post("")
async def create_voucher(v: VoucherIn, user=Depends(WRITE)):
    fy = await _fy_for(v.date, user["business_id"])
    data = await _prepare(v, user["business_id"])
    c = await db.counters.find_one_and_update({"_id": f"{fy['id']}:{v.voucher_type}"}, {"$inc": {"seq": 1}},
                                              upsert=True, return_document=ReturnDocument.AFTER)
    doc = {**data, "id": new_id(), "business_id": user["business_id"], "fy_id": fy["id"], "seq": c["seq"],
           "voucher_no": f"{VOUCHER_TYPES[v.voucher_type]}/{fy['name']}/{c['seq']:04d}",
           "status": "active", "created_by": user["name"], "created_at": now_iso(), "updated_at": now_iso()}
    await db.vouchers.insert_one(doc)
    doc = clean(doc)
    await audit("voucher", doc["id"], "create", user, after=doc)
    return doc


@router.put("/{vid}")
async def update_voucher(vid: str, v: VoucherIn, user=Depends(WRITE)):
    before = await db.vouchers.find_one({"id": vid, "business_id": user["business_id"]}, NO_ID)
    if not before:
        raise HTTPException(404, "Voucher not found")
    if before["status"] != "active":
        raise HTTPException(400, "Cancelled vouchers cannot be edited")
    if v.voucher_type != before["voucher_type"]:
        raise HTTPException(400, "Voucher type cannot be changed")
    old_fy = await db.financial_years.find_one({"id": before["fy_id"]}, NO_ID)
    if old_fy and old_fy.get("locked"):
        raise HTTPException(400, f"Financial year {old_fy['name']} is locked")
    fy = await _fy_for(v.date, user["business_id"])
    if fy["id"] != before["fy_id"]:
        raise HTTPException(400, "Voucher date must stay within its financial year")
    data = await _prepare(v, user["business_id"])
    await db.vouchers.update_one({"id": vid}, {"$set": {**data, "updated_at": now_iso(), "updated_by": user["name"]}})
    after = await db.vouchers.find_one({"id": vid}, NO_ID)
    await audit("voucher", vid, "update", user, before=clean(before), after=clean(after))
    return clean(after)


@router.post("/{vid}/cancel")
async def cancel_voucher(vid: str, body: CancelIn, user=Depends(WRITE)):
    before = await db.vouchers.find_one({"id": vid, "business_id": user["business_id"]}, NO_ID)
    if not before:
        raise HTTPException(404, "Voucher not found")
    if before["status"] == "cancelled":
        raise HTTPException(400, "Voucher already cancelled")
    fy = await db.financial_years.find_one({"id": before["fy_id"]}, NO_ID)
    if fy and fy.get("locked"):
        raise HTTPException(400, f"Financial year {fy['name']} is locked")
    upd = {"status": "cancelled", "cancel_reason": body.reason, "cancelled_by": user["name"], "cancelled_at": now_iso()}
    await db.vouchers.update_one({"id": vid}, {"$set": upd})
    await audit("voucher", vid, "cancel", user, before=clean(before), note=body.reason)
    return {"ok": True}


@router.get("")
async def list_vouchers(from_date: Optional[str] = None, to_date: Optional[str] = None, voucher_type: Optional[str] = None,
                        ledger_id: Optional[str] = None, q: Optional[str] = None, status: Optional[str] = None,
                        limit: int = 500, user=Depends(ANY)):
    query = {"business_id": user["business_id"]}
    if from_date or to_date:
        query["date"] = {k: v for k, v in (("$gte", from_date), ("$lte", to_date)) if v}
    if voucher_type:
        query["voucher_type"] = {"$in": voucher_type.split(",")}
    if ledger_id:
        query["entries.ledger_id"] = ledger_id
    if status:
        query["status"] = status
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        query["$or"] = [{"voucher_no": rx}, {"narration": rx}, {"party_name": rx}, {"reference_no": rx}]
    rows = await db.vouchers.find(query, NO_ID).sort([("date", -1), ("created_at", -1)]).to_list(min(limit, 5000))
    return clean(rows)


@router.get("/{vid}")
async def get_voucher(vid: str, user=Depends(ANY)):
    v = await db.vouchers.find_one({"id": vid, "business_id": user["business_id"]}, NO_ID)
    if not v:
        raise HTTPException(404, "Voucher not found")
    history = await db.audit_logs.find({"entity_id": vid}, {**NO_ID, "before": 0, "after": 0}).sort("timestamp", 1).to_list(200)
    return {**clean(v), "history": clean(history)}
