from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import ANY, WRITE
from db import db, NO_ID, new_id, now_iso, audit, clean

router = APIRouter(prefix="/api/stock-items")
SIGN = {"purchase": 1, "credit_note": 1, "sales": -1, "debit_note": -1}


class StockIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    hsn: str = ""
    unit: str = "Nos"
    gst_rate: float = Field(18, ge=0, le=100)
    sale_rate: float = Field(0, ge=0)
    purchase_rate: float = Field(0, ge=0)
    opening_qty: float = 0
    opening_rate: float = Field(0, ge=0)
    reorder_level: float = Field(0, ge=0)


async def _moves(bid: str, to_date: Optional[str] = None, before: Optional[str] = None, item_id: Optional[str] = None):
    match = {"business_id": bid, "status": "active", "voucher_type": {"$in": list(SIGN)}}
    d = {k: v for k, v in (("$lte", to_date), ("$lt", before)) if v}
    if d:
        match["date"] = d
    inner = {"items.item_id": item_id} if item_id else {"items.item_id": {"$nin": [None, ""]}}
    rows = await db.vouchers.aggregate([
        {"$match": match}, {"$unwind": "$items"}, {"$match": inner},
        {"$group": {"_id": {"item": "$items.item_id", "type": "$voucher_type"}, "qty": {"$sum": "$items.qty"}, "amount": {"$sum": "$items.amount"}}},
    ]).to_list(None)
    out = defaultdict(lambda: {"net": 0.0, "pur_qty": 0.0, "pur_amt": 0.0, "sold": 0.0, "bought": 0.0})
    for r in rows:
        m, t = out[r["_id"]["item"]], r["_id"]["type"]
        m["net"] += SIGN[t] * r["qty"]
        if t == "purchase":
            m["pur_qty"] += r["qty"]
            m["pur_amt"] += r["amount"]
            m["bought"] += r["qty"]
        elif t == "sales":
            m["sold"] += r["qty"]
    return out


def _view(s: dict, m: dict) -> dict:
    on_hand = round(s.get("opening_qty", 0) + m["net"], 3)
    qty = s.get("opening_qty", 0) + m["pur_qty"]
    cost = (s.get("opening_qty", 0) * s.get("opening_rate", 0) + m["pur_amt"]) / qty if qty > 0 else s.get("purchase_rate", 0)
    return {**clean(s), "on_hand": on_hand, "avg_cost": round(cost, 2), "value": round(max(on_hand, 0) * cost, 2),
            "sold_qty": round(m["sold"], 3), "purchased_qty": round(m["bought"], 3),
            "low": s.get("reorder_level", 0) > 0 and on_hand <= s["reorder_level"], "negative": on_hand < 0}


@router.get("")
async def list_items(to_date: Optional[str] = None, user=Depends(ANY)):
    items = await db.stock_items.find({"business_id": user["business_id"], "active": True}, NO_ID).sort("name", 1).to_list(5000)
    moves = await _moves(user["business_id"], to_date=to_date)
    rows = [_view(s, moves[s["id"]]) for s in items]
    return {"items": rows, "total_value": round(sum(r["value"] for r in rows), 2), "low_count": sum(1 for r in rows if r["low"] or r["negative"])}


async def _check(body: StockIn, bid: str, exclude: Optional[str] = None):
    q = {"business_id": bid, "name_lower": body.name.strip().lower(), "active": True}
    if exclude:
        q["id"] = {"$ne": exclude}
    if await db.stock_items.find_one(q):
        raise HTTPException(400, "A stock item with this name already exists")


@router.post("")
async def create_item(body: StockIn, user=Depends(WRITE)):
    await _check(body, user["business_id"])
    doc = {**body.model_dump(), "name": body.name.strip(), "name_lower": body.name.strip().lower(), "id": new_id(),
           "business_id": user["business_id"], "active": True, "created_at": now_iso()}
    await db.stock_items.insert_one(doc)
    doc = clean(doc)
    await audit("stock_item", doc["id"], "create", user, after=doc)
    return doc


@router.put("/{sid}")
async def update_item(sid: str, body: StockIn, user=Depends(WRITE)):
    q = {"id": sid, "business_id": user["business_id"]}
    before = await db.stock_items.find_one(q, NO_ID)
    if not before:
        raise HTTPException(404, "Stock item not found")
    await _check(body, user["business_id"], sid)
    upd = {**body.model_dump(), "name": body.name.strip(), "name_lower": body.name.strip().lower(), "updated_at": now_iso()}
    await db.stock_items.update_one(q, {"$set": upd})
    after = await db.stock_items.find_one(q, NO_ID)
    await audit("stock_item", sid, "update", user, before=clean(before), after=clean(after))
    return clean(after)


@router.delete("/{sid}")
async def remove_item(sid: str, user=Depends(WRITE)):
    q = {"id": sid, "business_id": user["business_id"]}
    s = await db.stock_items.find_one(q, NO_ID)
    if not s:
        raise HTTPException(404, "Stock item not found")
    if await db.vouchers.find_one({"business_id": user["business_id"], "items.item_id": sid}):
        raise HTTPException(400, "Item is used in vouchers and cannot be removed")
    await db.stock_items.update_one(q, {"$set": {"active": False}})
    await audit("stock_item", sid, "deactivate", user, before=clean(s))
    return {"ok": True}


@router.get("/{sid}/movements")
async def movements(sid: str, from_date: Optional[str] = None, to_date: Optional[str] = None, user=Depends(ANY)):
    bid = user["business_id"]
    s = await db.stock_items.find_one({"id": sid, "business_id": bid}, NO_ID)
    if not s:
        raise HTTPException(404, "Stock item not found")
    opening = s.get("opening_qty", 0)
    if from_date:
        opening += (await _moves(bid, before=from_date, item_id=sid))[sid]["net"]
    q = {"business_id": bid, "status": "active", "voucher_type": {"$in": list(SIGN)}, "items.item_id": sid}
    d = {k: v for k, v in (("$gte", from_date), ("$lte", to_date)) if v}
    if d:
        q["date"] = d
    vs = await db.vouchers.find(q, NO_ID).sort([("date", 1), ("created_at", 1)]).to_list(20000)
    bal, rows = round(opening, 3), []
    for v in vs:
        for it in (i for i in v["items"] if i.get("item_id") == sid):
            qty = SIGN[v["voucher_type"]] * it["qty"]
            bal = round(bal + qty, 3)
            rows.append({"voucher_id": v["id"], "date": v["date"], "voucher_no": v["voucher_no"], "voucher_type": v["voucher_type"],
                         "party": v["party_name"], "in_qty": qty if qty > 0 else "", "out_qty": -qty if qty < 0 else "",
                         "rate": it["rate"], "balance": bal})
    return {"item": clean(s), "opening": round(opening, 3), "rows": rows, "closing": bal}
