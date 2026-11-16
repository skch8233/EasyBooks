import re

from fastapi import APIRouter, Depends

from auth import ANY
from db import db, NO_ID

router = APIRouter(prefix="/api/gstin")
CODES = {"01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh", "05": "Uttarakhand", "06": "Haryana", "07": "Delhi", "08": "Rajasthan",
         "09": "Uttar Pradesh", "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur", "15": "Mizoram", "16": "Tripura", "17": "Meghalaya",
         "18": "Assam", "19": "West Bengal", "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat", "26": "Dadra and Nagar Haveli and Daman and Diu",
         "27": "Maharashtra", "29": "Karnataka", "30": "Goa", "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu", "34": "Puducherry", "35": "Andaman and Nicobar Islands",
         "36": "Telangana", "37": "Andhra Pradesh", "38": "Ladakh", "97": "Other Territory"}
CH = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def check_digit(g14: str) -> str:
    total = 0
    for i, c in enumerate(g14):
        p = CH.index(c) * (2 if i % 2 else 1)
        total += p // 36 + p % 36
    return CH[(36 - total % 36) % 36]


def parse(g: str) -> dict:
    g = (g or "").strip().upper()
    if not re.match(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$", g):
        return {"gstin": g, "valid": False, "error": "GSTIN must be 15 characters like 27AAPFU0939F1ZV"}
    if g[:2] not in CODES:
        return {"gstin": g, "valid": False, "error": "First two digits are not a valid state code"}
    if check_digit(g[:14]) != g[14]:
        return {"gstin": g, "valid": False, "error": "Check digit does not match - please re-check the GSTIN"}
    return {"gstin": g, "valid": True, "state_code": g[:2], "state_name": CODES[g[:2]], "pan": g[2:12]}


@router.get("/{g}")
async def lookup(g: str, user=Depends(ANY)):
    r = parse(g)
    if not r["valid"]:
        return r
    bid = user["business_id"]
    saved = None
    led = await db.ledgers.find({"business_id": bid, "gstin": r["gstin"]}, NO_ID).sort("updated_at", -1).to_list(1)
    party = await db.erp_parties.find({"business_id": bid, "gstin": r["gstin"]}, NO_ID).sort("updated_at", -1).to_list(1)
    if party:
        p = party[0]
        saved = {"name": p["company_name"], "address": p.get("address", ""), "state": p.get("state", ""), "phone": p.get("mobile", ""), "email": p.get("email", ""),
                 "contact_person": p.get("contact_person", ""), "source": "party", "id": p["id"]}
    if led:
        l = led[0]
        saved = {**(saved or {}), **{k: v for k, v in {"name": l["name"], "address": l.get("address", ""), "state": l.get("state", ""), "phone": l.get("phone", ""),
                                                       "email": l.get("email", "")}.items() if v or not saved}, "ledger_id": l["id"], "source": (saved or {}).get("source", "ledger")}
    return {**r, "saved": saved}
