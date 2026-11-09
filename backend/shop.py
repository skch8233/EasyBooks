import os
import re
import secrets
from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field, field_validator

from auth import ADMIN, SUPER, create_token, hash_password
from billing import _rzp, new_key
from business import OFFLINE_PLANS, create_business
from db import db, NO_ID, new_id, now_iso, audit, clean
from emailer import create_invoice, email_purchase
from licensing import OFFLINE, check_pc, offline_status, save_code, sign_code, trial_state, verify_code

router = APIRouter(prefix="/api")
OfflinePlan = Literal["offline_first", "offline_renewal", "offline_multi_first", "offline_multi_renewal"]
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


def _pcs(lic: dict) -> list:
    if "machines" in lic:
        return lic["machines"] or []
    return [{"id": lic["machine_id"], "at": lic.get("bound_at")}] if lic.get("machine_id") else []


def _tier(lic: dict) -> str:
    return lic.get("tier") or OFFLINE_PLANS.get(lic.get("plan") or "offline_first", OFFLINE_PLANS["offline_first"])["tier"]


def _max_pcs(lic: dict) -> int:
    return lic.get("max_pcs") or (8 if _tier(lic) == "multi" else 1)


def _sign(lic: dict, mid: str | None) -> str | None:
    plan = lic.get("plan") or "offline_first"
    return sign_code({"k": lic["key"], "n": lic["name"], "b": lic["business_name"], "p": plan, "i": date.today().isoformat(), "e": lic["expires"],
                      "d": OFFLINE_PLANS[plan]["max_users"], "t": _tier(lic), "c": _max_pcs(lic), "m": mid}) if mid else None


def _single_code(lic: dict) -> str | None:
    pcs = _pcs(lic)
    return _sign(lic, pcs[0]["id"]) if len(pcs) == 1 else None


async def issue_offline(b: Buyer, source: str, payment_id: str = "") -> dict:
    today, plan = date.today(), OFFLINE_PLANS[b.plan]
    if plan["renewal"]:
        lic = await _existing(b.licence_key)
        if _tier(lic) != plan["tier"]:
            want = "Multi-PC renewal" if _tier(lic) == "multi" else "Single-PC renewal"
            raise HTTPException(400, f"This key is a {_tier(lic).title()}-PC licence. Choose {want}.")
        start = max(today, date.fromisoformat(lic["expires"]))
        expires = (start + timedelta(days=365)).isoformat()
        entry = {"plan": b.plan, "issued": now_iso(), "expires": expires, "source": source, "payment_id": payment_id}
        await db.offline_licences.update_one({"key": lic["key"]}, {"$set": {"expires": expires, "plan": b.plan, "tier": plan["tier"], "max_pcs": plan["pcs"],
                                                                            "machines": _pcs(lic)}, "$push": {"history": entry}})
    else:
        entry = {"plan": b.plan, "issued": now_iso(), "expires": (today + timedelta(days=365)).isoformat(), "source": source, "payment_id": payment_id}
        lic = {"key": new_key()}
        await db.offline_licences.insert_one({"id": new_id(), "key": lic["key"], "name": b.name, "email": b.email.lower(), "phone": b.phone, "gstin": b.gstin,
                                              "business_name": b.business_name or b.name, "plan": b.plan, "tier": plan["tier"], "max_pcs": plan["pcs"],
                                              "expires": entry["expires"], "machines": [], "history": [entry], "created_at": now_iso()})
    lic = await _existing(lic["key"])
    code = _single_code(lic)
    inv = await create_invoice(buyer={"name": lic["name"], "business_name": lic["business_name"], "email": lic["email"], "phone": b.phone, "gstin": b.gstin or lic.get("gstin", "")},
                               item=plan["name"], base=plan["price"], licence_key=lic["key"], payment_id=payment_id, source=source)
    mail = await email_purchase(to=lic["email"], name=lic["name"], inv=inv, expires=lic["expires"], code=code, offline=True)
    await db.offline_licences.update_one({"key": lic["key"]}, {"$set": {"last_invoice": inv["number"], "last_email": mail}})
    pcs = _pcs(lic)
    return {"key": lic["key"], "code": code, "expires": lic["expires"], "plan": b.plan, "tier": plan["tier"], "max_pcs": plan["pcs"],
            "pcs_used": len(pcs), "name": lic["name"], "business_name": lic["business_name"], "machine_id": pcs[0]["id"] if len(pcs) == 1 else None,
            "invoice_no": inv["number"], "email_status": mail["status"], "email": lic["email"]}


@router.post("/shop/activate")
async def shop_activate(body: BindIn):
    mid = body.machine_id.strip().upper()
    if not MACHINE_RE.match(mid):
        raise HTTPException(400, "Enter the Machine ID exactly as shown on the Licence screen (XXXX-XXXX-XXXX-XXXX)")
    lic = await _existing(body.key)
    if lic["expires"] < date.today().isoformat():
        raise HTTPException(400, f"This licence expired on {lic['expires']}. Buy a renewal key first.")
    if "machines" not in lic:
        await db.offline_licences.update_one({"key": lic["key"], "machines": {"$exists": False}}, {"$set": {"machines": _pcs(lic)}})
    limit = _max_pcs(lic)
    if not any(p["id"] == mid for p in _pcs(lic)):
        res = await db.offline_licences.update_one(
            {"key": lic["key"], "machines.id": {"$ne": mid}, "$expr": {"$lt": [{"$size": "$machines"}, limit]}},
            {"$push": {"machines": {"id": mid, "at": now_iso()}}})
        lic = await _existing(body.key)
        if not res.modified_count and not any(p["id"] == mid for p in _pcs(lic)):
            msg = ("This licence is already activated on another computer. Each Single-PC key works on one PC only." if limit == 1
                   else f"This key is already active on all {limit} computers allowed.")
            raise HTTPException(409, msg + " Contact Hannusoft to move it to a new PC.")
    pcs = _pcs(lic)
    return {"key": lic["key"], "code": _sign(lic, mid), "expires": lic["expires"], "machine_id": mid, "name": lic["name"], "business_name": lic["business_name"],
            "tier": _tier(lic), "max_pcs": limit, "pcs_used": len(pcs)}


class ResetIn(BaseModel):
    machine_id: str = ""


@router.post("/platform/offline-licences/{key}/reset-pc")
async def reset_pc(key: str, body: ResetIn | None = None, user=Depends(SUPER)):
    lic = await _existing(key)
    mid = (body.machine_id if body else "").strip().upper()
    keep = [p for p in _pcs(lic) if mid and p["id"] != mid]
    await db.offline_licences.update_one({"key": lic["key"]}, {"$set": {"machines": keep, "machine_id": None, "code": None}})
    await audit("offline_licence", lic["key"], "reset_pc", user, note=f"removed {mid or 'all PCs'}")
    return {"ok": True, "pcs_used": len(keep)}


@router.post("/platform/offline-licences/{key}/resend")
async def resend(key: str, user=Depends(SUPER)):
    lic = await _existing(key)
    inv = await db.hs_invoices.find_one({"number": lic.get("last_invoice")}, NO_ID)
    if not inv:
        raise HTTPException(404, "No invoice found for this licence")
    mail = await email_purchase(to=lic["email"], name=lic["name"], inv=inv, expires=lic["expires"], code=_single_code(lic), offline=True)
    await db.offline_licences.update_one({"key": lic["key"]}, {"$set": {"last_email": mail}})
    if mail["status"] != "sent":
        raise HTTPException(502, "Email could not be sent. Try again later.")
    return mail


@router.post("/shop/order")
async def shop_order(b: Buyer):
    client, kid = _rzp()
    if not client:
        raise HTTPException(503, "Online payments are not enabled yet. Please contact Hannusoft to buy your key.")
    if OFFLINE_PLANS[b.plan]["renewal"]:
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
    if d:
        return clean(d)
    url = os.environ.get("OFFLINE_DOWNLOAD_URL", "").strip()
    return {"url": url, "version": "Latest", "size": "", "notes": "Auto-built on GitHub", "updated_at": None} if url else {"url": None}


@router.put("/platform/download")
async def set_download(body: DownloadIn, user=Depends(SUPER)):
    if not body.url.startswith(("https://", "http://")):
        raise HTTPException(400, "Enter a full download link starting with https://")
    await db.app_releases.update_one({"id": "offline-windows"}, {"$set": {**body.model_dump(), "updated_at": now_iso()}}, upsert=True)
    return await download_info()


@router.get("/platform/offline-licences")
async def list_offline(user=Depends(SUPER)):
    rows = await db.offline_licences.find({}, {**NO_ID, "history": 0}).sort("created_at", -1).to_list(2000)
    return [{**clean(r), "machines": _pcs(r), "tier": _tier(r), "max_pcs": _max_pcs(r)} for r in rows]


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


@router.post("/offline/session")
async def offline_session():
    """Offline app has no login: open the books as the local owner (server listens on 127.0.0.1 only)."""
    if not OFFLINE:
        raise HTTPException(404, "Not found")
    user = await db.users.find_one({"active": True, "role": "admin"}, NO_ID, sort=[("created_at", 1)])
    if user:
        trial_state(has_data=True)
    else:
        email = "owner@easybooks.offline"
        biz = await create_business("My Business", email)
        user = {"id": new_id(), "business_id": biz["id"], "name": "Owner", "email": email, "role": "admin", "active": True,
                "password_hash": hash_password(secrets.token_urlsafe(24)), "created_at": now_iso()}
        await db.users.insert_one(user)
        trial_state()
    user = clean(user)
    return {"token": create_token(user), "user": user}


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
    if p["e"] < (trial_state().get("effective_today") or date.today().isoformat()):
        raise HTTPException(400, f"This activation code expired on {p['e']}. Buy a renewal key.")
    save_code(body.code)
    await audit("offline_licence", p["k"], "activate", user, note=f"valid till {p['e']}")
    return offline_status()
