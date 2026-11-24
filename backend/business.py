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
    "offline_first": {"key": "offline_first", "name": "Offline Single-PC - First Year", "users_label": "Works on 1 computer", "price": 12000, "max_users": 8, "tier": "single", "pcs": 1, "renewal": False},
    "offline_renewal": {"key": "offline_renewal", "name": "Offline Single-PC - Annual Renewal", "users_label": "Required every year after the first", "price": 6500, "max_users": 8, "tier": "single", "pcs": 1, "renewal": True},
    "offline_multi_first": {"key": "offline_multi_first", "name": "Offline Multi-PC - First Year", "users_label": "One key for up to 8 computers", "price": 18000, "max_users": 8, "tier": "multi", "pcs": 8, "renewal": False},
    "offline_multi_renewal": {"key": "offline_multi_renewal", "name": "Offline Multi-PC - Annual Renewal", "users_label": "Required every year after the first", "price": 10000, "max_users": 8, "tier": "multi", "pcs": 8, "renewal": True},
}
OFFLINE_TRIAL_DAYS = 30
ERP_PLAN = {"key": "erp", "name": "Projects / ERP add-on", "users_label": "All ERP modules for your whole business", "price": 15000, "max_users": 8}
INDUSTRIES = {
    "retail": {"label": "Retail & Shopkeepers", "modes": ["complete"]},
    "college": {"label": "Colleges & Institutes", "modes": ["complete"]},
    "hospital": {"label": "Hospitals & Clinics", "modes": ["complete"]},
    "wholesale": {"label": "Wholesalers & Distributors", "modes": ["billing", "complete"]},
    "services": {"label": "Service Agencies", "modes": ["billing", "complete"]},
}
MODE_LABEL = {"billing": "Invoice & Billing Only", "complete": "Complete Accounting & Billing"}
BASE_PRICE = {"retail_complete": 5000, "college_complete": 15000, "hospital_complete": 15000, "wholesale_billing": 2500,
              "wholesale_complete": 5000, "services_billing": 2500, "services_complete": 5000}
MULTI_USER_ADDON = 3500  # default for the 3-8 user tier; editable later in the Super Admin plan manager
for k, price in BASE_PRICE.items():
    ind, mode = k.split("_")
    name = f"{INDUSTRIES[ind]['label']} - {MODE_LABEL[mode]}"
    PLANS[k] = {"key": k, "industry": ind, "mode": mode, "tier": "base", "name": name, "users_label": "1 user + 1 free user", "price": price, "max_users": 2}
    PLANS[f"{k}_multi"] = {"key": f"{k}_multi", "industry": ind, "mode": mode, "tier": "multi", "name": f"{name} (3 to 8 users)",
                           "users_label": "3 to 8 users", "price": price + MULTI_USER_ADDON, "max_users": 8}
PLANS["basic"]["legacy"] = PLANS["pro"]["legacy"] = True


def industry_of(b: dict) -> tuple:
    ind = b.get("industry_type") if b.get("industry_type") in INDUSTRIES else "wholesale"
    mode = b.get("industry_mode") if b.get("industry_mode") in INDUSTRIES[ind]["modes"] else INDUSTRIES[ind]["modes"][-1]
    return ind, mode


for p in list(PLANS.values()) + list(OFFLINE_PLANS.values()) + [ERP_PLAN]:
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
    d = parse_dt(iso)
    return math.ceil((d - datetime.now(timezone.utc)).total_seconds() / 86400) if d else 0


GRACE_DAYS = 7


def status_of(b: dict) -> dict:
    if OFFLINE:
        return offline_status()
    st = _status(b)
    if b.get("max_users_override"):
        st["max_users"] = b["max_users_override"]
    if b.get("suspended"):
        st.update(status="suspended", locked=True)
    return st


def parse_dt(v) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00")) if v else None
    except ValueError:
        return None
    return d.replace(tzinfo=timezone.utc) if d and d.tzinfo is None else d


def _status(b: dict) -> dict:
    now = datetime.now(timezone.utc)
    sub, trial = parse_dt(b.get("subscription_ends")), parse_dt(b.get("trial_ends"))
    if sub and sub > now:
        return {"status": "active", "ends_at": b["subscription_ends"], "days_left": _days_left(b["subscription_ends"]),
                "max_users": PLANS.get(b["plan"], {"max_users": TRIAL_USERS})["max_users"], "plan": b["plan"]}
    if trial and trial > now and not b.get("subscription_ends"):
        return {"status": "trial", "ends_at": b["trial_ends"], "days_left": _days_left(b["trial_ends"]), "max_users": TRIAL_USERS, "plan": "trial"}
    ends = b.get("subscription_ends") or b.get("trial_ends")
    ends_dt = parse_dt(ends)
    locked = bool(ends_dt) and (now - ends_dt).days >= GRACE_DAYS
    return {"status": "expired", "ends_at": ends, "days_left": 0, "max_users": TRIAL_USERS, "plan": b.get("plan", "trial"),
            "grace": not locked, "locked": locked}


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


async def create_business(name: str, owner_email: str, phone: str = "", state: str = "", gstin: str = "", industry_type: str = "wholesale",
                          industry_mode: str = "complete", demo: bool = False) -> dict:
    trial_ends = (datetime.now(timezone.utc) + timedelta(days=TRIAL_DAYS)).isoformat()
    ind, mode = industry_of({"industry_type": industry_type, "industry_mode": industry_mode})
    b = {"id": new_id(), "name": name.strip(), "owner_email": owner_email, "phone": phone, "plan": "trial", "industry_type": ind, "industry_mode": mode, "demo": demo,
         "trial_ends": trial_ends, "subscription_ends": None, "created_at": now_iso()}
    await db.businesses.insert_one(b)
    await seed_business(b["id"], {"name": name.strip(), "state": state, "gstin": gstin, "phone": phone, "email": owner_email})
    b.pop("_id", None)
    return b


async def extend_subscription(bid: str, plan: str, days: int = 365) -> dict:
    b = await get_business(bid)
    now = datetime.now(timezone.utc)
    start = max(now, parse_dt(b.get("subscription_ends")) or now)
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
