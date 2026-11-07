import os
import re
from typing import List, Optional

import requests
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from auth import ANY, ADMIN, ADMIN_WRITE
from business import fy_doc
from db import db, NO_ID, new_id, now_iso, audit, clean

router = APIRouter(prefix="/api")
BACKUP_COLLECTIONS = ["settings", "financial_years", "ledgers", "vouchers", "audit_logs", "stock_items", "reminders"]
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
UPI_RE = re.compile(r"^[\w.\-]{2,256}@[a-zA-Z][a-zA-Z0-9.\-]{1,64}$")

STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
APP_NAME = "easy-books"
_storage_key = None


def init_storage(force: bool = False):
    global _storage_key
    if _storage_key and not force:
        return _storage_key
    r = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": os.environ.get("EMERGENT_LLM_KEY")}, timeout=30)
    r.raise_for_status()
    _storage_key = r.json()["storage_key"]
    return _storage_key


def _storage(method: str, path: str, **kw):
    for attempt in (0, 1):
        r = requests.request(method, f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": init_storage(force=attempt == 1), **kw.pop("headers", {})}, timeout=60, **kw)
        if r.status_code != 404 or attempt == 1:
            r.raise_for_status()
            return r
    return r


class SettingsIn(BaseModel):
    company_name: str
    address: str = ""
    state: str = ""
    gstin: str = ""
    phone: str = ""
    email: str = ""
    gst_rates: List[float] = [0, 5, 12, 18, 28]
    upi_id: str = ""
    bank_name: str = ""
    bank_account: str = ""
    bank_ifsc: str = ""
    invoice_terms: str = ""
    default_credit_days: int = Field(30, ge=0, le=365)


class FYIn(BaseModel):
    start_year: int


class FYUpdate(BaseModel):
    locked: Optional[bool] = None
    is_active: Optional[bool] = None


class RestoreIn(BaseModel):
    collections: dict


@router.get("/settings")
async def get_settings(user=Depends(ANY)):
    s = await db.settings.find_one({"business_id": user["business_id"]}, NO_ID)
    return clean(s)


@router.put("/settings")
async def put_settings(body: SettingsIn, user=Depends(ADMIN_WRITE)):
    gstin = body.gstin.strip().upper()
    if gstin and not GSTIN_RE.match(gstin):
        raise HTTPException(400, "Invalid GSTIN format")
    upi = body.upi_id.strip()
    if upi and not UPI_RE.match(upi):
        raise HTTPException(400, "Invalid UPI ID (example: shopname@okhdfcbank)")
    rates = sorted({round(r, 2) for r in body.gst_rates if 0 <= r <= 100})
    q = {"business_id": user["business_id"]}
    before = await db.settings.find_one(q, NO_ID)
    upd = {**body.model_dump(exclude_unset=True), "gstin": gstin, "upi_id": upi, "bank_ifsc": body.bank_ifsc.strip().upper(), "gst_rates": rates}
    for k in ("upi_id", "bank_ifsc", "gstin", "gst_rates"):
        if k not in body.model_fields_set:
            upd.pop(k)
    await db.settings.update_one(q, {"$set": upd})
    await db.businesses.update_one({"id": user["business_id"]}, {"$set": {"name": body.company_name}})
    await audit("settings", user["business_id"], "update", user, before=clean(before), after=upd)
    s = await db.settings.find_one(q, NO_ID)
    return clean(s)


@router.post("/settings/logo")
async def upload_logo(file: UploadFile = File(...), user=Depends(ADMIN_WRITE)):
    if file.content_type not in ("image/png", "image/jpeg", "image/webp"):
        raise HTTPException(400, "Logo must be a PNG, JPG or WEBP image")
    data = await file.read()
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(400, "Logo must be under 2 MB")
    ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[file.content_type]
    path = f"{APP_NAME}/logos/{user['business_id']}/{new_id()}.{ext}"
    try:
        res = _storage("PUT", path, data=data, headers={"Content-Type": file.content_type}).json()
    except Exception as exc:
        raise HTTPException(502, f"Logo upload failed: {exc}")
    await db.files.insert_one({"id": new_id(), "business_id": user["business_id"], "storage_path": res["path"], "kind": "logo",
                               "original_filename": file.filename, "content_type": file.content_type, "size": len(data),
                               "is_deleted": False, "created_at": now_iso()})
    await db.settings.update_one({"business_id": user["business_id"]}, {"$set": {"logo_path": res["path"], "logo_type": file.content_type}})
    await audit("settings", user["business_id"], "logo", user)
    return {"logo_path": res["path"]}


@router.delete("/settings/logo")
async def remove_logo(user=Depends(ADMIN_WRITE)):
    await db.files.update_many({"business_id": user["business_id"], "kind": "logo"}, {"$set": {"is_deleted": True}})
    await db.settings.update_one({"business_id": user["business_id"]}, {"$set": {"logo_path": None}})
    return {"ok": True}


@router.get("/settings/logo")
async def get_logo(user=Depends(ANY)):
    s = await db.settings.find_one({"business_id": user["business_id"]}, NO_ID)
    if not s or not s.get("logo_path"):
        raise HTTPException(404, "No logo uploaded")
    try:
        r = _storage("GET", s["logo_path"])
    except Exception:
        raise HTTPException(404, "Logo not available")
    return Response(content=r.content, media_type=s.get("logo_type", "image/png"))


@router.get("/financial-years")
async def list_fy(user=Depends(ANY)):
    fys = await db.financial_years.find({"business_id": user["business_id"]}, NO_ID).sort("start_date", -1).to_list(100)
    return clean(fys)


@router.post("/financial-years")
async def create_fy(body: FYIn, user=Depends(ADMIN_WRITE)):
    if not 2000 <= body.start_year <= 2100:
        raise HTTPException(400, "Invalid year")
    doc = fy_doc(body.start_year, user["business_id"])
    if await db.financial_years.find_one({"business_id": user["business_id"], "name": doc["name"]}):
        raise HTTPException(400, "Financial year already exists")
    await db.financial_years.insert_one(doc)
    await audit("financial_year", doc["id"], "create", user, after=clean(doc))
    return clean(doc)


@router.put("/financial-years/{fid}")
async def update_fy(fid: str, body: FYUpdate, user=Depends(ADMIN_WRITE)):
    q = {"id": fid, "business_id": user["business_id"]}
    fy = await db.financial_years.find_one(q, NO_ID)
    if not fy:
        raise HTTPException(404, "Financial year not found")
    upd = {k: v for k, v in body.model_dump().items() if v is not None}
    if upd.get("is_active"):
        await db.financial_years.update_many({"business_id": user["business_id"]}, {"$set": {"is_active": False}})
    await db.financial_years.update_one(q, {"$set": upd})
    await audit("financial_year", fid, "update", user, before=clean(fy), after=upd)
    updated = await db.financial_years.find_one(q, NO_ID)
    return clean(updated)


@router.get("/audit-logs")
async def audit_logs(entity: Optional[str] = None, limit: int = 300, user=Depends(ANY)):
    if user["role"] == "viewer":
        raise HTTPException(403, "You do not have permission for this action")
    q = {"business_id": user["business_id"], **({"entity": entity} if entity else {})}
    logs = await db.audit_logs.find(q, {**NO_ID, "before": 0, "after": 0}).sort("timestamp", -1).to_list(min(limit, 2000))
    return clean(logs)


@router.get("/backup")
async def backup(user=Depends(ADMIN)):
    bid = user["business_id"]
    data = {c: clean(await db[c].find({"business_id": bid}).to_list(None)) for c in BACKUP_COLLECTIONS}
    fy_ids = [f["id"] for f in data["financial_years"]]
    data["counters"] = await db.counters.find({"_id": {"$regex": f"^({'|'.join(map(re.escape, fy_ids)) or 'none'}):"}}).to_list(None)
    await audit("system", "backup", "backup", user)
    return {"app": "easy-books", "version": 2, "created_at": now_iso(), "collections": data}


@router.post("/restore")
async def restore(body: RestoreIn, user=Depends(ADMIN_WRITE)):
    cols, bid = body.collections, user["business_id"]
    if not all(isinstance(cols.get(c), list) for c in ("ledgers", "vouchers", "financial_years")):
        raise HTTPException(400, "Invalid backup file")
    if not all(isinstance(d, dict) for c in BACKUP_COLLECTIONS + ["counters"] for d in (cols.get(c) or [])):
        raise HTTPException(400, "Invalid backup file")
    foreign = {d.get("business_id") for c in BACKUP_COLLECTIONS for d in (cols.get(c) or []) if d.get("business_id")} - {bid}
    if foreign:
        raise HTTPException(400, "This backup belongs to a different business and cannot be restored here")
    if not cols["financial_years"]:
        raise HTTPException(400, "Backup has no financial years")
    for c in BACKUP_COLLECTIONS:
        ids = [d.get("id") for d in (cols.get(c) or []) if d.get("id")]
        if ids and await db[c].count_documents({"id": {"$in": ids}, "business_id": {"$ne": bid}}):
            raise HTTPException(400, "This backup belongs to a different business and cannot be restored here")
    snapshot = {c: await db[c].find({"business_id": bid}, NO_ID).to_list(None) for c in BACKUP_COLLECTIONS}
    await db.restore_snapshots.insert_one({"id": new_id(), "business_id": bid, "created_at": now_iso(), "by": user["email"], "data": snapshot})
    try:
        for c in BACKUP_COLLECTIONS:
            if isinstance(cols.get(c), list):
                await db[c].delete_many({"business_id": bid})
                docs = [{**{k: v for k, v in d.items() if k != "_id"}, "business_id": bid} for d in cols[c]]
                if docs:
                    await db[c].insert_many(docs)
    except Exception:
        for c in BACKUP_COLLECTIONS:
            await db[c].delete_many({"business_id": bid})
            if snapshot[c]:
                await db[c].insert_many([dict(d) for d in snapshot[c]])
        raise HTTPException(400, "Backup file could not be restored (conflicting or invalid records). Your existing data was kept.")
    restored_fy = {f.get("id") for f in cols["financial_years"]}
    for ctr in cols.get("counters") or []:
        if isinstance(ctr.get("_id"), str) and ctr["_id"].split(":")[0] in restored_fy:
            await db.counters.update_one({"_id": ctr["_id"]}, {"$set": {"seq": ctr.get("seq", 0)}}, upsert=True)
    await audit("system", "restore", "restore", user, note=f"{len(cols['vouchers'])} vouchers, {len(cols['ledgers'])} ledgers")
    return {"ok": True}
