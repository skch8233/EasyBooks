import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from auth import ANY, ADMIN, ADMIN_WRITE, create_token
from business import create_business, get_business, status_of
from db import db, NO_ID, now_iso, audit, clean

router = APIRouter(prefix="/api/ca")
BType = Literal["company", "llp", "partnership", "proprietorship"]
MRole = Literal["admin", "accountant", "viewer"]


class ClientIn(BaseModel):
    business_name: str
    business_type: BType = "proprietorship"
    state: str = ""
    gstin: str = ""
    phone: str = ""


class SwitchIn(BaseModel):
    business_id: str


class AccessIn(BaseModel):
    email: EmailStr
    role: MRole = "accountant"


def _home(user):
    return user.get("home_business_id") or user["business_id"], user.get("home_role") or user["role"]


async def _summary(bid: str, role: str, current: str) -> dict:
    b = await get_business(bid) or {}
    s = await db.settings.find_one({"business_id": bid}, NO_ID) or {}
    fy = await db.financial_years.find_one({"business_id": bid, "is_active": True}, NO_ID) \
        or await db.financial_years.find_one({"business_id": bid}, NO_ID, sort=[("start_date", -1)]) or {}
    q = {"business_id": bid, "status": "active"}
    if fy:
        q["date"] = {"$gte": fy["start_date"], "$lte": fy["end_date"]}
    tags = await db.vouchers.distinct("system_tag", {**q, "system_tag": {"$regex": "^(depreciation|tax):"}})
    last = await db.vouchers.find_one(q, {"_id": 0, "date": 1}, sort=[("date", -1)])
    st = status_of(b) if b else {"status": "unknown"}
    return {"id": bid, "name": s.get("company_name") or b.get("name", ""), "role": role, "current": bid == current,
            "business_type": s.get("business_type") or "proprietorship", "gstin": s.get("gstin", ""), "state": s.get("state", ""),
            "fy": fy.get("name", ""), "fy_end": fy.get("end_date", ""), "vouchers": await db.vouchers.count_documents(q),
            "last_entry": (last or {}).get("date", ""), "depreciation_posted": any(t.startswith("depreciation:") for t in tags),
            "tax_posted": any(t.startswith("tax:") for t in tags), "plan_status": st["status"]}


@router.get("/businesses")
async def my_businesses(user=Depends(ANY)):
    home, home_role = _home(user)
    out = [await _summary(home, home_role, user["business_id"])]
    out[0]["home"] = True
    ms = await db.memberships.find({"user_id": user["id"]}, NO_ID).sort("added_at", 1).to_list(500)
    for m in ms:
        if m["business_id"] != home:
            out.append(await _summary(m["business_id"], m["role"], user["business_id"]))
    return out


@router.post("/switch")
async def switch(body: SwitchIn, user=Depends(ANY)):
    home, home_role = _home(user)
    if body.business_id == home:
        u = {**user, "business_id": home, "role": home_role}
        u.pop("home_business_id", None), u.pop("home_role", None)
        return {"token": create_token(user), "user": clean(u)}
    m = await db.memberships.find_one({"user_id": user["id"], "business_id": body.business_id}, NO_ID)
    if not m:
        raise HTTPException(403, "You do not have access to this business")
    u = {**user, "home_business_id": home, "home_role": home_role, "business_id": body.business_id, "role": m["role"]}
    return {"token": create_token(user, body.business_id), "user": clean(u)}


@router.post("/clients")
async def add_client(body: ClientIn, user=Depends(ANY)):
    name = body.business_name.strip()
    if not name:
        raise HTTPException(400, "Client business name is required")
    g = body.gstin.strip().upper()
    if g and not re.match(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$", g):
        raise HTTPException(400, "Invalid GSTIN format")
    if _home(user)[1] == "viewer":
        raise HTTPException(403, "Viewers cannot add client businesses")
    biz = await create_business(name, user["email"], body.phone, body.state, g)
    await db.settings.update_one({"business_id": biz["id"]}, {"$set": {"business_type": body.business_type}})
    await db.memberships.insert_one({"user_id": user["id"], "business_id": biz["id"], "role": "admin", "added_by": user["id"], "added_at": now_iso()})
    await audit("business", biz["id"], "ca_client_created", {**user, "business_id": biz["id"]}, note=f"Client business created by {user['email']}")
    return await _summary(biz["id"], "admin", user["business_id"])


@router.get("/access")
async def list_access(user=Depends(ADMIN)):
    ms = await db.memberships.find({"business_id": user["business_id"]}, NO_ID).sort("added_at", 1).to_list(500)
    users = {u["id"]: u for u in await db.users.find({"id": {"$in": [m["user_id"] for m in ms]}}, {"_id": 0, "id": 1, "name": 1, "email": 1}).to_list(500)}
    return [{"user_id": m["user_id"], "role": m["role"], "added_at": m["added_at"], "name": users.get(m["user_id"], {}).get("name", ""),
             "email": users.get(m["user_id"], {}).get("email", "")} for m in ms]


@router.post("/access")
async def grant_access(body: AccessIn, user=Depends(ADMIN_WRITE)):
    target = await db.users.find_one({"email": body.email.lower()}, NO_ID)
    if not target:
        raise HTTPException(404, "No EASYTALLY BOOKS account uses this email. Ask your CA to sign up first, then add them here.")
    if target["id"] == user["id"]:
        raise HTTPException(400, "You cannot change your own access")
    if target["business_id"] == user["business_id"]:
        raise HTTPException(400, "This person is already a user of this business. Change their role under Settings > Users.")
    await db.memberships.update_one({"user_id": target["id"], "business_id": user["business_id"]},
                                    {"$set": {"role": body.role}, "$setOnInsert": {"added_by": user["id"], "added_at": now_iso()}}, upsert=True)
    await audit("membership", target["id"], "grant", user, after={"email": target["email"], "role": body.role})
    return {"ok": True, "name": target["name"], "email": target["email"], "role": body.role}


@router.delete("/access/{uid}")
async def revoke_access(uid: str, user=Depends(ADMIN_WRITE)):
    if uid == user["id"]:
        raise HTTPException(400, "You cannot remove your own access")
    m = await db.memberships.find_one({"user_id": uid, "business_id": user["business_id"]}, NO_ID)
    if m and m["role"] == "admin":
        others = await db.users.count_documents({"business_id": user["business_id"], "role": "admin", "active": True}) \
            + await db.memberships.count_documents({"business_id": user["business_id"], "role": "admin", "user_id": {"$ne": uid}})
        if not others:
            raise HTTPException(400, "This is the only admin of this business, so their access cannot be removed")
    r = await db.memberships.delete_one({"user_id": uid, "business_id": user["business_id"]})
    if not r.deleted_count:
        raise HTTPException(404, "Access not found")
    await audit("membership", uid, "revoke", user)
    return {"ok": True}
