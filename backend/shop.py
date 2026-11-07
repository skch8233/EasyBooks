import re
from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field, field_validator

from auth import ADMIN, SUPER
from billing import _rzp, new_key
from business import OFFLINE_PLANS
from db import db, NO_ID, new_id, now_iso, audit, clean
from emailer import create_invoice, email_purchase
from licensing import OFFLINE, check_pc, offline_status, save_code, sign_code, verify_code

router = APIRouter(prefix="/api")
OfflinePlan = Literal["offline_first", "offline_renewal"]
MACHINE_RE = re.compile(r"^[0-9A-F]{4}(-[0-9A-F]{4}){3}$")
GSTIN_RE = re.compile(r"^[0-3][0-9][A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
KEY_RE = re.compile(r"^EB-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$")


class Buyer(BaseModel):
    plan: OfflinePlan
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    phone: str = ""
    business_name: str = ""
    licence_key: str = ""
    gstin: str = Field(default="", max_length=15)

    @field_validator("gstin")
    @classmethod
    def _gstin(cls, v: str) -> str:
        v = v.strip().upper()
        if v and not GSTIN_RE.match(v):
            raise ValueError("Enter a valid 15-character GSTIN (e.g. 27ABCDE1234F1Z5) or leave it blank")
        return v


class BindIn(BaseModel):
    key: str = Field(min_length=5, max_length=40)
    machine_id: str = Field(max_length=40)


class VerifyIn(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class DownloadIn(BaseModel):
    url: str = Field(min_length=8, max_length=2000)
    version: str = "1.0.0"
    size: str = ""
    notes: str = ""


class CodeIn(BaseModel):
    code: str


async def _existing(key: str, email: str = "") -> dict:
    lic = await db.offline_licences.find_one({"key": key.strip().upper()}, NO_ID)
    if not lic:
        raise HTTPException(404, "Offline licence key not found. Check the key from your first-year purchase.")
    return lic


def _sign(key: str, name: str, biz: str, plan: str, expires: str, mid: str | None) -> str | None:
    return sign_code({"k": key, "n": name, "b": biz, "p": plan, "i": date.today().isoformat(), "e": expires,
                      "d": OFFLINE_PLANS[plan]["max_users"], "m": mid}) if mid else None


async def issue_offline(b: Buyer, source: str, payment_id: str = "") -> dict:
    today = date.today()
    if b.plan == "offline_renewal":
        lic = await _existing(b.licence_key)
        start = max(today, date.fromisoformat(lic["expires"]))
        expires, key = (start + timedelta(days=365)).isoformat(), lic["key"]
    else:
        lic, key, expires = None, new_key(), (today + timedelta(days=365)).isoformat()
    name, biz = (lic or {}).get("name") or b.name, (lic or {}).get("business_name") or b.business_name or b.name
    mid = (lic or {}).get("machine_id")
    code = _sign(key, name, biz, b.plan, expires, mid)
    entry = {"plan": b.plan, "issued": now_iso(), "expires": expires, "source": source, "payment_id": payment_id}
    if lic:
        await db.offline_licences.update_one({"key": key}, {"$set": {"expires": expires, "code": code, "plan": b.plan}, "$push": {"history": entry}})
    else:
        await db.offline_licences.insert_one({"id": new_id(), "key": key, "name": name, "email": b.email.lower(), "phone": b.phone, "gstin": b.gstin.strip().upper(),
                                              "business_name": biz, "plan": b.plan, "expires": expires, "code": None, "machine_id": None,
                                              "history": [entry], "created_at": now_iso()})
    plan = OFFLINE_PLANS[b.plan]
    to = (lic or {}).get("email") or b.email.lower()
    inv = await create_invoice(buyer={"name": name, "business_name": biz, "email": to, "phone": b.phone, "gstin": b.gstin or (lic or {}).get("gstin", "")},
                               item=plan["name"], base=plan["price"], licence_key=key, payment_id=payment_id, source=source)
    mail = await email_purchase(to=to, name=name, inv=inv, expires=expires, code=code, offline=True)
    await db.offline_licences.update_one({"key": key}, {"$set": {"last_invoice": inv["number"], "last_email": mail}})
    return {"key": key, "code": code, "expires": expires, "plan": b.plan, "name": name, "business_name": biz, "machine_id": mid,
            "invoice_no": inv["number"], "email_status": mail["status"], "email": to}


@router.post("/shop/activate")
async def shop_activate(body: BindIn):
    mid = body.machine_id.strip().upper()
    if not MACHINE_RE.match(mid):
        raise HTTPException(400, "Enter the Machine ID exactly as shown on the Licence screen (XXXX-XXXX-XXXX-XXXX)")
    lic = await _existing(body.key)
    if lic["expires"] < date.today().isoformat():
        raise HTTPException(400, f"This licence expired on {lic['expires']}. Buy a renewal key first.")
    res = await db.offline_licences.update_one({"key": lic["key"], "machine_id": {"$in": [None, mid]}}, {"$set": {"machine_id": mid}})
    if not res.matched_count:
        raise HTTPException(409, "This licence is already activated on another computer. Each key works on one PC only. Contact Hannusoft to move it to a new PC.")
    code = _sign(lic["key"], lic["name"], lic["business_name"], lic.get("plan", "offline_first"), lic["expires"], mid)
    await db.offline_licences.update_one({"key": lic["key"]}, {"$set": {"code": code, "bound_at": lic.get("bound_at") or now_iso()}})
    return {"key": lic["key"], "code": code, "expires": lic["expires"], "machine_id": mid, "name": lic["name"], "business_name": lic["business_name"]}


@router.post("/platform/offline-licences/{key}/reset-pc")
async def reset_pc(key: str, user=Depends(SUPER)):
    lic = await _existing(key)
    await db.offline_licences.update_one({"key": lic["key"]}, {"$set": {"machine_id": None, "code": None, "bound_at": None}})
    await audit("offline_licence", lic["key"], "reset_pc", user, note=f"was {lic.get('machine_id')}")
    return {"ok": True}


@router.post("/platform/offline-licences/{key}/resend")
async def resend(key: str, user=Depends(SUPER)):
    lic = await _existing(key)
    inv = await db.hs_invoices.find_one({"number": lic.get("last_invoice")}, NO_ID)
    if not inv:
        raise HTTPException(404, "No invoice found for this licence")
    mail = await email_purchase(to=lic["email"], name=lic["name"], inv=inv, expires=lic["expires"], code=lic.get("code"), offline=True)
    await db.offline_licences.update_one({"key": lic["key"]}, {"$set": {"last_email": mail}})
    if mail["status"] != "sent":
        raise HTTPException(502, "Email could not be sent. Try again later.")
    return mail


@router.post("/shop/order")
async def shop_order(b: Buyer):
    client, kid = _rzp()
    if not client:
        raise HTTPException(503, "Online payments are not enabled yet. Please contact Hannusoft to buy your key.")
    if b.plan == "offline_renewal":
        if not KEY_RE.match(b.licence_key.strip().upper()):
            raise HTTPException(400, "Enter your existing offline licence key (EB-XXXX-XXXX-XXXX-XXXX)")
        await _existing(b.licence_key)
    plan = OFFLINE_PLANS[b.plan]
    try:
        order = client.order.create({"amount": int(round(plan["total"] * 100)), "currency": "INR",
                                     "receipt": f"ebo_{int(datetime.now().timestamp())}", "payment_capture": 1, "notes": {"plan": b.plan, "email": b.email}})
    except Exception as exc:
        raise HTTPException(502, f"Payment gateway error: {exc}")
    await db.shop_orders.insert_one({"id": new_id(), "order_id": order["id"], "buyer": b.model_dump(), "amount": plan["total"], "status": "created", "created_at": now_iso()})
    return {"order_id": order["id"], "amount": order["amount"], "currency": "INR", "key_id": kid, "plan": plan}


@router.post("/shop/verify")
async def shop_verify(body: VerifyIn):
    client, _ = _rzp()
    if not client:
        raise HTTPException(503, "Online payments are not enabled")
    o = await db.shop_orders.find_one({"order_id": body.razorpay_order_id}, NO_ID)
    if not o:
        raise HTTPException(404, "Order not found")
    if o["status"] == "paid":
        return o["result"]
    try:
        client.utility.verify_payment_signature(body.model_dump())
    except Exception:
        raise HTTPException(400, "Payment verification failed")
    res = await db.shop_orders.update_one({"order_id": body.razorpay_order_id, "status": "created"}, {"$set": {"status": "processing"}})
    if not res.modified_count:
        raise HTTPException(409, "Payment is being processed, refresh in a moment")
    try:
        result = await issue_offline(Buyer(**o["buyer"]), "payment", body.razorpay_payment_id)
    except Exception:
        await db.shop_orders.update_one({"order_id": body.razorpay_order_id}, {"$set": {"status": "created"}})
        raise HTTPException(500, "Payment received but the key could not be issued. Retry or contact Hannusoft with your payment ID.")
    await db.shop_orders.update_one({"order_id": body.razorpay_order_id}, {"$set": {"status": "paid", "payment_id": body.razorpay_payment_id, "result": result}})
    return result


@router.get("/shop/download")
async def download_info():
    d = await db.app_releases.find_one({"id": "offline-windows"}, NO_ID)
    return clean(d) if d else {"url": None}


@router.put("/platform/download")
async def set_download(body: DownloadIn, user=Depends(SUPER)):
    if not body.url.startswith(("https://", "http://")):
        raise HTTPException(400, "Enter a full download link starting with https://")
    await db.app_releases.update_one({"id": "offline-windows"}, {"$set": {**body.model_dump(), "updated_at": now_iso()}}, upsert=True)
    return await download_info()


@router.get("/platform/offline-licences")
async def list_offline(user=Depends(SUPER)):
    rows = await db.offline_licences.find({}, {**NO_ID, "history": 0}).sort("created_at", -1).to_list(2000)
    return clean(rows)


@router.post("/platform/offline-licences")
async def manual_offline(b: Buyer, user=Depends(SUPER)):
    res = await issue_offline(b, "manual")
    await audit("offline_licence", res["key"], "issue", user, note=f"{b.plan} till {res['expires']}")
    return res


# ---- endpoints used inside the installed offline app ----
@router.get("/offline/status")
async def offline_app_status():
    users = await db.users.count_documents({})
    return {"offline": OFFLINE, "has_users": users > 0, **(offline_status() if OFFLINE else {})}


@router.post("/offline/licence")
async def offline_activate(body: CodeIn, user=Depends(ADMIN)):
    if not OFFLINE:
        raise HTTPException(400, "Only available in the offline version")
    try:
        p = verify_code(body.code)
    except ValueError:
        raise HTTPException(400, "Invalid activation code. Copy the full code starting with EBOL1.")
    try:
        check_pc(p)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if p["e"] < date.today().isoformat():
        raise HTTPException(400, f"This activation code expired on {p['e']}. Buy a renewal key.")
    save_code(body.code)
    await audit("offline_licence", p["k"], "activate", user, note=f"valid till {p['e']}")
    return offline_status()
