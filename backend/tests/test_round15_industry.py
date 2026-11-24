import os
import uuid
from datetime import date

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


def tb_ok(s):
    r = s.get(f"{API}/reports/trial-balance")
    if r.status_code == 403:  # billing-only plans block accounting reports; check books via complete mode
        s.put(f"{API}/industry", json={"industry_type": "services", "industry_mode": "complete"})
        r = s.get(f"{API}/reports/trial-balance")
    tb = r.json()
    assert tb["balanced"], tb


def test_signup_industry_and_plans():
    e = f"test_ind_{uuid.uuid4().hex[:8]}@ex.in"
    r = requests.post(f"{API}/auth/signup", json={"business_name": "TEST Hosp", "name": "A", "email": e, "password": "secret12", "industry_type": "hospital"})
    assert r.status_code == 200, r.text
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    assert requests.get(f"{API}/industry", headers=h).json()["industry_type"] == "hospital"
    plans = requests.get(f"{API}/billing/plans", headers=h).json()["plans"]
    assert {p["key"] for p in plans} == {"hospital_complete", "hospital_complete_multi"} and plans[0]["price"] == 15000
    r = requests.put(f"{API}/industry", headers=h, json={"industry_type": "services", "industry_mode": "billing"})
    assert r.json()["industry_mode"] == "billing"
    assert [p["price"] for p in requests.get(f"{API}/billing/plans", headers=h).json()["plans"]][0] == 2500
    assert requests.post(f"{API}/billing/order", headers=h, json={"plan": "basic"}).status_code in (400, 503)


def test_college_fees_and_payroll():
    s = sess("college")
    st = s.get(f"{API}/college/students").json()[0]
    assert st["total_fee"] == 30000
    r = s.post(f"{API}/college/fees", json={"student_id": st["id"], "date": T, "amount": 40000, "ledger_id": cash(s)})
    assert r.status_code == 400
    r = s.post(f"{API}/college/fees", json={"student_id": st["id"], "date": T, "amount": 15000, "fine": 20, "ledger_id": cash(s)})
    assert r.status_code == 200 and r.json()["receipt_no"] == "FR/0001" and r.json()["balance_after"] == 15000
    st2 = [x for x in s.get(f"{API}/college/students").json() if x["id"] == st["id"]][0]
    assert st2["schedule"][0]["status"] == "paid" and st2["balance"] == 15000
    r = s.post(f"{API}/payroll/runs", json={"month": T[:7], "date": T, "ledger_id": cash(s)})
    assert r.status_code == 200 and r.json()["net"] == 45600
    assert s.post(f"{API}/payroll/runs", json={"month": T[:7], "date": T, "ledger_id": cash(s)}).status_code == 400
    tb_ok(s)


def test_hospital_and_services():
    s = sess("hospital")
    p = s.get(f"{API}/hospital/patients").json()[0]
    m = [x for x in s.get(f"{API}/hospital/medicines").json() if x["name"].startswith("Paracetamol")][0]
    r = s.post(f"{API}/hospital/bills", json={"patient_id": p["id"], "kind": "pharmacy", "date": T, "ledger_id": cash(s), "lines": [{"medicine_id": m["id"], "qty": 500}]})
    assert r.status_code == 400
    r = s.post(f"{API}/hospital/bills", json={"patient_id": p["id"], "kind": "pharmacy", "date": T, "ledger_id": cash(s), "lines": [{"medicine_id": m["id"], "qty": 10}]})
    assert r.status_code == 200 and r.json()["total"] == 20
    assert [x for x in s.get(f"{API}/hospital/medicines").json() if x["id"] == m["id"]][0]["qty"] == 190
    tb_ok(s)
    s = sess("services", "billing")
    led = s.get(f"{API}/ledgers").json()
    sales = [l["id"] for l in led if l["group"] == "sales"][0]
    party = s.post(f"{API}/ledgers", json={"name": "TEST Client", "group": "sundry_debtors"}).json()["id"]
    r = s.post(f"{API}/recurring", json={"name": "Retainer", "party_ledger_id": party, "account_ledger_id": sales, "items": [{"description": "SEO", "qty": 1, "rate": 10000, "gst_rate": 18}], "next_date": T})
    assert r.status_code == 200, r.text
    made = s.post(f"{API}/recurring/run").json()["created"]
    assert len(made) == 1 and made[0]["amount"] == 11800
    assert s.post(f"{API}/recurring/run").json()["created"] == []
    r = s.post(f"{API}/tds/receipts", json={"party_ledger_id": party, "ledger_id": cash(s), "date": T, "gross": 11800, "tds": 1000})
    assert r.status_code == 200 and r.json()["net"] == 10800
    tb_ok(s)
