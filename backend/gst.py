from collections import defaultdict

from fastapi import APIRouter, Depends, Query

from accounting import D
from auth import ANY
from db import db, NO_ID

router = APIRouter(prefix="/api/reports")
MONTH = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
HEADS = ("igst", "cgst", "sgst")


async def _month_data(bid: str, month: str, types):
    vs = await db.vouchers.find({"business_id": bid, "status": "active", "voucher_type": {"$in": types},
                                 "date": {"$gte": f"{month}-01", "$lte": f"{month}-31"}}, NO_ID).sort([("date", 1), ("seq", 1)]).to_list(50000)
    ids = list({v["party_ledger_id"] for v in vs})
    parties = {l["id"]: l for l in await db.ledgers.find({"business_id": bid, "id": {"$in": ids}}, NO_ID).to_list(10000)}
    s = await db.settings.find_one({"business_id": bid}, NO_ID) or {}
    return vs, parties, s


def _f(x) -> float:
    return float(D(x))


def _tot(rows, keys=("taxable",) + HEADS):
    return {k: _f(sum(r.get(k, 0) for r in rows)) for k in keys}


@router.get("/gstr1")
async def gstr1(month: str = MONTH, user=Depends(ANY)):
    vs, parties, s = await _month_data(user["business_id"], month, ["sales", "credit_note"])
    b2b, b2c, cdn = [], defaultdict(lambda: defaultdict(float)), []
    b2c_docs = set()
    hsn = defaultdict(lambda: defaultdict(float))
    for v in vs:
        p = parties.get(v["party_ledger_id"], {})
        gstin, pos = p.get("gstin", ""), p.get("state") or s.get("state", "")
        sign = -1 if v["voucher_type"] == "credit_note" else 1
        rates = defaultdict(lambda: defaultdict(float))
        for it in v.get("items", []):
            r = rates[it["gst_rate"]]
            r["taxable"] += it["amount"]
            for h in HEADS:
                r[h] += it.get(h, 0)
            hk = hsn[(it.get("hsn") or "-", it["gst_rate"])]
            hk["qty"] += sign * it["qty"]
            hk["taxable"] += sign * it["amount"]
            for h in HEADS:
                hk[h] += sign * it.get(h, 0)
        for rate, r in rates.items():
            row = {"gstin": gstin or "Unregistered", "party": v["party_name"], "voucher_no": v["voucher_no"], "date": v["date"],
                   "place_of_supply": pos, "rate": rate, "invoice_value": v["totals"].get("total", 0), **{k: _f(x) for k, x in r.items()}}
            if v["voucher_type"] == "credit_note":
                cdn.append({**row, "note_type": "Credit Note"})
            elif gstin:
                b2b.append(row)
            else:
                b2c_docs.add(v["id"])
                agg = b2c[(pos, rate)]
                for k in ("taxable",) + HEADS:
                    agg[k] += r[k]
    b2c_rows = [{"place_of_supply": pos, "rate": rate, **{k: _f(x) for k, x in a.items()}} for (pos, rate), a in sorted(b2c.items())]
    hsn_rows = [{"hsn": h, "rate": rate, "qty": round(a["qty"], 3), **{k: _f(a[k]) for k in ("taxable",) + HEADS},
                 "total": _f(a["taxable"] + sum(a[x] for x in HEADS))} for (h, rate), a in sorted(hsn.items())]
    out, cn = _tot(b2b + b2c_rows), _tot(cdn)
    return {"month": month, "gstin": s.get("gstin", ""), "b2b": b2b, "b2c": b2c_rows, "cdn": cdn, "hsn": hsn_rows,
            "summary": {"b2b": _tot(b2b), "b2c": _tot(b2c_rows), "cdn": cn,
                        "net": {k: _f(out[k] - cn[k]) for k in out}, "invoice_count": sum(1 for v in vs if v["voucher_type"] == "sales"),
                        "note_count": len({c["voucher_no"] for c in cdn}), "b2b_count": len({r["voucher_no"] for r in b2b}), "b2c_count": len(b2c_docs)}}


def _utilise(liab: dict, itc: dict):
    liab, itc = {k: D(v) for k, v in liab.items()}, {k: D(v) for k, v in itc.items()}
    paid_itc = {k: D(0) for k in HEADS}
    order = {"igst": ("igst", "cgst", "sgst"), "cgst": ("cgst", "igst"), "sgst": ("sgst", "igst")}
    for credit in ("igst", "cgst", "sgst"):
        for head in order[credit]:
            use = min(itc[credit], liab[head])
            itc[credit] -= use
            liab[head] -= use
            paid_itc[head] += use
    return {k: float(liab[k]) for k in HEADS}, {k: float(paid_itc[k]) for k in HEADS}, {k: float(itc[k]) for k in HEADS}


@router.get("/gstr3b")
async def gstr3b(month: str = MONTH, user=Depends(ANY)):
    vs, _, s = await _month_data(user["business_id"], month, ["sales", "credit_note", "purchase", "debit_note"])
    acc = {k: defaultdict(float) for k in ("taxable_out", "nil_out", "itc", "inward")}
    for v in vs:
        out = v["voucher_type"] in ("sales", "credit_note")
        sign = -1 if v["voucher_type"] in ("credit_note", "debit_note") else 1
        for it in v.get("items", []):
            tax = sum(it.get(h, 0) for h in HEADS)
            bucket = ("taxable_out" if tax > 0 else "nil_out") if out else "itc" if tax > 0 else "inward"
            acc[bucket]["taxable"] += sign * it["amount"]
            for h in HEADS:
                acc[bucket][h] += sign * it.get(h, 0)
    fmt = lambda a: {k: _f(a.get(k, 0)) for k in ("taxable",) + HEADS}
    o, i = fmt(acc["taxable_out"]), fmt(acc["itc"])
    payable, itc_used, carry = _utilise({h: max(o[h], 0) for h in HEADS}, {h: max(i[h], 0) for h in HEADS})
    return {"month": month, "gstin": s.get("gstin", ""),
            "outward_taxable": o, "outward_nil": fmt(acc["nil_out"]), "itc": i, "inward_nil": fmt(acc["inward"]),
            "itc_utilised": itc_used, "cash_payable": payable, "itc_carry_forward": carry,
            "total_cash_payable": _f(sum(payable.values()))}
