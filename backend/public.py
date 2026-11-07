import secrets

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from auth import ANY
from billing import _rzp
from business import PLANS, TRIAL_DAYS, TRIAL_USERS
from db import db, NO_ID, clean
from routes_admin import _storage

router = APIRouter(prefix="/api")
COMPANY_FIELDS = ("company_name", "address", "state", "gstin", "phone", "email", "upi_id", "bank_name", "bank_account", "bank_ifsc", "invoice_terms")
PARTY_FIELDS = ("name", "gstin", "state", "address", "phone")
VOUCHER_FIELDS = ("voucher_type", "voucher_no", "date", "party_name", "party_ledger_id", "gst_type", "items", "totals", "amount", "narration", "reference_no", "status", "entries")


@router.get("/public/plans")
async def public_plans():
    _, kid = _rzp()
    return {"plans": list(PLANS.values()), "trial_days": TRIAL_DAYS, "trial_users": TRIAL_USERS, "payments_enabled": bool(kid)}


@router.post("/vouchers/{vid}/share")
async def share_voucher(vid: str, user=Depends(ANY)):
    v = await db.vouchers.find_one({"id": vid, "business_id": user["business_id"]}, NO_ID)
    if not v:
        raise HTTPException(404, "Voucher not found")
    if v["voucher_type"] != "sales" or v.get("status") == "cancelled":
        raise HTTPException(400, "Only active sales invoices can be shared")
    token = v.get("share_token") or secrets.token_urlsafe(16)
    if not v.get("share_token"):
        await db.vouchers.update_one({"id": vid}, {"$set": {"share_token": token}})
    party = await db.ledgers.find_one({"id": v["party_ledger_id"], "business_id": user["business_id"]}, NO_ID) or {}
    return {"token": token, "phone": party.get("phone", "")}


async def _shared(token: str) -> dict:
    v = await db.vouchers.find_one({"share_token": token}, NO_ID) if token else None
    if not v:
        raise HTTPException(404, "Invoice not found")
    return v


@router.get("/public/invoice/{token}")
async def public_invoice(token: str):
    v = await _shared(token)
    s = await db.settings.find_one({"business_id": v["business_id"]}, NO_ID) or {}
    p = await db.ledgers.find_one({"id": v["party_ledger_id"], "business_id": v["business_id"]}, NO_ID) or {}
    return {"voucher": clean({k: v.get(k) for k in VOUCHER_FIELDS if k not in ("entries", "party_ledger_id")}),
            "settings": {**{k: s.get(k, "") for k in COMPANY_FIELDS}, "has_logo": bool(s.get("logo_path"))},
            "party": {k: p.get(k, "") for k in PARTY_FIELDS}}


@router.get("/public/invoice/{token}/logo")
async def public_logo(token: str):
    v = await _shared(token)
    s = await db.settings.find_one({"business_id": v["business_id"]}, NO_ID) or {}
    if not s.get("logo_path"):
        raise HTTPException(404, "No logo")
    try:
        r = _storage("GET", s["logo_path"])
    except Exception:
        raise HTTPException(404, "Logo not available")
    return Response(content=r.content, media_type=s.get("logo_type", "image/png"))
