from collections import defaultdict
from datetime import date, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException

from accounting import GROUP_MAP
from auth import ANY
from db import db, NO_ID
from routes_reports import _ledgers, _open, _pl, closing_signed
import stock as stock_mod

router = APIRouter(prefix="/api/reports")
r2 = lambda x: round(x or 0, 2)


def _prev(d: Optional[str]) -> Optional[str]:
    if not d:
        return None
    y = date.fromisoformat(d)
    return (y.replace(year=y.year - 1) if not (y.month == 2 and y.day == 29) else y.replace(year=y.year - 1, day=28)).isoformat()


@router.get("/project-summary")
async def project_summary(from_date: Optional[str] = None, to_date: Optional[str] = None, user=Depends(ANY)):
    bid = user["business_id"]
    ledgers = await _ledgers(bid)
    m = {"business_id": bid, "status": "active"}
    d = {k: v for k, v in (("$gte", from_date), ("$lte", to_date)) if v}
    if d:
        m["date"] = d
    agg = await db.vouchers.aggregate([{"$match": m}, {"$unwind": "$entries"},
                                       {"$group": {"_id": {"p": "$project_id", "l": "$entries.ledger_id"}, "dr": {"$sum": "$entries.debit"}, "cr": {"$sum": "$entries.credit"}}}]).to_list(None)
    per = defaultdict(lambda: defaultdict(float))
    for a in agg:
        g = ledgers.get(a["_id"]["l"], {}).get("group")
        n = GROUP_MAP.get(g, {}).get("nature")
        if n in ("income", "expense"):
            per[a["_id"].get("p")][g] += (a["cr"] - a["dr"]) if n == "income" else (a["dr"] - a["cr"])
    projects = {p["id"]: p for p in await db.erp_projects.find({"business_id": bid}, NO_ID).sort("code", 1).to_list(5000)}

    def row(code, name, t):
        rev, oth = t["sales"] + t["direct_income"], t["indirect_income"]
        cost = t["purchase"] + t["direct_expense"]
        return {"code": code, "project": name, "revenue": r2(rev), "other_income": r2(oth), "purchases": r2(t["purchase"]), "direct_expenses": r2(t["direct_expense"]),
                "gross_profit": r2(rev - cost), "indirect_expenses": r2(t["indirect_expense"]), "net_profit": r2(rev + oth - cost - t["indirect_expense"])}
    rows = [row(p["code"], p["name"], per[pid]) for pid, p in projects.items() if pid in per]
    if None in per:
        rows.append(row("-", "Not tagged to any project (head office / general)", per[None]))
    total = defaultdict(float)
    for t in per.values():
        for k, v in t.items():
            total[k] += v
    return {"rows": rows, "combined": row("ALL", "Combined (overall business)", total)}


HEADS = {
    "company": {
        "eq": [("Shareholders' funds", [("share_capital", "Share capital", ["capital"]), ("reserves", "Reserves and surplus", [])]),
               ("Non-current liabilities", [("lt_borrow", "Long-term borrowings", ["loans"])]),
               ("Current liabilities", [("trade_pay", "Trade payables", ["sundry_creditors"]), ("ocl", "Other current liabilities (incl. statutory dues)", ["current_liabilities", "duties_taxes"])])],
        "as": [("Non-current assets", [("ppe", "Property, plant and equipment", ["fixed_assets"])]),
               ("Current assets", [("inventories", "Inventories", []), ("trade_rec", "Trade receivables", ["sundry_debtors"]), ("cash", "Cash and cash equivalents", ["cash", "bank"]), ("oca", "Other current assets", ["current_assets"])])],
    },
    "other": {
        "eq": [("Sources of funds", [("capital", "Capital account", ["capital"]), ("loans", "Loan funds (secured / unsecured)", ["loans"])]),
               ("Current liabilities and provisions", [("trade_pay", "Sundry creditors", ["sundry_creditors"]), ("ocl", "Other current liabilities and provisions (incl. duties & taxes)", ["current_liabilities", "duties_taxes"])])],
        "as": [("Application of funds", [("ppe", "Fixed assets", ["fixed_assets"])]),
               ("Current assets, loans and advances", [("inventories", "Closing stock (inventories)", []), ("trade_rec", "Sundry debtors", ["sundry_debtors"]), ("cash", "Cash and bank balances", ["cash", "bank"]), ("oca", "Other current assets, loans and advances", ["current_assets"])])],
    },
}
PL = {
    "company": [("rev", "Revenue from operations", ["sales", "direct_income"], 1), ("oi", "Other income", ["indirect_income"], 1),
                ("pur", "Purchases of stock-in-trade", ["purchase"], -1), ("dex", "Operating and direct expenses", ["direct_expense"], -1),
                ("oex", "Other expenses", ["indirect_expense"], -1)],
    "other": [("rev", "Sales / revenue from operations", ["sales", "direct_income"], 1), ("pur", "Purchases", ["purchase"], -1),
              ("dex", "Direct expenses", ["direct_expense"], -1), ("oi", "Other income", ["indirect_income"], 1), ("oex", "Indirect / administrative expenses", ["indirect_expense"], -1)],
}
PURPOSE = {
    "company_audit": "Prepared for statutory audit under the Companies Act, 2013",
    "tax_audit": "Prepared for tax audit under section 44AB of the Income-tax Act, 1961",
    "other": "Prepared for management / bank / other purposes",
}


async def stock_value(bid, on_date):
    if not on_date:
        return 0.0
    items = await db.stock_items.find({"business_id": bid, "active": True}, NO_ID).to_list(5000)
    if not items:
        return 0.0
    moves = await stock_mod._moves(bid, to_date=on_date)
    return r2(sum(stock_mod._view(s, moves[s["id"]])["value"] for s in items))


async def _inception_stock(bid):
    items = await db.stock_items.find({"business_id": bid, "active": True}, {"opening_qty": 1, "opening_rate": 1}).to_list(5000)
    return r2(sum((i.get("opening_qty") or 0) * (i.get("opening_rate") or 0) for i in items))


async def _snapshot(bid, from_date, to_date, project_id):
    ledgers, bal = await closing_signed(bid, to_date, project_id)
    pl = await _pl(bid, from_date, to_date, project_id)
    if project_id:
        cs = os_ = 0.0
    else:
        cs = await stock_value(bid, to_date)
        os_ = await stock_value(bid, (date.fromisoformat(from_date) - timedelta(days=1)).isoformat()) if from_date else await _inception_stock(bid)
    pl = {**pl, "net_profit": r2(pl["net_profit"] + cs - os_), "closing_stock": cs, "opening_stock": os_}
    acc = -sum(b for lid, b in bal.items() if GROUP_MAP.get(ledgers[lid]["group"], {}).get("nature") in ("income", "expense")) + cs
    diff = sum(_open(l, project_id) for l in ledgers.values())
    return ledgers, bal, pl, r2(acc), r2(diff)


@router.get("/final-accounts")
async def final_accounts(to_date: str, from_date: Optional[str] = None, business_type: Optional[Literal["company", "llp", "partnership", "proprietorship"]] = None,
                         purpose: Literal["company_audit", "tax_audit", "other"] = "other", project_id: Optional[str] = None, user=Depends(ANY)):
    bid = user["business_id"]
    s = await db.settings.find_one({"business_id": bid}, NO_ID) or {}
    btype = business_type or s.get("business_type") or "proprietorship"
    kind = "company" if btype == "company" else "other"
    if purpose == "company_audit" and btype != "company":
        raise HTTPException(400, "Company audit purpose is only for companies. Choose income tax audit or other.")
    cur = await _snapshot(bid, from_date, to_date, project_id)
    has_prev = bool(await db.vouchers.find_one({"business_id": bid, "status": "active", "date": {"$lte": _prev(to_date)}}))
    prev = await _snapshot(bid, _prev(from_date), _prev(to_date), project_id) if has_prev else None
    notes, bs, nno = [], [], [2]

    def ledger_rows(snap, groups, sign):
        ledgers, bal = snap[0], snap[1]
        return {l["name"]: r2(sign * bal[lid]) for lid, l in ledgers.items() if l["group"] in groups and abs(bal[lid]) >= 0.005}

    def note(title, cy_rows, py_rows, extra=None):
        names = sorted(set(cy_rows) | set(py_rows))
        rows = [{"particulars": n, "cy": cy_rows.get(n, 0), "py": py_rows.get(n, 0)} for n in names] + (extra or [])
        no = nno[0]
        nno[0] += 1
        notes.append({"no": no, "title": title, "rows": rows, "cy": r2(sum(r["cy"] for r in rows)), "py": r2(sum(r["py"] for r in rows))})
        return no, notes[-1]["cy"], notes[-1]["py"]

    def surplus(snap):
        acc, yr, diff = snap[3], snap[2]["net_profit"], snap[4]
        return acc - yr, yr, diff

    def section(side, sign):
        out, tot_c, tot_p = [], 0.0, 0.0
        for head, items in HEADS[kind][side]:
            out.append({"type": "head", "label": head})
            for key, label, groups in items:
                c_rows = ledger_rows(cur, groups, sign)
                p_rows = ledger_rows(prev, groups, sign) if prev else {}
                extra = []
                if key == "inventories":
                    extra = [{"particulars": "Stock-in-trade (valued at weighted average cost)", "cy": cur[2]["closing_stock"], "py": prev[2]["closing_stock"] if prev else 0}]
                if key in ("reserves", "capital"):
                    co, cy, cd = surplus(cur)
                    po, py, pd = surplus(prev) if prev else (0, 0, 0)
                    lbl = "Surplus in Statement of Profit and Loss" if kind == "company" else "Net profit / (loss)"
                    extra = [{"particulars": f"{lbl} - opening balance", "cy": r2(co), "py": r2(po)},
                             {"particulars": "Add: profit / (loss) for the year", "cy": r2(cy), "py": r2(py)}]
                    if abs(cd) >= 0.005 or abs(pd) >= 0.005:
                        extra.append({"particulars": "Difference in opening balances (suspense)", "cy": r2(cd), "py": r2(pd)})
                if not c_rows and not p_rows and not any(abs(e["cy"]) + abs(e["py"]) >= 0.005 for e in extra):
                    out.append({"type": "item", "label": label, "note": None, "cy": 0, "py": 0})
                    continue
                no, cy_t, py_t = note(label, c_rows, p_rows, extra)
                out.append({"type": "item", "label": label, "note": no, "cy": cy_t, "py": py_t})
                tot_c += cy_t
                tot_p += py_t
        return out, r2(tot_c), r2(tot_p)

    eq, eq_c, eq_p = section("eq", -1)
    as_, as_c, as_p = section("as", 1)
    eq_title = "EQUITY AND LIABILITIES" if kind == "company" else "SOURCES OF FUNDS AND LIABILITIES"
    as_title = "ASSETS" if kind == "company" else "APPLICATION OF FUNDS (ASSETS)"
    bs = [{"type": "title", "label": f"I. {eq_title}"}, *eq, {"type": "total", "label": "TOTAL", "cy": eq_c, "py": eq_p},
          {"type": "title", "label": f"II. {as_title}"}, *as_, {"type": "total", "label": "TOTAL", "cy": as_c, "py": as_p}]

    def pl_amt(snap, groups):
        return r2(sum(snap[2]["totals"].get(g, 0) for g in groups)) if snap else 0

    def pl_note(label, groups, snap_c, snap_p):
        c = {r["ledger"]: r["amount"] for g in groups for r in snap_c[2]["sections"].get(g, [])}
        p = {r["ledger"]: r["amount"] for g in groups for r in (snap_p[2]["sections"].get(g, []) if snap_p else [])}
        return note(label, c, p) if c or p else (None, 0, 0)

    vals = {k: (pl_amt(cur, g), pl_amt(prev, g), pl_note(lbl, g, cur, prev)[0], lbl, sign) for k, lbl, g, sign in PL[kind]}
    item = lambda k: {"type": "item", "label": vals[k][3], "note": vals[k][2], "cy": vals[k][0], "py": vals[k][1]}
    tot = lambda keys, i: r2(sum(vals[k][i] for k in keys))
    st = lambda snap, k: snap[2][k] if snap else 0
    ch_c, ch_p = r2(st(cur, "opening_stock") - st(cur, "closing_stock")), r2(st(prev, "opening_stock") - st(prev, "closing_stock"))
    if kind == "company":
        ti_c, ti_p = tot(["rev", "oi"], 0), tot(["rev", "oi"], 1)
        te_c, te_p = r2(tot(["pur", "dex", "oex"], 0) + ch_c), r2(tot(["pur", "dex", "oex"], 1) + ch_p)
        pl = [{"type": "title", "label": "I. Revenue from operations"}, item("rev"), {"type": "title", "label": "II. Other income"}, item("oi"),
              {"type": "total", "label": "III. Total income (I + II)", "cy": ti_c, "py": ti_p}, {"type": "title", "label": "IV. Expenses"},
              item("pur"), {"type": "item", "label": "Changes in inventories of stock-in-trade (opening - closing)", "note": None, "cy": ch_c, "py": ch_p}, item("dex"), item("oex"),
              {"type": "total", "label": "Total expenses (IV)", "cy": te_c, "py": te_p},
              {"type": "total", "label": "V. Profit / (loss) before tax (III - IV)", "cy": r2(ti_c - te_c), "py": r2(ti_p - te_p)},
              {"type": "item", "label": "VI. Tax expense (current and deferred tax - to be provided)", "note": None, "cy": 0, "py": 0},
              {"type": "total", "label": "VII. Profit / (loss) for the period", "cy": r2(ti_c - te_c), "py": r2(ti_p - te_p)}]
    else:
        gp_c = r2(vals["rev"][0] - vals["pur"][0] - vals["dex"][0] - ch_c)
        gp_p = r2(vals["rev"][1] - vals["pur"][1] - vals["dex"][1] - ch_p)
        np_c, np_p = r2(gp_c + vals["oi"][0] - vals["oex"][0]), r2(gp_p + vals["oi"][1] - vals["oex"][1])
        pl = [item("rev"), {"type": "head", "label": "Less: Cost of sales"},
              {"type": "item", "label": "Opening stock", "note": None, "cy": st(cur, "opening_stock"), "py": st(prev, "opening_stock")}, item("pur"), item("dex"),
              {"type": "item", "label": "Less: Closing stock", "note": None, "cy": -st(cur, "closing_stock"), "py": -st(prev, "closing_stock")},
              {"type": "total", "label": "Gross profit", "cy": gp_c, "py": gp_p}, {"type": "head", "label": "Add:"}, item("oi"),
              {"type": "head", "label": "Less:"}, item("oex"), {"type": "total", "label": "Net profit / (loss) transferred to capital account", "cy": np_c, "py": np_p}]
    proj = await db.erp_projects.find_one({"id": project_id, "business_id": bid}, NO_ID) if project_id and project_id != "none" else None
    entity = {"company": "Company", "llp": "LLP", "partnership": "Firm", "proprietorship": "Proprietary concern"}[btype]
    basis = {"company_audit": "the Companies Act, 2013 (including Schedule III) and the Accounting Standards notified under section 133 of the Act",
             "tax_audit": "the Income-tax Act, 1961, the Income Computation and Disclosure Standards (ICDS) and the Accounting Standards issued by ICAI",
             "other": "generally accepted accounting principles in India"}[purpose]
    policies = [
        f"Basis of preparation: These financial statements of the {entity} are prepared under the historical cost convention on the accrual (mercantile) basis of accounting, in accordance with {basis}.",
        "Revenue recognition: Sales of goods are recognised when significant risks and rewards pass to the buyer; services are recognised as the service is rendered. Revenue is shown net of GST.",
        "Goods and Services Tax: Purchases and expenses are recorded net of eligible input tax credit. GST payable / receivable is shown under statutory dues.",
        "Inventories: Stock-in-trade is valued at weighted average cost (lower of cost and net realisable value) as per the stock register.",
        "Fixed assets: Fixed assets are stated at cost less accumulated depreciation, if any.",
        "Provisions and contingent liabilities: Provisions are recognised when there is a present obligation; contingent liabilities are disclosed in the notes.",
        "Previous year figures have been regrouped / rearranged wherever necessary. Figures are in Indian Rupees and rounded to the nearest paisa.",
    ]
    if purpose == "tax_audit":
        policies.append(f"PAN: {s.get('pan') or '__________'}; GSTIN: {s.get('gstin') or '__________'}. Method of accounting: mercantile, and the same has been followed consistently.")
    if kind == "company":
        policies.append("Income tax: Current tax and deferred tax are to be determined and provided in accordance with the Income-tax Act, 1961 and AS 22.")
    if proj:
        policies.append(f"Project accounts: these statements include only transactions tagged to project {proj['code']} - {proj['name']}; opening balances are not allocated to projects.")
    return {
        "business_type": btype, "kind": kind, "purpose": purpose, "purpose_text": PURPOSE[purpose], "company": s.get("company_name", ""), "address": s.get("address", ""),
        "pan": s.get("pan", ""), "gstin": s.get("gstin", ""), "cin": s.get("cin", ""), "from_date": from_date, "to_date": to_date,
        "prev_to_date": _prev(to_date) if prev else None, "project": {"code": proj["code"], "name": proj["name"]} if proj else None,
        "balance_sheet": bs, "profit_loss": pl, "policies": policies, "notes": notes,
        "balanced": abs(eq_c - as_c) < 0.01, "totals": {"liabilities": eq_c, "assets": as_c},
        "schedule": "Schedule III, Division I (Companies Act, 2013)" if kind == "company" else "Vertical format",
    }
