import math
import os
import secrets
from datetime import datetime, timezone
from typing import Literal

import razorpay
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import ANY, ADMIN, SUPER
from business import PLANS, TRIAL_USERS, get_business, status_of, extend_subscription
from db import db, NO_ID, new_id, now_iso, audit, clean
from emailer import create_invoice, email_purchase

router = APIRouter(prefix="/api")
PlanKey = Literal["basic", "pro"]
ALERT_DAYS = 30


def _rzp():
    kid, sec = os.environ.get("RAZORPAY_KEY_ID", "").strip(), os.environ.get("RAZORPAY_KEY_SECRET", "").strip()
    return (razorpay.Client(auth=(kid, sec)), kid) if kid and sec else (None, None)


def _days_left(iso: str) -> int:
    return math.ceil((datetime.fromisoformat(iso) - datetime.now(timezone.utc)).total_seconds() / 86400)


def new_key() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "EB-" + "-".join("".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(4))


async def issue_licence(bid: str, plan: str, expires_at: str, source: str) -> dict:
    doc = {"id": new_id(), "business_id": bid, "key": new_key(), "plan": plan, "max_devices": PLANS[plan]["max_users"],
           "activations": [], "issued_at": now_iso(), "expires_at": expires_at, "status": "active", "source": source}
    await db.licences.insert_one(doc)
    return clean(doc)


def licence_view(l: dict) -> dict:
    days = _days_left(l["expires_at"])
    status = "revoked" if l["status"] == "revoked" else ("expired" if days < 0 else "active")
    return {**clean(l), "days_left": max(days, 0), "state": status, "alert": status == "active" and days <= ALERT_DAYS}


class OrderIn(BaseModel):
    plan: PlanKey


class VerifyIn(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class ActivateIn(BaseModel):
    key: str
    machine_id: str
    device_name: str = ""


class DeviceIn(BaseModel):
    machine_id: str


class ExtendIn(BaseModel):
    plan: PlanKey
    days: int = 365
    issue_licence: bool = True


@router.get("/billing/plans")
async def plans(user=Depends(ANY)):
    _, kid = _rzp()
    return {"plans": list(PLANS.values()), "payments_enabled": bool(kid), "trial_users": TRIAL_USERS}


@router.get("/billing/status")
async def billing_status(user=Depends(ANY)):
    b = await get_business(user["business_id"])
    st = status_of(b)
    users = await db.users.count_documents({"business_id": b["id"], "active": True})
    return {"business": clean(b), **st, "active_users": users, "alert": st["status"] == "expired" or st["days_left"] <= ALERT_DAYS}


@router.get("/billing/payments")
async def payments(user=Depends(ADMIN)):
    rows = await db.payments.find({"business_id": user["business_id"]}, NO_ID).sort("created_at", -1).to_list(100)
    return clean(rows)


@router.post("/billing/order")
async def create_order(body: OrderIn, user=Depends(ADMIN)):
    client, kid = _rzp()
    if not client:
        raise HTTPException(503, "Online payments are not configured yet. Please contact support.")
    bid = user["business_id"]
    users = await db.users.count_documents({"business_id": bid, "active": True})
    if users > PLANS[body.plan]["max_users"]:
        raise HTTPException(400, f"You have {users} active users. This plan allows {PLANS[body.plan]['max_users']}. Disable users or pick the Multi User plan.")
    plan = PLANS[body.plan]
    amount = int(round(plan["total"] * 100))
    try:
        order = client.order.create({"amount": amount, "currency": "INR", "receipt": f"eb_{bid[:8]}_{int(datetime.now().timestamp())}",
                                     "payment_capture": 1, "notes": {"business_id": bid, "plan": body.plan}})
    except Exception as exc:
        raise HTTPException(502, f"Payment gateway error: {exc}")
    await db.payments.insert_one({"id": new_id(), "business_id": bid, "order_id": order["id"], "plan": body.plan, "amount": plan["total"],
                                  "base": plan["price"], "gst": plan["gst"], "status": "created", "created_by": user["email"], "created_at": now_iso()})
    b = await get_business(bid)
    return {"order_id": order["id"], "amount": amount, "currency": "INR", "key_id": kid, "plan": plan,
            "business_name": b["name"], "email": user["email"]}


@router.post("/billing/verify")
async def verify_payment(body: VerifyIn, user=Depends(ADMIN)):
    client, _ = _rzp()
    if not client:
        raise HTTPException(503, "Online payments are not configured")
    pay = await db.payments.find_one({"order_id": body.razorpay_order_id, "business_id": user["business_id"]}, NO_ID)
    if not pay:
        raise HTTPException(404, "Order not found")
    if pay["status"] == "paid":
        return {"ok": True, "already": True}
    try:
        client.utility.verify_payment_signature({"razorpay_order_id": body.razorpay_order_id, "razorpay_payment_id": body.razorpay_payment_id,
                                                 "razorpay_signature": body.razorpay_signature})
    except Exception:
        await db.payments.update_one({"order_id": body.razorpay_order_id}, {"$set": {"status": "failed"}})
        raise HTTPException(400, "Payment verification failed")
    res = await db.payments.update_one({"order_id": body.razorpay_order_id, "status": {"$ne": "paid"}},
                                       {"$set": {"status": "paid", "payment_id": body.razorpay_payment_id, "paid_at": now_iso()}})
    if not res.modified_count:
        return {"ok": True, "already": True}
    sub = await extend_subscription(user["business_id"], pay["plan"])
    lic = await issue_licence(user["business_id"], pay["plan"], sub["subscription_ends"], "payment")
    await db.payments.update_one({"order_id": body.razorpay_order_id}, {"$set": {"licence_key": lic["key"], "valid_till": sub["subscription_ends"]}})
    await audit("subscription", user["business_id"], "payment", user, note=f"{pay['plan']} plan paid, valid till {sub['subscription_ends'][:10]}")
    b = await get_business(user["business_id"])
    inv = await create_invoice(buyer={"name": user["name"], "business_name": b["name"], "email": user["email"], "gstin": b.get("gstin", "")},
                               item=f"Easy Books Online - {PLANS[pay['plan']]['name']}", base=PLANS[pay["plan"]]["price"],
                               licence_key=lic["key"], payment_id=body.razorpay_payment_id, source="payment")
    mail = await email_purchase(to=user["email"], name=user["name"], inv=inv, expires=sub["subscription_ends"])
    return {"ok": True, **sub, "licence_key": lic["key"], "invoice_no": inv["number"], "email_status": mail["status"]}


@router.get("/licences")
async def my_licences(user=Depends(ADMIN)):
    rows = await db.licences.find({"business_id": user["business_id"]}, NO_ID).sort("issued_at", -1).to_list(100)
    return [licence_view(l) for l in rows]


@router.post("/licences/{lid}/deactivate-device")
async def deactivate_device(lid: str, body: DeviceIn, user=Depends(ADMIN)):
    res = await db.licences.update_one({"id": lid, "business_id": user["business_id"]}, {"$pull": {"activations": {"machine_id": body.machine_id}}})
    if not res.matched_count:
        raise HTTPException(404, "Licence not found")
    await audit("licence", lid, "deactivate_device", user, note=body.machine_id)
    return {"ok": True}


async def _licence_by_key(key: str) -> dict:
    l = await db.licences.find_one({"key": key.strip().upper()}, NO_ID)
    if not l:
        raise HTTPException(404, "Invalid licence key")
    return l


def _public(l: dict, b: dict, activated: bool) -> dict:
    v = licence_view(l)
    msg = {"revoked": "Licence has been revoked", "expired": "Licence expired. Please renew your annual subscription."}.get(v["state"])
    if not msg:
        msg = f"Licence valid for {v['days_left']} more days" + (". Renew soon to avoid interruption." if v["alert"] else ".")
    return {"valid": v["state"] == "active" and activated, "state": v["state"], "activated": activated, "expires_at": l["expires_at"],
            "days_left": v["days_left"], "alert": v["alert"], "message": msg, "business_name": b["name"], "plan": l["plan"],
            "devices_used": len(l["activations"]), "max_devices": l["max_devices"]}


@router.post("/licence/activate")
async def activate(body: ActivateIn):
    l = await _licence_by_key(body.key)
    b = await get_business(l["business_id"])
    if licence_view(l)["state"] != "active":
        return _public(l, b, False)
    if not any(a["machine_id"] == body.machine_id for a in l["activations"]):
        res = await db.licences.update_one(
            {"id": l["id"], "activations.machine_id": {"$ne": body.machine_id}, "$expr": {"$lt": [{"$size": "$activations"}, l["max_devices"]]}},
            {"$push": {"activations": {"machine_id": body.machine_id, "device_name": body.device_name or body.machine_id, "activated_at": now_iso()}}})
        l = await _licence_by_key(body.key)
        if not res.modified_count and not any(a["machine_id"] == body.machine_id for a in l["activations"]):
            raise HTTPException(400, f"Device limit reached ({l['max_devices']}). Deactivate a device from Subscription page.")
    return _public(l, b, True)


@router.post("/licence/validate")
async def validate(body: ActivateIn):
    l = await _licence_by_key(body.key)
    b = await get_business(l["business_id"])
    return _public(l, b, any(a["machine_id"] == body.machine_id for a in l["activations"]))


@router.get("/platform/businesses")
async def all_businesses(user=Depends(SUPER)):
    rows = await db.businesses.find({}, NO_ID).sort("created_at", -1).to_list(5000)
    out = []
    for b in rows:
        out.append({**clean(b), **status_of(b), "users": await db.users.count_documents({"business_id": b["id"], "active": True})})
    return out


@router.post("/platform/businesses/{bid}/extend")
async def platform_extend(bid: str, body: ExtendIn, user=Depends(SUPER)):
    if not 1 <= body.days <= 3650:
        raise HTTPException(400, "Days must be between 1 and 3650")
    sub = await extend_subscription(bid, body.plan, body.days)
    lic = await issue_licence(bid, body.plan, sub["subscription_ends"], "manual") if body.issue_licence else None
    await audit("subscription", bid, "manual_extend", user, note=f"{body.plan} +{body.days} days")
    return {**sub, "licence_key": lic["key"] if lic else None}


@router.post("/platform/licences/{lid}/revoke")
async def revoke(lid: str, user=Depends(SUPER)):
    lic = await db.licences.find_one({"id": lid}, NO_ID)
    if not lic:
        raise HTTPException(404, "Licence not found")
    await db.licences.update_one({"id": lid}, {"$set": {"status": "revoked"}})
    await audit("licence", lid, "revoke", {**user, "business_id": lic["business_id"]}, note=f"Revoked by platform admin {user['email']}")
    return {"ok": True}
