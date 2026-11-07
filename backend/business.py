import math
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException

from db import db, NO_ID, new_id, now_iso
from licensing import OFFLINE, offline_status

TRIAL_DAYS = 30
TRIAL_USERS = 2
GST_RATE = 18
PLANS = {
    "basic": {"key": "basic", "name": "Single User Plan", "users_label": "1 user + 1 free user", "price": 6500, "max_users": 2},
    "pro": {"key": "pro", "name": "Multi User Plan", "users_label": "3 to 8 users", "price": 10000, "max_users": 8},
}
# Offline (standalone Windows) plans - edit prices here
OFFLINE_PLANS = {
    "offline_first": {"key": "offline_first", "name": "Offline Windows - First Year", "users_label": "Standalone PC software, up to 8 users", "price": 12000, "max_users": 8},
    "offline_renewal": {"key": "offline_renewal", "name": "Offline Annual Renewal Key", "users_label": "Required every year after the first", "price": 6500, "max_users": 8},
}
for p in list(PLANS.values()) + list(OFFLINE_PLANS.values()):
    p["gst"] = round(p["price"] * GST_RATE / 100, 2)
    p["total"] = round(p["price"] + p["gst"], 2)

SEED_LEDGERS = [
    ("Cash", "cash", 0, "Dr", "cash"), ("Bank Account", "bank", 0, "Dr", None),
    ("Sales", "sales", 0, "Dr", "sales"), ("Purchase", "purchase", 0, "Dr", "purchase"),
    ("CGST", "duties_taxes", 0, "Cr", "cgst"), ("SGST", "duties_taxes", 0, "Cr", "sgst"), ("IGST", "duties_taxes", 0, "Cr", "igst"),
    ("Capital Account", "capital", 0, "Cr", None), ("Rent Expense", "indirect_expense", 0, "Dr", None),
    ("Salary", "indirect_expense", 0, "Dr", None),
]


def fy_doc(start_year: int, bid: str) -> dict:
    return {"id": new_id(), "business_id": bid, "name": f"{start_year}-{str(start_year + 1)[-2:]}",
            "start_date": f"{start_year}-04-01", "end_date": f"{start_year + 1}-03-31",
            "locked": False, "is_active": False, "created_at": now_iso()}


def _days_left(iso: str) -> int:
    return math.ceil((datetime.fromisoformat(iso) - datetime.now(timezone.utc)).total_seconds() / 86400)


def status_of(b: dict) -> dict:
    if OFFLINE:
        return offline_status()
    now = now_iso()
    if b.get("subscription_ends") and b["subscription_ends"] > now:
        return {"status": "active", "ends_at": b["subscription_ends"], "days_left": _days_left(b["subscription_ends"]),
                "max_users": PLANS[b["plan"]]["max_users"], "plan": b["plan"]}
    if b.get("trial_ends", "") > now and not b.get("subscription_ends"):
        return {"status": "trial", "ends_at": b["trial_ends"], "days_left": _days_left(b["trial_ends"]), "max_users": TRIAL_USERS, "plan": "trial"}
    ends = b.get("subscription_ends") or b.get("trial_ends")
    return {"status": "expired", "ends_at": ends, "days_left": 0, "max_users": TRIAL_USERS, "plan": b.get("plan", "trial")}


async def get_business(bid: str) -> dict:
    b = await db.businesses.find_one({"id": bid}, NO_ID)
    if not b:
        raise HTTPException(404, "Business not found")
    return b


async def seed_business(bid: str, company: dict, ledgers=SEED_LEDGERS):
    await db.settings.insert_one({"id": new_id(), "business_id": bid, "company_name": company.get("name", "My Business"),
                                  "address": company.get("address", ""), "state": company.get("state", ""),
                                  "gstin": company.get("gstin", ""), "phone": company.get("phone", ""), "email": company.get("email", ""),
                                  "gst_rates": [0, 5, 12, 18, 28], "upi_id": "", "bank_name": "", "bank_account": "", "bank_ifsc": "",
                                  "invoice_terms": "Goods once sold will not be taken back.", "logo_path": None})
    today = date.today()
    fy = fy_doc(today.year if today.month >= 4 else today.year - 1, bid)
    fy["is_active"] = True
    await db.financial_years.insert_one(fy)
    await db.ledgers.insert_many([{
        "id": new_id(), "business_id": bid, "name": n, "name_lower": n.lower(), "group": g, "opening_balance": ob,
        "opening_type": t, "system_key": k, "gstin": "", "state": "", "phone": "", "email": "", "address": "",
        "active": True, "created_at": now_iso()} for n, g, ob, t, k in ledgers])


async def create_business(name: str, owner_email: str, phone: str = "", state: str = "", gstin: str = "") -> dict:
    trial_ends = (datetime.now(timezone.utc) + timedelta(days=TRIAL_DAYS)).isoformat()
    b = {"id": new_id(), "name": name.strip(), "owner_email": owner_email, "phone": phone, "plan": "trial",
         "trial_ends": trial_ends, "subscription_ends": None, "created_at": now_iso()}
    await db.businesses.insert_one(b)
    await seed_business(b["id"], {"name": name.strip(), "state": state, "gstin": gstin, "phone": phone, "email": owner_email})
    b.pop("_id", None)
    return b


async def extend_subscription(bid: str, plan: str, days: int = 365) -> dict:
    b = await get_business(bid)
    start = max(datetime.now(timezone.utc), datetime.fromisoformat(b["subscription_ends"]) if b.get("subscription_ends") else datetime.now(timezone.utc))
    ends = (start + timedelta(days=days)).isoformat()
    await db.businesses.update_one({"id": bid}, {"$set": {"plan": plan, "subscription_ends": ends}})
    return {"subscription_ends": ends, "plan": plan}


async def migrate_legacy():
    """Assign pre-multi-business data to a default business."""
    legacy_admin = await db.users.find_one({"business_id": {"$exists": False}}, NO_ID)
    if not legacy_admin:
        return
    s = await db.settings.find_one({"id": "company"}, NO_ID) or {}
    b = {"id": new_id(), "name": s.get("company_name", "My Business"), "owner_email": legacy_admin["email"], "phone": "",
         "plan": "pro", "trial_ends": now_iso(), "subscription_ends": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
         "created_at": now_iso()}
    await db.businesses.insert_one(b)
    for c in ("ledgers", "vouchers", "financial_years", "audit_logs", "settings"):
        await db[c].update_many({"business_id": {"$exists": False}}, {"$set": {"business_id": b["id"]}})
    await db.settings.update_many({"business_id": b["id"]}, {"$set": {"upi_id": "", "bank_name": "", "bank_account": "", "bank_ifsc": "",
                                                                       "invoice_terms": "", "logo_path": None}})
    await db.users.update_many({"business_id": {"$exists": False}}, {"$set": {"business_id": b["id"]}})
