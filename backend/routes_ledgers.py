from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from accounting import GROUPS, GROUP_MAP
from auth import ANY, WRITE
from db import db, NO_ID, new_id, now_iso, audit, clean

router = APIRouter(prefix="/api")


class LedgerIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    group: str
    opening_balance: float = Field(0, ge=0)
    opening_type: Literal["Dr", "Cr"] = "Dr"
    gstin: str = ""
    state: str = ""
    phone: str = ""
    email: str = ""
    address: str = ""


@router.get("/groups")
async def groups(user=Depends(ANY)):
    return GROUPS


async def ledger_balances(to_date: Optional[str] = None) -> dict:
    match = {"status": "active"}
    if to_date:
        match["date"] = {"$lte": to_date}
    rows = await db.vouchers.aggregate([
        {"$match": match}, {"$unwind": "$entries"},
        {"$group": {"_id": "$entries.ledger_id", "dr": {"$sum": "$entries.debit"}, "cr": {"$sum": "$entries.credit"}}},
    ]).to_list(None)
    return {r["_id"]: round(r["dr"] - r["cr"], 2) for r in rows}


def opening_signed(led: dict) -> float:
    ob = led.get("opening_balance", 0) or 0
    return ob if led.get("opening_type", "Dr") == "Dr" else -ob


@router.get("/ledgers")
async def list_ledgers(group: Optional[str] = None, include_inactive: bool = False, user=Depends(ANY)):
    q = {} if include_inactive else {"active": True}
    if group:
        q["group"] = {"$in": group.split(",")}
    ledgers = await db.ledgers.find(q, NO_ID).sort("name", 1).to_list(5000)
    moves = await ledger_balances()
    for led in ledgers:
        bal = round(opening_signed(led) + moves.get(led["id"], 0), 2)
        led["balance"] = abs(bal)
        led["balance_type"] = "Dr" if bal >= 0 else "Cr"
        led["group_name"] = GROUP_MAP.get(led["group"], {}).get("name", led["group"])
    return clean(ledgers)


async def _check(body: LedgerIn, exclude_id: Optional[str] = None):
    if body.group not in GROUP_MAP:
        raise HTTPException(400, "Invalid ledger group")
    q = {"name_lower": body.name.strip().lower(), "active": True}
    if exclude_id:
        q["id"] = {"$ne": exclude_id}
    if await db.ledgers.find_one(q):
        raise HTTPException(400, "A ledger with this name already exists")


@router.post("/ledgers")
async def create_ledger(body: LedgerIn, user=Depends(WRITE)):
    await _check(body)
    doc = {**body.model_dump(), "name": body.name.strip(), "name_lower": body.name.strip().lower(),
           "gstin": body.gstin.strip().upper(), "id": new_id(), "active": True, "system_key": None,
           "created_at": now_iso()}
    await db.ledgers.insert_one(doc)
    doc = clean(doc)
    await audit("ledger", doc["id"], "create", user, after=doc)
    return doc


@router.put("/ledgers/{lid}")
async def update_ledger(lid: str, body: LedgerIn, user=Depends(WRITE)):
    before = await db.ledgers.find_one({"id": lid}, NO_ID)
    if not before:
        raise HTTPException(404, "Ledger not found")
    await _check(body, lid)
    if before.get("system_key") and body.group != before["group"]:
        raise HTTPException(400, "Group of a system ledger cannot be changed")
    upd = {**body.model_dump(), "name": body.name.strip(), "name_lower": body.name.strip().lower(),
           "gstin": body.gstin.strip().upper(), "updated_at": now_iso()}
    await db.ledgers.update_one({"id": lid}, {"$set": upd})
    await db.vouchers.update_many({"entries.ledger_id": lid}, {"$set": {"entries.$[e].ledger_name": upd["name"]}},
                                  array_filters=[{"e.ledger_id": lid}])
    await db.vouchers.update_many({"party_ledger_id": lid}, {"$set": {"party_name": upd["name"]}})
    after = await db.ledgers.find_one({"id": lid}, NO_ID)
    await audit("ledger", lid, "update", user, before=clean(before), after=clean(after))
    return clean(after)


@router.delete("/ledgers/{lid}")
async def deactivate_ledger(lid: str, user=Depends(WRITE)):
    led = await db.ledgers.find_one({"id": lid}, NO_ID)
    if not led:
        raise HTTPException(404, "Ledger not found")
    if led.get("system_key"):
        raise HTTPException(400, "System ledgers cannot be removed")
    if await db.vouchers.find_one({"entries.ledger_id": lid}):
        raise HTTPException(400, "Ledger has transactions and cannot be removed")
    if led.get("opening_balance"):
        raise HTTPException(400, "Clear the opening balance before removing this ledger")
    await db.ledgers.update_one({"id": lid}, {"$set": {"active": False, "updated_at": now_iso()}})
    await audit("ledger", lid, "deactivate", user, before=clean(led))
    return {"ok": True}
