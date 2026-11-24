# Round 14 Part 1 - industry SaaS extra regression tests (iteration 24)
import os
import uuid
from datetime import date, timedelta

import requests

API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
T = date.today().isoformat()


def sess(industry, mode="complete"):
    e = f"test_ind_{uuid.uuid4().hex[:10]}@ex.in"
    r = requests.post(f"{API}/auth/signup", json={"industry_type": industry, "industry_mode": mode, "business_name": f"TEST {industry}", "name": "T",
                                                  "email": e, "password": "secret12", "state": "27-Maharashtra"})
    assert r.status_code == 200, r.text
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    if industry in ("retail", "college", "hospital"):
        assert s.post(f"{API}/industry/sample-data").status_code == 200
    return s


def cash(s):
    return [l["id"] for l in s.get(f"{API}/ledgers").json() if l["group"] == "cash"][0]


def ledger(s, key):
    return [l["id"] for l in s.get(f"{API}/ledgers").json() if l.get("system_key") == key][0]


# Public industries + pricing
def test_public_industries_prices():
    d = requests.get(f"{API}/public/industries").json()["industries"]
    exp = {"retail": {5000, 8500}, "college": {15000, 18500}, "hospital": {15000, 18500}, "wholesale": {2500, 5000, 6000, 8500}, "services": {2500, 5000, 6000, 8500}}
    for k, prices in exp.items():
        got = {p["price"] for p in d[k]["plans"]}
        assert got == prices, (k, got)
        for p in d[k]["plans"]:
            assert p["gst"] == round(p["price"] * 0.18, 2)


# Demo invalid industry rejected
def test_demo_invalid_industry():
    assert requests.post(f"{API}/public/demo", json={"industry_type": "bank"}).status_code == 422


# Retail demo seed (barcode / reorder)
def test_retail_demo_seed():
    s = sess("retail")
    items = s.get(f"{API}/stock-items").json()
    items = items.get("items", items) if isinstance(items, dict) else items
    names = {i["name"]: i for i in items}
    assert names["Tata Salt 1kg"]["barcode"] == "8901058000017"
    assert names["Parle-G 250g"]["reorder_level"] == 5


# Hospital: expired batch blocked, stock decrement, oversell
def test_hospital_pharmacy_rules():
    s = sess("hospital")
    p = s.get(f"{API}/hospital/patients").json()[0]
    assert p["reg_no"] == "UHID/0001"
    meds = s.get(f"{API}/hospital/medicines").json()
    amx = [m for m in meds if m["name"].startswith("Amoxicillin")][0]
    assert amx["expiring"] and not amx["expired"]
    exp = s.post(f"{API}/hospital/medicines", json={"name": "TEST_Old", "batch": "X1", "expiry": (date.today() - timedelta(days=3)).isoformat(), "qty": 10, "mrp": 5}).json()
    assert exp["expired"]
    c = cash(s)
    r = s.post(f"{API}/hospital/bills", json={"patient_id": p["id"], "kind": "pharmacy", "date": T, "ledger_id": c, "lines": [{"medicine_id": exp["id"], "qty": 1}]})
    assert r.status_code == 400 and "expired" in r.text
    r = s.post(f"{API}/hospital/bills", json={"patient_id": p["id"], "kind": "pharmacy", "date": T, "ledger_id": c, "lines": [{"medicine_id": amx["id"], "qty": 61}]})
    assert r.status_code == 400
    r = s.post(f"{API}/hospital/bills", json={"patient_id": p["id"], "kind": "pharmacy", "date": T, "ledger_id": c, "lines": [{"medicine_id": amx["id"], "qty": 5}]})
    assert r.status_code == 200 and r.json()["total"] == 45 and r.json()["bill_no"] == "PH/0001"
    amx2 = [m for m in s.get(f"{API}/hospital/medicines").json() if m["id"] == amx["id"]][0]
    assert amx2["qty"] == 55
    r = s.post(f"{API}/hospital/bills", json={"patient_id": p["id"], "kind": "ipd", "date": T, "admission_date": T, "discharge_date": T, "ledger_id": c,
                                               "lines": [{"description": "Room", "amount": 3000}]})
    assert r.status_code == 200 and r.json()["bill_no"] == "IPD/0001"
    np = s.post(f"{API}/hospital/patients", json={"name": "TEST_Pat"}).json()
    assert np["reg_no"] == "UHID/0002"


# Hospital: same batch on two lines must not oversell
def test_hospital_duplicate_lines_oversell():
    s = sess("hospital")
    p = s.get(f"{API}/hospital/patients").json()[0]
    amx = [m for m in s.get(f"{API}/hospital/medicines").json() if m["name"].startswith("Amoxicillin")][0]
    r = s.post(f"{API}/hospital/bills", json={"patient_id": p["id"], "kind": "pharmacy", "date": T, "ledger_id": cash(s),
                                               "lines": [{"medicine_id": amx["id"], "qty": 40}, {"medicine_id": amx["id"], "qty": 40}]})
    after = [m for m in s.get(f"{API}/hospital/medicines").json() if m["id"] == amx["id"]][0]
    assert r.status_code == 400 or after["qty"] >= 0, f"oversold: qty={after['qty']}"


# College payroll double-run refused
def test_college_payroll_twice():
    s = sess("college")
    m = T[:7]
    r = s.post(f"{API}/payroll/runs", json={"month": m, "date": T, "ledger_id": cash(s)})
    assert r.status_code == 200 and r.json()["net"] == 45600
    r2 = s.post(f"{API}/payroll/runs", json={"month": m, "date": T, "ledger_id": cash(s)})
    assert r2.status_code == 400
    assert len(s.get(f"{API}/payroll/runs").json()) == 1


# Services billing: recurring once + TDS
def test_services_recurring_tds():
    s = sess("services", "billing")
    assert s.get(f"{API}/industry").json()["industry_mode"] == "billing"
    led = s.post(f"{API}/ledgers", json={"name": f"TEST_Client {uuid.uuid4().hex[:4]}", "group": "sundry_debtors", "opening_balance": 0, "opening_type": "Dr"})
    assert led.status_code in (200, 201), led.text
    cid = led.json()["id"]
    r = s.post(f"{API}/recurring", json={"name": "TEST_Retainer", "party_ledger_id": cid, "account_ledger_id": ledger(s, "sales"), "gst_type": "intra",
                                          "items": [{"name": "Retainer", "qty": 1, "rate": 10000, "gst_rate": 18}], "every_months": 1, "next_date": T})
    assert r.status_code == 200, r.text
    run1 = s.post(f"{API}/recurring/run").json()["created"]
    assert len(run1) == 1 and run1[0]["amount"] == 11800
    assert s.post(f"{API}/recurring/run").json()["created"] == []
    r = s.post(f"{API}/tds/receipts", json={"party_ledger_id": cid, "ledger_id": cash(s), "date": T, "gross": 11800, "tds": 1000})
    assert r.status_code == 200 and r.json()["net"] == 10800
    assert s.post(f"{API}/tds/receipts", json={"party_ledger_id": cid, "ledger_id": cash(s), "date": T, "gross": 100, "tds": 100}).status_code == 400
    assert s.get(f"{API}/reports/trial-balance").status_code == 403
    s.put(f"{API}/industry", json={"industry_type": "services", "industry_mode": "complete"})
    assert s.get(f"{API}/reports/trial-balance").json()["balanced"]


# Viewer cannot change industry
def test_viewer_cannot_change_industry():
    e = f"test_v_{uuid.uuid4().hex[:8]}@ex.in"
    r = requests.post(f"{API}/auth/signup", json={"business_name": "TEST_Viewer Biz", "name": "A", "email": e, "password": "secret12", "industry_type": "retail"})
    assert r.status_code == 200, r.text
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    ve = f"test_vw_{uuid.uuid4().hex[:8]}@ex.in"
    u = requests.post(f"{API}/users", headers=h, json={"name": "TEST_V", "email": ve, "password": "secret12", "role": "viewer"})
    assert u.status_code in (200, 201), u.text
    tok = requests.post(f"{API}/auth/login", json={"email": ve, "password": "secret12"}).json()["token"]
    r = requests.put(f"{API}/industry", headers={"Authorization": f"Bearer {tok}"}, json={"industry_type": "college"})
    assert r.status_code == 403
    assert requests.get(f"{API}/industry", headers=h).json()["industry_type"] == "retail"


# Admin regression: no industry set -> wholesale complete
def test_admin_regression():
    r = requests.post(f"{API}/auth/login", json={"email": "admin@easybooks.in", "password": "Admin@123"})
    assert r.status_code == 200
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    ind = requests.get(f"{API}/industry", headers=h).json()
    assert ind["industry_type"] == "wholesale" and ind["industry_mode"] == "complete"
    assert requests.get(f"{API}/reports/trial-balance", headers=h).status_code == 200
    assert requests.get(f"{API}/dashboard", headers=h).status_code in (200, 404)
