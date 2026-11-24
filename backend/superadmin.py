import re
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import SUPER, create_token
from business import GST_RATE, INDUSTRIES, MODE_LABEL, PLANS, extend_subscription, get_business, industry_of, parse_dt, status_of
from db import db, NO_ID, new_id, now_iso, audit, clean

router = APIRouter(prefix="/api/super")
PLAN_FIELDS = ("name", "price", "monthly_price", "max_users", "active", "modules")


async def load_plan_overrides():
    for p in await db.plan_settings.find({}, NO_ID).to_list(500):
        base = PLANS.get(p["key"], {"key": p["key"], "tier": "custom", "users_label": ""})
        PLANS[p["key"]] = {**base, **{k: v for k, v in p.items() if k != "_id"}}
        q = PLANS[p["key"]]
        tier = base.get("tier")
        q["users_label"] = f"3 to {q['max_users']} users" if tier == "multi" else f"Up to {q['max_users']} users" if tier == "custom" else base.get("users_label", "")
        q["gst"] = round(q["price"] * GST_RATE / 100, 2)
        q["total"] = round(q["price"] + q["gst"], 2)


class PlanIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    price: float = Field(gt=0, le=1000000)
    monthly_price: float = Field(0, ge=0, le=100000)
    max_users: int = Field(ge=1, le=500)
    active: bool = True
    modules: list = []


class NewPlanIn(PlanIn):
    key: str = Field(pattern=r"^[a-z0-9_]{3,40}$")
    industry: Literal["retail", "college", "hospital", "wholesale", "services"]
    mode: Literal["billing", "complete"] = "complete"


@router.get("/plans")
async def plans(user=Depends(SUPER)):
    return [p for p in PLANS.values() if p.get("industry")]


@router.put("/plans/{key}")
async def edit_plan(key: str, body: PlanIn, user=Depends(SUPER)):
    if key not in PLANS or not PLANS[key].get("industry"):
        raise HTTPException(404, "Plan not found")
    before = {k: PLANS[key].get(k) for k in PLAN_FIELDS}
    await db.plan_settings.update_one({"key": key}, {"$set": {"key": key, **body.model_dump(), "updated_at": now_iso()}}, upsert=True)
    await load_plan_overrides()
    await audit("plan", key, "edit", user, before=before, after=body.model_dump())
    return PLANS[key]


@router.post("/plans")
async def new_plan(body: NewPlanIn, user=Depends(SUPER)):
    if body.key in PLANS:
        raise HTTPException(400, "A plan with this key already exists")
    if body.mode not in INDUSTRIES[body.industry]["modes"]:
        raise HTTPException(400, f"{INDUSTRIES[body.industry]['label']} has no {MODE_LABEL[body.mode]} mode")
    doc = {**body.model_dump(), "tier": "custom", "created_at": now_iso()}
    await db.plan_settings.insert_one(doc)
    await load_plan_overrides()
    await audit("plan", body.key, "create", user, after=clean(doc))
    return PLANS[body.key]


# ---------- overview & organisations ----------
def _owner(users, b):
    o = next((u for u in users if u["email"] == b.get("owner_email")), users[0] if users else {})
    return {"owner_name": o.get("name", ""), "owner_email": b.get("owner_email", ""), "owner_phone": b.get("phone", "")}


async def _orgs():
    rows = await db.businesses.find({"demo": {"$ne": True}}, NO_ID).sort("created_at", -1).to_list(10000)
    users = {}
    for u in await db.users.find({"active": True}, {"_id": 0, "business_id": 1, "name": 1, "email": 1}).to_list(50000):
        users.setdefault(u["business_id"], []).append(u)
    out = []
    for b in rows:
        st = status_of(b)
        ind, mode = industry_of(b)
        p = PLANS.get(b.get("plan"), {})
        label = "Free Trial" if st["status"] == "trial" else (p.get("name") or ("Free Trial (expired)" if b.get("plan", "trial") == "trial" else b["plan"]))
        out.append({"id": b["id"], "name": b["name"], **_owner(users.get(b["id"], []), b), "industry_type": ind, "industry_mode": mode,
                    "industry_label": INDUSTRIES[ind]["label"], "plan": b.get("plan"), "plan_label": label, "status": st["status"],
                    "grace": st.get("grace", False), "locked": st.get("locked", False), "ends_at": st.get("ends_at"), "days_left": st.get("days_left", 0),
                    "max_users": st["max_users"], "users": len(users.get(b["id"], [])), "modules": b.get("modules") or {},
                    "max_users_override": b.get("max_users_override"), "created_at": b.get("created_at")})
    return out


@router.get("/overview")
async def overview(user=Depends(SUPER)):
    orgs = await _orgs()
    soon = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    paid = [o for o in orgs if o["status"] == "active"]
    year_ago = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
    month_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    hist = await _history()
    rev = lambda since: round(sum(h["amount"] for h in hist if (h["date"] or "") >= since), 2)
    return {"total_orgs": len(orgs), "active_paid": len(paid), "trials": sum(o["status"] == "trial" for o in orgs),
            "expiring_7d": sum(o["status"] in ("active", "trial") and bool(o["ends_at"]) and o["ends_at"] <= soon for o in orgs),
            "expired": sum(o["status"] == "expired" for o in orgs), "suspended": sum(o["status"] == "suspended" for o in orgs),
            "revenue_month": rev(month_ago), "revenue_year": rev(year_ago),
            "industries": [{"key": k, "label": v["label"], "active": sum(o["industry_type"] == k and o["status"] == "active" for o in orgs),
                            "trial": sum(o["industry_type"] == k and o["status"] == "trial" for o in orgs),
                            "total": sum(o["industry_type"] == k for o in orgs)} for k, v in INDUSTRIES.items()]}


@router.get("/orgs")
async def orgs(q: str = "", industry: str = "", status: str = "", user=Depends(SUPER)):
    rows = await _orgs()
    if q:
        rx = re.compile(re.escape(q), re.I)
        rows = [r for r in rows if rx.search(f"{r['name']} {r['owner_name']} {r['owner_email']} {r['owner_phone']}")]
    if industry:
        rows = [r for r in rows if r["industry_type"] == industry]
    if status:
        rows = [r for r in rows if (r["status"] == status or (status == "grace" and r["grace"]))]
    return rows


class ExtendIn(BaseModel):
    period: Literal["trial14", "month", "year", "days"]
    days: int = Field(0, ge=0, le=3650)
    plan: str = ""
    amount: float = Field(0, ge=0)
    reference: str = Field("", max_length=80)
    method: Literal["UPI", "NEFT", "Cheque", "Cash", "Card", "Other", "None"] = "UPI"
    note: str = Field("", max_length=200)
    lift_suspension: bool = False


async def _org(bid: str) -> dict:
    b = await get_business(bid)
    if not b or b.get("demo"):
        raise HTTPException(404, "Organization not found")
    return b


@router.post("/orgs/{bid}/extend")
async def extend(bid: str, body: ExtendIn, user=Depends(SUPER)):
    b = await _org(bid)
    if body.amount and not body.reference.strip() and body.method not in ("Cash", "None"):
        raise HTTPException(400, "Enter the transaction reference (UTR / cheque no) for this payment")
    if b.get("suspended") and not body.lift_suspension:
        raise HTTPException(400, "This organization is suspended. Tick 'Lift suspension' to extend and reactivate it, or reactivate it first")
    now = datetime.now(timezone.utc)
    if body.period == "trial14":
        sub_end = parse_dt(b.get("subscription_ends"))
        if sub_end and sub_end > now:
            raise HTTPException(400, "This organization has an active paid plan - extend the plan instead")
        field = "subscription_ends" if sub_end else "trial_ends"
        ends = (max(now, parse_dt(b.get(field)) or now) + timedelta(days=14)).isoformat()
        await db.businesses.update_one({"id": bid}, {"$set": {field: ends}})
        res, days = {field: ends}, 14
        plan = b.get("plan") if sub_end else "trial"
    else:
        ind, mode = industry_of(b)
        plan = body.plan or (b.get("plan") if b.get("plan") in PLANS and PLANS[b["plan"]].get("industry") else f"{ind}_{mode}")
        if plan not in PLANS or not PLANS[plan].get("industry"):
            raise HTTPException(400, "Choose one of the industry plans")
        days = {"month": 30, "year": 365}.get(body.period) or body.days
        if not 1 <= days <= 3650:
            raise HTTPException(400, "Days must be between 1 and 3650")
        res = await extend_subscription(bid, plan, days)
    plan_name = "Free trial extension" if plan == "trial" else PLANS.get(plan, {}).get("name", plan)
    entry = {"id": new_id(), "business_id": bid, "org": b["name"], "plan": plan, "plan_name": plan_name,
             "period": body.period, "days": days, "amount": body.amount, "method": body.method, "reference": body.reference.strip(), "note": body.note,
             "new_expiry": res.get("subscription_ends") or res.get("trial_ends"), "by": user["email"], "date": now_iso(), "source": "manual"}
    lifted = bool(b.get("suspended"))
    entry["suspension_lifted"] = lifted
    await db.subscription_ledger.insert_one(entry)
    if lifted:
        await db.businesses.update_one({"id": bid}, {"$unset": {"suspended": ""}})
        await audit("business", bid, "unsuspend", {**user, "business_id": bid}, note="Suspension lifted via Extend")
    await audit("subscription", bid, "manual_extend", {**user, "business_id": bid},
                note=f"{entry['plan_name']} +{days} days, ₹{body.amount} {body.method} {body.reference}" + ("; suspension lifted" if lifted else ""))
    return clean(entry)


class ConfigIn(BaseModel):
    industry_type: Literal["retail", "college", "hospital", "wholesale", "services"]
    industry_mode: Literal["billing", "complete"] = "complete"
    plan: Optional[str] = None
    max_users_override: Optional[int] = Field(None, ge=1, le=500)
    erp: Optional[bool] = None


@router.put("/orgs/{bid}/config")
async def config(bid: str, body: ConfigIn, user=Depends(SUPER)):
    b = await _org(bid)
    ind, mode = industry_of(body.model_dump())
    upd = {"industry_type": ind, "industry_mode": mode, "max_users_override": body.max_users_override}
    if body.plan:
        if body.plan not in PLANS or not PLANS[body.plan].get("industry"):
            raise HTTPException(400, "Unknown plan")
        upd["plan"] = body.plan
    mods = dict(b.get("modules") or {})
    if body.erp is None:
        mods.pop("erp", None)
    else:
        mods["erp"] = body.erp
    upd["modules"] = mods
    await db.businesses.update_one({"id": bid}, {"$set": upd})
    await audit("business", bid, "super_config", {**user, "business_id": bid}, before={k: b.get(k) for k in upd}, after=upd)
    return {"ok": True, **upd}


class SuspendIn(BaseModel):
    reason: str = Field("", max_length=200)


@router.post("/orgs/{bid}/suspend")
async def suspend(bid: str, body: SuspendIn, user=Depends(SUPER)):
    await _org(bid)
    await db.businesses.update_one({"id": bid}, {"$set": {"suspended": {"at": now_iso(), "by": user["email"], "reason": body.reason}}})
    await audit("business", bid, "suspend", {**user, "business_id": bid}, note=body.reason)
    return {"ok": True}


@router.post("/orgs/{bid}/reactivate")
async def reactivate(bid: str, user=Depends(SUPER)):
    await _org(bid)
    await db.businesses.update_one({"id": bid}, {"$unset": {"suspended": ""}})
    await audit("business", bid, "reactivate", {**user, "business_id": bid})
    return {"ok": True}


class SupportIn(BaseModel):
    reason: str = Field(min_length=3, max_length=200)


@router.post("/orgs/{bid}/support-view")
async def support_view(bid: str, body: SupportIn, user=Depends(SUPER)):
    b = await _org(bid)
    log = {"id": new_id(), "business_id": bid, "org": b["name"], "by": user["email"], "reason": body.reason, "at": now_iso()}
    await db.support_access_log.insert_one(log)
    await audit("support", bid, "support_view", {**user, "business_id": bid, "role": "viewer"}, note=body.reason)
    u = {**user, "home_business_id": user["business_id"], "home_role": user["role"], "business_id": bid, "role": "viewer", "support_view": True}
    return {"token": create_token(user, bid, support=True), "user": clean(u)}


@router.get("/support-log")
async def support_log(user=Depends(SUPER)):
    return clean(await db.support_access_log.find({}, NO_ID).sort("at", -1).to_list(1000))


async def _history():
    names = {b["id"]: b["name"] for b in await db.businesses.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(20000)}
    out = [{"date": p.get("paid_at") or p.get("created_at"), "org": names.get(p["business_id"], ""), "business_id": p["business_id"],
            "plan": PLANS.get(p.get("plan"), {}).get("name", p.get("plan")), "amount": p.get("amount", 0), "method": "Razorpay",
            "reference": p.get("payment_id", ""), "days": 365, "source": "online", "by": "customer"}
           for p in await db.payments.find({"status": "paid"}, NO_ID).to_list(20000)]
    out += [{"date": e["date"], "org": e["org"], "business_id": e["business_id"], "plan": e["plan_name"], "amount": e["amount"], "method": e["method"],
             "reference": e["reference"], "days": e["days"], "source": "manual", "by": e["by"], "new_expiry": e.get("new_expiry")}
            for e in await db.subscription_ledger.find({}, NO_ID).to_list(20000)]
    return sorted(out, key=lambda x: x["date"] or "", reverse=True)


@router.get("/payments")
async def payments(user=Depends(SUPER)):
    return await _history()
