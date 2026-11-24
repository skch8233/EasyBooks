# Round 17: retest of iteration_25 fixes - sample-data endpoint, hospital non-IPD dates cleared, TDS base validation,
# POS exact MRP total posting (2-line split), demo rate limit spoof. Uses signups, demo test runs last.
import os
import uuid
from datetime import date

import pytest
import requests

API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
T = date.today().isoformat()


def signup(ind, mode="complete"):
    e = f"test_r17_{uuid.uuid4().hex[:8]}@ex.in"
    r = requests.post(f"{API}/auth/signup", json={"business_name": f"TEST_R17 {ind}", "name": "T", "email": e,
                                                  "password": "secret12", "industry_type": ind, "industry_mode": mode})
    assert r.status_code == 200, r.text
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return s


def cash(s):
    return [l["id"] for l in s.get(f"{API}/ledgers").json() if l["group"] == "cash"][0]


# ---- sample data per industry
@pytest.mark.parametrize("ind,path,n", [("college", "/college/students", 2), ("hospital", "/hospital/patients", 1),
                                        ("hospital", "/hospital/medicines", 2), ("retail", "/stock-items", 3)])
def test_sample_data(ind, path, n):
    s = signup(ind)
    r = s.post(f"{API}/industry/sample-data")
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "industry": ind}
    g = s.get(f"{API}{path}")
    assert g.status_code == 200, g.text
    d = g.json()
    assert len(d["items"] if isinstance(d, dict) else d) == n


def test_sample_data_twice_duplicates():
    s = signup("retail")
    s.post(f"{API}/industry/sample-data")
    r = s.post(f"{API}/industry/sample-data")
    items = s.get(f"{API}/stock-items").json()["items"]
    print("second call:", r.status_code, "items:", len(items))
    assert len(items) == 3, f"sample-data not idempotent: {len(items)} items after 2 calls"


def test_sample_data_requires_auth():
    assert requests.post(f"{API}/industry/sample-data").status_code in (401, 403)


# ---- hospital: non-IPD bill clears admission/discharge
def test_non_ipd_dates_cleared():
    s = signup("hospital")
    p = s.post(f"{API}/hospital/patients", json={"name": "TEST_Pat"}).json()
    r = s.post(f"{API}/hospital/bills", json={"patient_id": p["id"], "kind": "opd", "date": T, "ledger_id": cash(s), "admission_date": "2026-01-01",
                                               "discharge_date": "2026-01-03", "lines": [{"description": "Consult", "amount": 500}]})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["admission_date"] == "" and b["discharge_date"] == ""
    st = [x for x in s.get(f"{API}/hospital/bills").json() if x["id"] == b["id"]][0]
    assert st["admission_date"] == "" and st["discharge_date"] == ""
    r = s.post(f"{API}/hospital/bills", json={"patient_id": p["id"], "kind": "ipd", "date": T, "ledger_id": cash(s), "admission_date": "2026-01-01",
                                               "discharge_date": "2026-01-03", "lines": [{"description": "Bed", "amount": 500}]})
    assert r.json()["admission_date"] == "2026-01-01"


# ---- TDS base validation
def test_tds_base_rules():
    s = signup("services")
    led = s.get(f"{API}/ledgers").json()
    c = cash(s)
    party = s.post(f"{API}/ledgers", json={"name": f"TEST_Client {uuid.uuid4().hex[:4]}", "group": "sundry_debtors"})
    assert party.status_code in (200, 201), party.text
    pid = party.json()["id"]
    base = {"party_ledger_id": pid, "ledger_id": c, "date": T, "gross": 11800, "section": "194J"}
    assert s.post(f"{API}/tds/receipts", json={**base, "tds": 100, "tds_base": 12000}).status_code == 400
    assert s.post(f"{API}/tds/receipts", json={**base, "tds": 5000, "tds_base": 4000}).status_code == 400
    r = s.post(f"{API}/tds/receipts", json={**base, "tds": 1180, "tds_base": 0})
    assert r.status_code == 200, r.text
    assert r.json()["tds_base"] == 11800 and r.json()["net"] == 10620
    r = s.post(f"{API}/tds/receipts", json={**base, "tds": 1000, "tds_base": 10000})
    assert r.status_code == 200 and r.json()["tds_base"] == 10000


# ---- POS: posting lines as the frontend does gives an exact 377.00 voucher
def r2(x):
    return round(x + 1e-9, 2)


def exact_rate(q, mrp, g):
    want = r2(q * mrp)
    b = r2(want / (1 + g / 100))
    for d in (0, -1, 1, -2, 2):
        t = r2(b + d / 100)
        if r2(t + r2(t * g / 100)) == want:
            return round(t / q, 6)
    return None


def test_pos_exact_total():
    s = signup("retail")
    s.post(f"{API}/industry/sample-data")
    items = {i["name"]: i for i in s.get(f"{API}/stock-items").json()["items"]}
    led = s.get(f"{API}/ledgers").json()
    sales = [l["id"] for l in led if l["group"] == "sales"]
    if not sales:
        pytest.skip("no sales ledger")
    cart = [("Tata Salt 1kg", 1), ("Parle-G 250g", 7), ("Amul Butter 100g", 3)]
    lines = []
    for n, q in cart:
        it = items[n]
        r = exact_rate(q, it["mrp"], it["gst_rate"])
        if r is not None:
            lines.append({"item_id": it["id"], "description": n, "qty": q, "rate": r, "gst_rate": it["gst_rate"]})
        else:
            lines += [{"item_id": it["id"], "description": n, "qty": q - 1, "rate": exact_rate(q - 1, it["mrp"], it["gst_rate"]), "gst_rate": it["gst_rate"]},
                      {"item_id": it["id"], "description": n, "qty": 1, "rate": exact_rate(1, it["mrp"], it["gst_rate"]), "gst_rate": it["gst_rate"]}]
    r = s.post(f"{API}/vouchers", json={"voucher_type": "sales", "date": T, "party_ledger_id": cash(s), "account_ledger_id": sales[0],
                                         "gst_type": "intra", "items": lines, "narration": "TEST POS"})
    assert r.status_code in (200, 201), r.text
    print(lines, r.json().get("amount"))
    assert abs(r.json()["amount"] - 377.0) < 0.001
