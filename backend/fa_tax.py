from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from accounting import VoucherIn, Entry
from auth import ANY, WRITE
from db import db, NO_ID, new_id, now_iso
from routes_ledgers import opening_signed
from routes_vouchers import create_voucher, cancel_voucher, CancelIn

router = APIRouter(prefix="/api")
rupee = lambda x: int(Decimal(str(x)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
r2 = lambda x: round(x or 0, 2)
SYS = {"depreciation": ("Depreciation", "indirect_expense"), "income_tax": ("Income Tax Expense", "indirect_expense"),
       "tax_provision": ("Provision for Income Tax", "current_liabilities")}
TAX_PRESETS = {
    "company": [("Domestic company u/s 115BAA (22% + 10% surcharge + 4% cess)", 25.168), ("Domestic company, turnover up to Rs 400 crore (25% + 4% cess)", 26.0),
                ("Domestic company, other (30% + 4% cess)", 31.2)],
    "llp": [("LLP (30% + 4% cess)", 31.2), ("LLP with income above Rs 1 crore (30% + 12% surcharge + 4% cess)", 34.944)],
    "partnership": [("Partnership firm (30% + 4% cess)", 31.2), ("Firm with income above Rs 1 crore (30% + 12% surcharge + 4% cess)", 34.944)],
    "proprietorship": [("Proprietor - enter your effective slab rate", 0.0)],
}


async def ensure_ledger(bid: str, key: str) -> dict:
    name, group = SYS[key]
    ok = {"indirect_expense", "direct_expense"} if group.endswith("expense") else {"current_liabilities", "duties_taxes"}
    led = await db.ledgers.find_one({"business_id": bid, "system_key": key}, NO_ID)
    if led and led["group"] in ok:
        return led
    if led:
        await db.ledgers.update_one({"id": led["id"]}, {"$unset": {"system_key": ""}})
    for n in range(0, 20):
        nm = name if n == 0 else f"{name} (auto)" if n == 1 else f"{name} (auto {n})"
        same = await db.ledgers.find_one({"business_id": bid, "name_lower": nm.lower()}, NO_ID)
        if not same:
            name = nm
            break
        if same["group"] in ok:
            await db.ledgers.update_one({"id": same["id"]}, {"$set": {"system_key": key}})
            return {**same, "system_key": key}
    led = {"id": new_id(), "business_id": bid, "name": name, "name_lower": name.lower(), "group": group, "opening_balance": 0, "opening_type": "Dr",
           "system_key": key, "gstin": "", "state": "", "phone": "", "email": "", "address": "", "active": True, "created_at": now_iso()}
    await db.ledgers.insert_one({**led})
    return {k: v for k, v in led.items() if k != "_id"}


def _is_dep(v) -> bool:
    return str(v.get("system_tag") or "").startswith("depreciation:")


def _period_from(v) -> str:
    if v.get("period_from"):
        return v["period_from"]
    d = date.fromisoformat(v["date"])
    return (d.replace(year=d.year - 1) + timedelta(days=1)).isoformat() if not (d.month == 2 and d.day == 29) else d.replace(year=d.year - 1, day=28).isoformat()


async def _tagged_in(bid: str, prefix: str, from_date: str, to_date: str):
    vs = await db.vouchers.find({"business_id": bid, "status": "active", "system_tag": {"$regex": f"^{prefix}:"}, "date": {"$gte": from_date}}, NO_ID).sort("date", 1).to_list(200)
    return [v for v in vs if _period_from(v) <= to_date]


def _check_period(from_date: str, to_date: str):
    try:
        a, b = date.fromisoformat(from_date), date.fromisoformat(to_date)
    except ValueError:
        raise HTTPException(400, "Dates must be in YYYY-MM-DD format")
    if a > b:
        raise HTTPException(400, "Start date must be on or before the end date")
    if (b - a).days > 366:
        raise HTTPException(400, "Period cannot be longer than one year")
    return a, b


async def dep_schedule(bid: str, from_date: str, to_date: str) -> dict:
    start, end = _check_period(from_date, to_date)
    assets = await db.ledgers.find({"business_id": bid, "group": "fixed_assets"}, NO_ID).sort("name_lower", 1).to_list(2000)
    posted = await _tagged_in(bid, "depreciation", from_date, to_date)
    vs = await db.vouchers.find({"business_id": bid, "status": "active", "date": {"$lte": to_date}, "entries.ledger_id": {"$in": [a["id"] for a in assets]}},
                                {"_id": 0, "date": 1, "entries": 1, "system_tag": 1}).sort("date", 1).to_list(None)
    span = (end - start).days + 1
    full = span >= 365
    held = lambda d: (end - date.fromisoformat(d)).days + 1
    rows = []
    for a in assets:
        wdv = opening_signed(a)
        cost = float(a.get("dep_cost") or 0) or max(wdv, 0)
        adds, dels = [], []
        for v in vs:
            dep_v = _is_dep(v)
            for e in v["entries"]:
                if e["ledger_id"] != a["id"]:
                    continue
                if v["date"] < from_date:
                    if dep_v:
                        wdv -= e["credit"] - e["debit"]
                    elif e["debit"]:
                        wdv += e["debit"]
                        cost += e["debit"]
                    else:
                        cost -= cost * min(e["credit"] / wdv, 1) if wdv > 0 else 0
                        wdv -= e["credit"]
                elif not dep_v:
                    (adds if e["debit"] else dels).append((v["date"], e["debit"] or e["credit"]))
        opening, cost_start = wdv, max(cost, 0)
        method, rate = a.get("dep_method") or "none", float(a.get("dep_rate") or 0)
        add_tot, del_tot = sum(x for _, x in adds), sum(x for _, x in dels)
        avail = max(opening + add_tot - del_tot, 0)
        frac = 1 if full else span / 365
        dep, half = 0.0, 0.0
        if method == "wdv" and rate > 0:
            for d, x in adds:
                f = (0.5 if held(d) < 180 else 1) if full else held(d) / 365
                half += x if full and f < 1 else 0
                dep += x * rate / 100 * f
            dep += max(opening - del_tot, 0) * rate / 100 * frac
        elif method == "slm" and rate > 0:
            run_wdv, run_cost, dep = opening, cost_start, 0.0
            sold_cost = 0.0
            for d, x in sorted(adds + [(d, -x) for d, x in dels]):
                if x > 0:
                    run_wdv += x
                    run_cost += x
                    dep += x * rate / 100 * held(d) / (span if full else 365)
                else:
                    part = run_cost * min(-x / run_wdv, 1) if run_wdv > 0 else 0
                    sold_cost += part
                    run_cost -= part
                    run_wdv += x
                    dep += min(part, cost_start) * rate / 100 * max(span - held(d), 0) / (span if full else 365)
            dep += max(cost_start - sold_cost, 0) * rate / 100 * frac if cost_start else 0
            dep = min(dep, max(avail - 0.05 * max(run_cost, 0), 0))
        dep = r2(min(dep, avail))
        rows.append({"ledger_id": a["id"], "asset": a["name"], "method": method, "rate": rate, "opening": r2(opening), "cost": r2(cost_start), "additions": r2(add_tot),
                     "additions_half_rate": r2(half), "deletions": r2(del_tot), "depreciation": dep, "closing": r2(avail - dep)})
    return {"from_date": from_date, "to_date": to_date, "rows": rows, "total": r2(sum(r["depreciation"] for r in rows)),
            "posted": {"id": posted[-1]["id"], "voucher_no": ", ".join(p["voucher_no"] for p in posted), "amount": r2(sum(p["amount"] for p in posted))} if posted else None}


class PeriodIn(BaseModel):
    from_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    to_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


class TaxIn(PeriodIn):
    rate: float = Field(ge=0, le=60)
    add_back: float = Field(0, ge=0)
    deductions: float = Field(0, ge=0)
    amount: Optional[float] = Field(None, ge=0)


async def _post(bid, tag, from_date, date_, entries, narration, user):
    for old in await _tagged_in(bid, tag.split(":")[0], from_date, date_):
        await cancel_voucher(old["id"], CancelIn(reason="Replaced by recalculated year-end entry"), user)
    v = await create_voucher(VoucherIn(voucher_type="journal", date=date_, narration=narration, reference_no=tag.split(":")[0].replace("_", " ").title(),
                                       entries=[Entry(**e) for e in entries]), user)
    await db.vouchers.update_one({"id": v["id"]}, {"$set": {"system_tag": tag, "period_from": from_date}})
    return v


@router.get("/depreciation")
async def get_dep(from_date: str, to_date: str, user=Depends(ANY)):
    return await dep_schedule(user["business_id"], from_date, to_date)


@router.post("/depreciation/post")
async def post_dep(b: PeriodIn, user=Depends(WRITE)):
    bid = user["business_id"]
    sch = await dep_schedule(bid, b.from_date, b.to_date)
    rows = [r for r in sch["rows"] if r["depreciation"] > 0]
    if not rows:
        raise HTTPException(400, "No depreciation to post. Set a method and rate on your fixed asset ledgers first.")
    led = await ensure_ledger(bid, "depreciation")
    entries = [{"ledger_id": led["id"], "debit": sch["total"], "credit": 0}] + [{"ledger_id": r["ledger_id"], "debit": 0, "credit": r["depreciation"]} for r in rows]
    v = await _post(bid, f"depreciation:{b.to_date}", b.from_date, b.to_date, entries, f"Depreciation for the period {b.from_date} to {b.to_date}", user)
    return {"voucher_no": v["voucher_no"], "amount": sch["total"]}


async def tax_basis(bid: str, from_date: str, to_date: str) -> dict:
    from final_accounts import stock_value
    from routes_reports import _pl
    from datetime import timedelta
    pl = await _pl(bid, from_date, to_date)
    tax_led = await db.ledgers.find_one({"business_id": bid, "system_key": "income_tax"}, NO_ID)
    tax_in_pl = sum(r["amount"] for g in ("indirect_expense", "direct_expense") for r in pl["sections"].get(g, []) if tax_led and r["ledger_id"] == tax_led["id"])
    stock = await stock_value(bid, to_date) - await stock_value(bid, (date.fromisoformat(from_date) - timedelta(days=1)).isoformat())
    return {"pbt": r2(pl["net_profit"] + tax_in_pl + stock), "stock_adjustment": r2(stock)}


@router.get("/tax-provision")
async def get_tax(from_date: str, to_date: str, rate: float = Query(0, ge=0, le=60), add_back: float = Query(0, ge=0), deductions: float = Query(0, ge=0), user=Depends(ANY)):
    bid = user["business_id"]
    _check_period(from_date, to_date)
    s = await db.settings.find_one({"business_id": bid}, NO_ID) or {}
    btype = s.get("business_type") or "proprietorship"
    base = await tax_basis(bid, from_date, to_date)
    taxable = max(base["pbt"] + add_back - deductions, 0)
    posted = (await _tagged_in(bid, "income_tax", from_date, to_date) or [None])[-1]
    dep = await _tagged_in(bid, "depreciation", from_date, to_date)
    has_assets = await db.ledgers.find_one({"business_id": bid, "group": "fixed_assets", "dep_method": {"$in": ["wdv", "slm"]}})
    return {**base, "business_type": btype, "presets": [{"label": l, "rate": r} for l, r in TAX_PRESETS[btype]], "add_back": add_back, "deductions": deductions,
            "taxable": r2(taxable), "rate": rate, "tax": rupee(taxable * rate / 100), "depreciation_posted": bool(dep) or not has_assets,
            "posted": {"id": posted["id"], "voucher_no": posted["voucher_no"], "amount": posted["amount"]} if posted else None}


@router.post("/tax-provision/post")
async def post_tax(b: TaxIn, user=Depends(WRITE)):
    bid = user["business_id"]
    _check_period(b.from_date, b.to_date)
    base = await tax_basis(bid, b.from_date, b.to_date)
    tax = rupee(b.amount) if b.amount is not None else rupee(max(base["pbt"] + b.add_back - b.deductions, 0) * b.rate / 100)
    if tax <= 0:
        raise HTTPException(400, "Tax works out to zero. Check the profit, rate and adjustments.")
    exp, prov = await ensure_ledger(bid, "income_tax"), await ensure_ledger(bid, "tax_provision")
    v = await _post(bid, f"income_tax:{b.to_date}", b.from_date, b.to_date, [{"ledger_id": exp["id"], "debit": tax, "credit": 0}, {"ledger_id": prov["id"], "debit": 0, "credit": tax}],
                    f"Provision for income tax for the period {b.from_date} to {b.to_date} @ {b.rate}%", user)
    return {"voucher_no": v["voucher_no"], "amount": tax}
