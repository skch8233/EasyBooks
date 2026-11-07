import re
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import ANY, WRITE, ADMIN
from db import db, NO_ID, new_id, now_iso, audit, clean

router = APIRouter(prefix="/api")
BACKUP_COLLECTIONS = ["settings", "financial_years", "ledgers", "vouchers", "counters", "audit_logs"]
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


class SettingsIn(BaseModel):
    company_name: str
    address: str = ""
    state: str = ""
    gstin: str = ""
    phone: str = ""
    email: str = ""
    gst_rates: List[float] = [0, 5, 12, 18, 28]


class FYIn(BaseModel):
    start_year: int


class FYUpdate(BaseModel):
    locked: Optional[bool] = None
    is_active: Optional[bool] = None


class RestoreIn(BaseModel):
    collections: dict


@router.get("/settings")
async def get_settings(user=Depends(ANY)):
    s = await db.settings.find_one({"id": "company"}, NO_ID)
    return clean(s)


@router.put("/settings")
async def put_settings(body: SettingsIn, user=Depends(ADMIN)):
    gstin = body.gstin.strip().upper()
    if gstin and not GSTIN_RE.match(gstin):
        raise HTTPException(400, "Invalid GSTIN format")
    rates = sorted({round(r, 2) for r in body.gst_rates if 0 <= r <= 100})
    before = await db.settings.find_one({"id": "company"}, NO_ID)
    upd = {**body.model_dump(), "gstin": gstin, "gst_rates": rates}
    await db.settings.update_one({"id": "company"}, {"$set": upd}, upsert=True)
    await audit("settings", "company", "update", user, before=clean(before), after=upd)
    s = await db.settings.find_one({"id": "company"}, NO_ID)
    return clean(s)


@router.get("/financial-years")
async def list_fy(user=Depends(ANY)):
    fys = await db.financial_years.find({}, NO_ID).sort("start_date", -1).to_list(100)
    return clean(fys)


def fy_doc(start_year: int) -> dict:
    return {"id": new_id(), "name": f"{start_year}-{str(start_year + 1)[-2:]}", "start_date": f"{start_year}-04-01",
            "end_date": f"{start_year + 1}-03-31", "locked": False, "is_active": False, "created_at": now_iso()}


@router.post("/financial-years")
async def create_fy(body: FYIn, user=Depends(ADMIN)):
    if not 2000 <= body.start_year <= 2100:
        raise HTTPException(400, "Invalid year")
    doc = fy_doc(body.start_year)
    if await db.financial_years.find_one({"name": doc["name"]}):
        raise HTTPException(400, "Financial year already exists")
    await db.financial_years.insert_one(doc)
    await audit("financial_year", doc["id"], "create", user, after=clean(doc))
    return clean(doc)


@router.put("/financial-years/{fid}")
async def update_fy(fid: str, body: FYUpdate, user=Depends(ADMIN)):
    fy = await db.financial_years.find_one({"id": fid}, NO_ID)
    if not fy:
        raise HTTPException(404, "Financial year not found")
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    if upd.get("is_active"):
        await db.financial_years.update_many({}, {"$set": {"is_active": False}})
    await db.financial_years.update_one({"id": fid}, {"$set": upd})
    await audit("financial_year", fid, "update", user, before=clean(fy), after=upd)
    updated = await db.financial_years.find_one({"id": fid}, NO_ID)
    return clean(updated)


@router.get("/audit-logs")
async def audit_logs(entity: Optional[str] = None, limit: int = 300, user=Depends(WRITE)):
    q = {"entity": entity} if entity else {}
    logs = await db.audit_logs.find(q, {**NO_ID, "before": 0, "after": 0}).sort("timestamp", -1).to_list(min(limit, 2000))
    return clean(logs)


@router.get("/backup")
async def backup(user=Depends(ADMIN)):
    data = {}
    for c in BACKUP_COLLECTIONS:
        data[c] = clean(await db[c].find({}).to_list(None)) if c != "counters" else await db[c].find({}).to_list(None)
    await audit("system", "backup", "backup", user)
    return {"app": "easy-books", "version": 1, "created_at": now_iso(), "collections": data}


@router.post("/restore")
async def restore(body: RestoreIn, user=Depends(ADMIN)):
    cols = body.collections
    if not all(isinstance(cols.get(c), list) for c in ("ledgers", "vouchers", "financial_years")):
        raise HTTPException(400, "Invalid backup file")
    if not all(isinstance(d, dict) for c in BACKUP_COLLECTIONS for d in (cols.get(c) or [])):
        raise HTTPException(400, "Invalid backup file")
    snapshot = {c: await db[c].find({}, NO_ID if c != "counters" else None).to_list(None) for c in BACKUP_COLLECTIONS}
    await db.restore_snapshots.insert_one({"id": new_id(), "created_at": now_iso(), "by": user["email"], "data": snapshot})
    for c in BACKUP_COLLECTIONS:
        if c in cols and isinstance(cols[c], list):
            await db[c].delete_many({})
            if cols[c]:
                await db[c].insert_many([{k: v for k, v in d.items() if k != "_id" or c == "counters"} for d in cols[c]])
    await audit("system", "restore", "restore", user, note=f"{len(cols['vouchers'])} vouchers, {len(cols['ledgers'])} ledgers")
    return {"ok": True}


SEED_LEDGERS = [
    ("Cash", "cash", 50000, "Dr", "cash"), ("HDFC Bank", "bank", 200000, "Dr", None),
    ("Sales", "sales", 0, "Dr", "sales"), ("Purchase", "purchase", 0, "Dr", "purchase"),
    ("CGST", "duties_taxes", 0, "Cr", "cgst"), ("SGST", "duties_taxes", 0, "Cr", "sgst"), ("IGST", "duties_taxes", 0, "Cr", "igst"),
    ("Capital Account", "capital", 250000, "Cr", None), ("Rent Expense", "indirect_expense", 0, "Dr", None),
    ("Salary", "indirect_expense", 0, "Dr", None), ("Sharma Traders", "sundry_debtors", 0, "Dr", None),
    ("Raj Electronics", "sundry_creditors", 0, "Cr", None),
]


async def seed_data():
    if not await db.settings.find_one({"id": "company"}):
        await db.settings.insert_one({"id": "company", "company_name": "My Business", "address": "", "state": "",
                                      "gstin": "", "phone": "", "email": "", "gst_rates": [0, 5, 12, 18, 28]})
    if not await db.financial_years.count_documents({}):
        today = date.today()
        doc = fy_doc(today.year if today.month >= 4 else today.year - 1)
        doc["is_active"] = True
        await db.financial_years.insert_one(doc)
    if not await db.ledgers.count_documents({}):
        await db.ledgers.insert_many([{
            "id": new_id(), "name": n, "name_lower": n.lower(), "group": g, "opening_balance": ob, "opening_type": t,
            "system_key": k, "gstin": "", "state": "", "phone": "", "email": "", "address": "", "active": True,
            "created_at": now_iso()} for n, g, ob, t, k in SEED_LEDGERS])
