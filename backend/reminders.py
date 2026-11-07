import secrets
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from auth import ANY, WRITE
from db import db, NO_ID, new_id, now_iso, audit, clean
from routes_ledgers import opening_signed

router = APIRouter(prefix="/api")


def _due(d: str, days: int) -> str:
    return (date.fromisoformat(d) + timedelta(days=days)).isoformat()


async def outstanding_bills(bid: str, as_of: str, ledger_id: Optional[str] = None) -> list:
    s = await db.settings.find_one({"business_id": bid}, NO_ID) or {}
    default_days = s.get("default_credit_days", 30)
    q = {"business_id": bid, "group": "sundry_debtors", "active": True}
    if ledger_id:
        q["id"] = ledger_id
    ledgers = await db.ledgers.find(q, NO_ID).to_list(10000)
    ids = [l["id"] for l in ledgers]
    vs = await db.vouchers.find({"business_id": bid, "status": "active", "date": {"$lte": as_of}, "entries.ledger_id": {"$in": ids}},
                                {**NO_ID, "items": 0}).sort([("date", 1), ("created_at", 1)]).to_list(100000)
    reminders = {r["_id"]: r for r in await db.reminders.aggregate([
        {"$match": {"business_id": bid, "ledger_id": {"$in": ids}}}, {"$sort": {"created_at": -1}},
        {"$group": {"_id": "$ledger_id", "last": {"$first": "$created_at"}, "count": {"$sum": 1}}}]).to_list(None)}
    by_ledger = {i: [] for i in ids}
    for v in vs:
        for lid in {e["ledger_id"] for e in v["entries"]} & set(ids):
            dr = sum(e["debit"] for e in v["entries"] if e["ledger_id"] == lid)
            cr = sum(e["credit"] for e in v["entries"] if e["ledger_id"] == lid)
            by_ledger[lid].append((v, dr, cr))
    out = []
    for l in ledgers:
        days = l["credit_days"] if l.get("credit_days") is not None else default_days
        ob = opening_signed(l)
        bills, credit = ([{"voucher_id": None, "voucher_no": "Opening Balance", "date": None, "due_date": None, "amount": ob}] if ob > 0 else []), max(-ob, 0)
        for v, dr, cr in by_ledger[l["id"]]:
            if dr > cr:
                bills.append({"voucher_id": v["id"], "voucher_no": v["voucher_no"], "date": v["date"], "due_date": _due(v["date"], days), "amount": round(dr - cr, 2)})
            else:
                credit += cr - dr
        pending = []
        for b in bills:
            use = min(credit, b["amount"])
            credit -= use
            left = round(b["amount"] - use, 2)
            if left > 0.005:
                overdue_days = (date.fromisoformat(as_of) - date.fromisoformat(b["due_date"])).days if b["due_date"] else None
                pending.append({**b, "pending": left, "days_overdue": overdue_days if overdue_days is None or overdue_days > 0 else 0,
                                "overdue": b["due_date"] is None or b["due_date"] < as_of})
        if not pending:
            continue
        overdue = [b for b in pending if b["overdue"]]
        r = reminders.get(l["id"], {})
        out.append({"ledger_id": l["id"], "name": l["name"], "phone": l.get("phone", ""), "credit_days": days,
                    "outstanding": round(sum(b["pending"] for b in pending), 2), "overdue_amount": round(sum(b["pending"] for b in overdue), 2),
                    "max_days_overdue": max((b["days_overdue"] or 0 for b in overdue), default=0), "bills": pending,
                    "last_reminded_at": r.get("last"), "reminder_count": r.get("count", 0)})
    out.sort(key=lambda x: (-x["overdue_amount"], x["name"]))
    return out


@router.get("/reminders/overdue")
async def overdue(as_of: Optional[str] = None, user=Depends(ANY)):
    as_of = as_of or date.today().isoformat()
    rows = await outstanding_bills(user["business_id"], as_of)
    od = [r for r in rows if r["overdue_amount"] > 0]
    return {"as_of": as_of, "customers": rows, "overdue_customers": len(od), "total_overdue": round(sum(r["overdue_amount"] for r in od), 2),
            "total_outstanding": round(sum(r["outstanding"] for r in rows), 2)}


@router.post("/reminders/{ledger_id}/send")
async def send_reminder(ledger_id: str, user=Depends(WRITE)):
    bid = user["business_id"]
    rows = await outstanding_bills(bid, date.today().isoformat(), ledger_id)
    if not rows or rows[0]["overdue_amount"] <= 0:
        raise HTTPException(400, "This customer has no overdue bills")
    r = rows[0]
    token = secrets.token_urlsafe(16)
    await db.reminders.insert_one({"id": new_id(), "business_id": bid, "ledger_id": ledger_id, "token": token, "amount": r["overdue_amount"],
                                   "bills": [b["voucher_no"] for b in r["bills"] if b["overdue"]], "sent_by": user["email"], "created_at": now_iso()})
    await audit("reminder", ledger_id, "send", user, note=f"₹{r['overdue_amount']} overdue")
    s = await db.settings.find_one({"business_id": bid}, NO_ID) or {}
    return {"token": token, "phone": r["phone"], "customer": r["name"], "overdue_amount": r["overdue_amount"],
            "bills": [b for b in r["bills"] if b["overdue"]], "company_name": s.get("company_name", ""), "upi_id": s.get("upi_id", "")}


@router.get("/reminders/history")
async def history(user=Depends(ANY)):
    rows = await db.reminders.find({"business_id": user["business_id"]}, {**NO_ID, "token": 0}).sort("created_at", -1).to_list(200)
    return clean(rows)


@router.get("/public/pay/{token}")
async def public_pay(token: str):
    rem = await db.reminders.find_one({"token": token}, NO_ID)
    if not rem:
        raise HTTPException(404, "Payment link not found")
    bid = rem["business_id"]
    s = await db.settings.find_one({"business_id": bid}, NO_ID) or {}
    led = await db.ledgers.find_one({"id": rem["ledger_id"], "business_id": bid}, NO_ID) or {}
    rows = await outstanding_bills(bid, date.today().isoformat(), rem["ledger_id"])
    r = rows[0] if rows else {"outstanding": 0, "overdue_amount": 0, "bills": []}
    return {"company": {k: s.get(k, "") for k in ("company_name", "address", "phone", "gstin", "upi_id", "bank_name", "bank_account", "bank_ifsc")},
            "customer": led.get("name", ""), "outstanding": r["outstanding"], "overdue_amount": r["overdue_amount"],
            "bills": [{k: b[k] for k in ("voucher_no", "date", "due_date", "pending", "days_overdue", "overdue")} for b in r["bills"]],
            "reminder_amount": rem["amount"], "sent_at": rem["created_at"]}
