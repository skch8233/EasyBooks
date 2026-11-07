from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from accounting import GROUP_MAP, GROUPS
from auth import ANY
from db import db, NO_ID, clean
from routes_ledgers import opening_signed

router = APIRouter(prefix="/api/reports")


async def _ledgers(bid):
    return {l["id"]: l for l in await db.ledgers.find({"business_id": bid}, NO_ID).to_list(10000)}


async def _moves(bid, from_date=None, to_date=None, before=None) -> dict:
    match = {"business_id": bid, "status": "active"}
    d = {k: v for k, v in (("$gte", from_date), ("$lte", to_date), ("$lt", before)) if v}
    if d:
        match["date"] = d
    rows = await db.vouchers.aggregate([
        {"$match": match}, {"$unwind": "$entries"},
        {"$group": {"_id": "$entries.ledger_id", "dr": {"$sum": "$entries.debit"}, "cr": {"$sum": "$entries.credit"}}},
    ]).to_list(None)
    return {r["_id"]: (r["dr"], r["cr"]) for r in rows}


def _nature(led):
    return GROUP_MAP.get(led["group"], {}).get("nature", "asset")


async def closing_signed(bid, to_date: Optional[str]) -> tuple:
    ledgers = await _ledgers(bid)
    moves = await _moves(bid, to_date=to_date)
    bal = {lid: round(opening_signed(l) + moves.get(lid, (0, 0))[0] - moves.get(lid, (0, 0))[1], 2) for lid, l in ledgers.items()}
    return ledgers, bal


@router.get("/trial-balance")
async def trial_balance(to_date: Optional[str] = None, user=Depends(ANY)):
    ledgers, bal = await closing_signed(user["business_id"], to_date)
    rows, tdr, tcr = [], 0.0, 0.0
    for g in GROUPS:
        for l in sorted([l for l in ledgers.values() if l["group"] == g["key"]], key=lambda x: x["name"]):
            b = bal[l["id"]]
            if abs(b) < 0.005:
                continue
            rows.append({"ledger_id": l["id"], "ledger": l["name"], "group": g["name"],
                         "debit": b if b > 0 else 0, "credit": -b if b < 0 else 0})
            tdr += max(b, 0)
            tcr += max(-b, 0)
    diff = round(sum(opening_signed(l) for l in ledgers.values()), 2)
    if abs(diff) >= 0.005:
        rows.append({"ledger_id": None, "ledger": "Difference in Opening Balances", "group": "",
                     "debit": -diff if diff < 0 else 0, "credit": diff if diff > 0 else 0})
        tdr += max(-diff, 0)
        tcr += max(diff, 0)
    return {"rows": rows, "total_debit": round(tdr, 2), "total_credit": round(tcr, 2),
            "balanced": abs(tdr - tcr) < 0.01, "opening_difference": diff}


async def _pl(bid, from_date, to_date):
    ledgers = await _ledgers(bid)
    moves = await _moves(bid, from_date=from_date, to_date=to_date)
    sec = defaultdict(list)
    for lid, l in ledgers.items():
        g = GROUP_MAP.get(l["group"], {})
        if g.get("nature") not in ("income", "expense"):
            continue
        dr, cr = moves.get(lid, (0, 0))
        amt = round(cr - dr if g["nature"] == "income" else dr - cr, 2)
        if abs(amt) >= 0.005:
            sec[l["group"]].append({"ledger_id": lid, "ledger": l["name"], "amount": amt})
    tot = {k: round(sum(r["amount"] for r in v), 2) for k, v in sec.items()}
    t = lambda k: tot.get(k, 0)
    gross = round(t("sales") + t("direct_income") - t("purchase") - t("direct_expense"), 2)
    net = round(gross + t("indirect_income") - t("indirect_expense"), 2)
    return {"sections": {k: sorted(v, key=lambda r: r["ledger"]) for k, v in sec.items()}, "totals": tot,
            "gross_profit": gross, "net_profit": net}


@router.get("/profit-loss")
async def profit_loss(from_date: Optional[str] = None, to_date: Optional[str] = None, user=Depends(ANY)):
    return await _pl(user["business_id"], from_date, to_date)


@router.get("/balance-sheet")
async def balance_sheet(to_date: Optional[str] = None, user=Depends(ANY)):
    ledgers, bal = await closing_signed(user["business_id"], to_date)
    assets, liabs, profit = defaultdict(list), defaultdict(list), 0.0
    for lid, l in ledgers.items():
        n, b = _nature(l), bal[lid]
        if n in ("income", "expense"):
            profit -= b
            continue
        if abs(b) < 0.005:
            continue
        g = GROUP_MAP[l["group"]]["name"]
        if n == "asset":
            assets[g].append({"ledger": l["name"], "amount": b})
        else:
            liabs[g].append({"ledger": l["name"], "amount": -b})
    diff = round(sum(opening_signed(l) for l in ledgers.values()), 2)
    pack = lambda d: [{"group": g, "rows": sorted(r, key=lambda x: x["ledger"]), "total": round(sum(x["amount"] for x in r), 2)} for g, r in d.items()]
    a, li = pack(assets), pack(liabs)
    ta = round(sum(x["total"] for x in a), 2)
    tl = round(sum(x["total"] for x in li) + profit + diff, 2)
    return {"assets": a, "liabilities": li, "profit_loss": round(profit, 2), "opening_difference": diff,
            "total_assets": ta, "total_liabilities": tl, "balanced": abs(ta - tl) < 0.01}


@router.get("/ledger-statement")
async def ledger_statement(ledger_id: str, from_date: Optional[str] = None, to_date: Optional[str] = None, user=Depends(ANY)):
    led = await db.ledgers.find_one({"id": ledger_id, "business_id": user["business_id"]}, NO_ID)
    if not led:
        raise HTTPException(404, "Ledger not found")
    opening = opening_signed(led)
    if from_date:
        dr, cr = (await _moves(user["business_id"], before=from_date)).get(ledger_id, (0, 0))
        opening += dr - cr
    q = {"business_id": user["business_id"], "status": "active", "entries.ledger_id": ledger_id}
    d = {k: v for k, v in (("$gte", from_date), ("$lte", to_date)) if v}
    if d:
        q["date"] = d
    vouchers = await db.vouchers.find(q, NO_ID).sort([("date", 1), ("created_at", 1)]).to_list(20000)
    rows, run, tdr, tcr = [], round(opening, 2), 0.0, 0.0
    for v in vouchers:
        mine = [e for e in v["entries"] if e["ledger_id"] == ledger_id]
        dr, cr = sum(e["debit"] for e in mine), sum(e["credit"] for e in mine)
        others = [e["ledger_name"] for e in v["entries"] if e["ledger_id"] != ledger_id and ((e["credit"] > 0) if dr > cr else (e["debit"] > 0))]
        run = round(run + dr - cr, 2)
        tdr += dr
        tcr += cr
        rows.append({"voucher_id": v["id"], "date": v["date"], "voucher_no": v["voucher_no"], "voucher_type": v["voucher_type"],
                     "particulars": others[0] if len(others) == 1 else ("Multiple: " + ", ".join(others[:3]) if others else "-"),
                     "narration": v.get("narration", ""), "debit": round(dr, 2), "credit": round(cr, 2), "balance": run})
    led["group_name"] = GROUP_MAP.get(led["group"], {}).get("name")
    return {"ledger": clean(led), "opening": round(opening, 2), "rows": rows, "total_debit": round(tdr, 2),
            "total_credit": round(tcr, 2), "closing": run}


@router.get("/outstanding")
async def outstanding(kind: str = "receivables", to_date: Optional[str] = None, user=Depends(ANY)):
    group = "sundry_debtors" if kind == "receivables" else "sundry_creditors"
    ledgers, bal = await closing_signed(user["business_id"], to_date)
    rows = []
    for lid, l in ledgers.items():
        if l["group"] != group or abs(bal[lid]) < 0.005:
            continue
        amt = bal[lid] if group == "sundry_debtors" else -bal[lid]
        rows.append({"ledger_id": lid, "ledger": l["name"], "gstin": l.get("gstin", ""), "phone": l.get("phone", ""), "amount": round(amt, 2)})
    rows.sort(key=lambda r: -r["amount"])
    return {"rows": rows, "total": round(sum(r["amount"] for r in rows), 2)}


@router.get("/register")
async def register(voucher_type: str = "sales", from_date: Optional[str] = None, to_date: Optional[str] = None, user=Depends(ANY)):
    q = {"business_id": user["business_id"], "status": "active", "voucher_type": voucher_type}
    d = {k: v for k, v in (("$gte", from_date), ("$lte", to_date)) if v}
    if d:
        q["date"] = d
    vs = await db.vouchers.find(q, NO_ID).sort([("date", 1), ("seq", 1)]).to_list(20000)
    party_ids = list({v["party_ledger_id"] for v in vs})
    gst = {l["id"]: l.get("gstin", "") for l in await db.ledgers.find({"business_id": user["business_id"], "id": {"$in": party_ids}}, NO_ID).to_list(10000)}
    rows = []
    for v in vs:
        t = v.get("totals") or {}
        rows.append({"voucher_id": v["id"], "date": v["date"], "voucher_no": v["voucher_no"], "party": v["party_name"],
                     "gstin": gst.get(v["party_ledger_id"], ""), "taxable": t.get("taxable", v["amount"]),
                     "cgst": t.get("cgst", 0), "sgst": t.get("sgst", 0), "igst": t.get("igst", 0), "total": t.get("total", v["amount"])})
    totals = {k: round(sum(r[k] for r in rows), 2) for k in ("taxable", "cgst", "sgst", "igst", "total")}
    return {"rows": rows, "totals": totals}


@router.get("/dashboard")
async def dashboard(from_date: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$"), to_date: str = Query(pattern=r"^\d{4}-\d{2}-\d{2}$"), user=Depends(ANY)):
    ledgers, bal = await closing_signed(user["business_id"], to_date)
    sumg = lambda g: round(sum(bal[i] for i, l in ledgers.items() if l["group"] == g), 2)
    pl = await _pl(user["business_id"], from_date, to_date)
    t = pl["totals"]
    vs = await db.vouchers.find({"business_id": user["business_id"], "status": "active", "date": {"$gte": from_date, "$lte": to_date}}, NO_ID).to_list(50000)
    months = defaultdict(lambda: {"income": 0.0, "expense": 0.0})
    for v in vs:
        m = v["date"][:7]
        for e in v["entries"]:
            n = _nature(ledgers.get(e["ledger_id"], {"group": "x"}))
            if n == "income":
                months[m]["income"] += e["credit"] - e["debit"]
            elif n == "expense":
                months[m]["expense"] += e["debit"] - e["credit"]
    y, mo = int(from_date[:4]), int(from_date[5:7])
    monthly = []
    while f"{y:04d}-{mo:02d}" <= to_date[:7] and len(monthly) < 24:
        k = f"{y:04d}-{mo:02d}"
        monthly.append({"month": k, "income": round(months[k]["income"], 2), "expense": round(months[k]["expense"], 2)})
        mo += 1
        if mo > 12:
            y, mo = y + 1, 1
    recent = await db.vouchers.find({"business_id": user["business_id"], "status": "active"}, {**NO_ID, "items": 0}).sort([("date", -1), ("created_at", -1)]).to_list(8)
    return {"total_sales": t.get("sales", 0), "total_purchases": t.get("purchase", 0),
            "cash_balance": sumg("cash"), "bank_balance": sumg("bank"),
            "receivables": sumg("sundry_debtors"), "payables": round(-sumg("sundry_creditors"), 2),
            "net_profit": pl["net_profit"], "voucher_count": len(vs), "monthly": monthly, "recent": clean(recent)}
