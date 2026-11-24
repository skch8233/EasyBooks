# Round 16: retest of iteration_24 fixes (pharmacy oversell/GST, billing-only 403 guard, POS MRP, TDS base,
# payroll duplicate, signup 422, recurring parallel run, platform list hides demos). Uses signups, not /public/demo.
import os
import uuid
import concurrent.futures as cf
from datetime import date

import pytest
import requests

API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
T = date.today().isoformat()


def signup(ind, mode="complete"):
    e = f"test_r16_{uuid.uuid4().hex[:8]}@ex.in"
    r = requests.post(f"{API}/auth/signup", json={"business_name": f"TEST_R16 {ind} {mode}", "name": "T", "email": e,
                                                  "password": "secret12", "industry_type": ind, "industry_mode": mode})
    assert r.status_code == 200, r.text
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return s


def cash(s):
    return [l["id"] for l in s.get(f"{API}/ledgers").json() if l["group"] == "cash"][0]


def tb(s):
    r = s.get(f"{API}/reports/trial-balance")
    assert r.status_code == 200, r.text
    return r.json()


# ---- signup validation
def test_signup_without_industry_422():
    r = requests.post(f"{API}/auth/signup", json={"business_name": "TEST_x", "name": "A", "email": f"test_{uuid.uuid4().hex[:6]}@ex.in", "password": "secret12"})
    assert r.status_code == 422


# ---- pharmacy: duplicate batch lines + GST split
def test_pharmacy_duplicate_lines_and_gst():
    s = signup("hospital")
    p = s.post(f"{API}/hospital/patients", json={"name": "TEST_Pat"}).json()
    m = s.post(f"{API}/hospital/medicines", json={"name": "TEST_Med", "batch": "B1", "expiry": f"{int(T[:4]) + 1}{T[4:]}", "qty": 10, "mrp": 112, "gst_rate": 12}).json()
    c = cash(s)
    r = s.post(f"{API}/hospital/bills", json={"patient_id": p["id"], "kind": "pharmacy", "date": T, "ledger_id": c,
                                               "lines": [{"medicine_id": m["id"], "qty": 6}, {"medicine_id": m["id"], "qty": 6}]})
    assert r.status_code == 400, r.text
    meds = s.get(f"{API}/hospital/medicines").json()
    assert [x for x in meds if x["id"] == m["id"]][0]["qty"] == 10
    r = s.post(f"{API}/hospital/bills", json={"patient_id": p["id"], "kind": "pharmacy", "date": T, "ledger_id": c,
                                               "lines": [{"medicine_id": m["id"], "qty": 5}, {"medicine_id": m["id"], "qty": 5}]})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["total"] == 1120 and b["gst"] == 120
    assert [x for x in s.get(f"{API}/hospital/medicines").json() if x["id"] == m["id"]][0]["qty"] == 0
    t = tb(s)
    assert t["balanced"]
    v = s.get(f"{API}/vouchers/{b['voucher_id']}").json()
    names = {l["id"]: l["name"] for l in s.get(f"{API}/ledgers").json()}
    cr = {names[e["ledger_id"]]: e["credit"] for e in v["entries"] if e.get("credit")}
    assert cr.get("Pharmacy Sales") == 1000 and cr.get("CGST", cr.get("Output CGST")) == 60 and cr.get("SGST", cr.get("Output SGST")) == 60, cr


def test_pharmacy_parallel_oversell():
    s = signup("hospital")
    p = s.post(f"{API}/hospital/patients", json={"name": "TEST_Pat"}).json()
    m = s.post(f"{API}/hospital/medicines", json={"name": "TEST_Med", "batch": "B2", "expiry": f"{int(T[:4]) + 1}{T[4:]}", "qty": 10, "mrp": 10, "gst_rate": 0}).json()
    c = cash(s)
    body = {"patient_id": p["id"], "kind": "pharmacy", "date": T, "ledger_id": c, "lines": [{"medicine_id": m["id"], "qty": 6}]}
    with cf.ThreadPoolExecutor(4) as ex:
        codes = [f.result().status_code for f in [ex.submit(s.post, f"{API}/hospital/bills", json=body) for _ in range(4)]]
    assert codes.count(200) == 1, codes
    q = [x for x in s.get(f"{API}/hospital/medicines").json() if x["id"] == m["id"]][0]["qty"]
    assert q == 4
    assert len(s.get(f"{API}/hospital/bills").json()) == 1


def test_ipd_bill_dates_saved():
    s = signup("hospital")
    p = s.post(f"{API}/hospital/patients", json={"name": "TEST_Pat"}).json()
    r = s.post(f"{API}/hospital/bills", json={"patient_id": p["id"], "kind": "ipd", "date": T, "admission_date": "2026-01-01", "discharge_date": "2026-01-05",
                                               "ledger_id": cash(s), "lines": [{"description": "Room", "amount": 4000}]})
    assert r.status_code == 200, r.text
    assert r.json()["admission_date"] == "2026-01-01" and r.json()["bill_no"].startswith("IPD")


# ---- billing-only guard
BLOCKED = ["/reports/trial-balance", f"/reports/final-accounts?to_date={T}", "/depreciation", "/tax-provision", "/audit-logs", "/ca/clients"]


@pytest.mark.parametrize("ind", ["wholesale", "services"])
def test_billing_only_blocks_accounting(ind):
    s = signup(ind, "billing")
    for p in BLOCKED:
        r = s.get(f"{API}{p}")
        assert r.status_code == 403, (p, r.status_code)
    r = s.get(f"{API}/reports/register", params={"voucher_type": "sales"})
    assert r.status_code == 200, r.text
    assert s.get(f"{API}/reports/register", params={"voucher_type": "purchase"}).status_code == 403


def test_complete_mode_not_blocked():
    s = signup("wholesale", "complete")
    for p in ["/reports/trial-balance", f"/reports/final-accounts?to_date={T}", "/audit-logs"]:
        assert s.get(f"{API}{p}").status_code == 200, p


def test_retail_billing_not_blocked():
    # guard is only for wholesale/services billing
    s = signup("retail", "billing")
    assert s.get(f"{API}/reports/trial-balance").status_code == 200


# ---- POS MRP inclusive (backend voucher maths with frontend base rate)
def _mrp_rate(mrp, q, g):
    r2 = lambda n: round(n + 1e-9, 2)
    want = r2(q * mrp); base = r2(want / (1 + g / 100))
    for t in (base, r2(base - 0.01), r2(base + 0.01), r2(base - 0.02), r2(base + 0.02)):
        if r2(t + r2(t * g / 100)) == want:
            return round(t / q, 6)
    return round(mrp / (1 + g / 100), 4)


def _exact(mrp, q, g):
    r2 = lambda n: round(n + 1e-9, 2)
    want = r2(q * mrp); base = r2(want / (1 + g / 100))
    for t in (base, r2(base - 0.01), r2(base + 0.01), r2(base - 0.02), r2(base + 0.02)):
        if r2(t + r2(t * g / 100)) == want:
            return round(t / q, 6)


def _post_lines(mrp, q, g):
    one = _exact(mrp, q, g)
    if one is not None:
        return [{"description": "TEST", "qty": q, "rate": one, "gst_rate": g}]
    return [{"description": "TEST", "qty": q - 1, "rate": _exact(mrp, q - 1, g), "gst_rate": g}, {"description": "TEST", "qty": 1, "rate": _exact(mrp, 1, g), "gst_rate": g}]


def test_pos_mrp_inclusive_voucher_total():
    s = signup("retail")
    led = s.get(f"{API}/ledgers").json()
    sales = [l["id"] for l in led if l["group"] == "sales"][0]
    c = cash(s)
    items = []
    for mrp, g, q in ((28, 5, 1), (25, 18, 7), (58, 12, 3)):
        items += _post_lines(mrp, q, g)
    r = s.post(f"{API}/vouchers", json={"voucher_type": "sales", "date": T, "party_ledger_id": c, "account_ledger_id": sales, "gst_type": "intra", "items": items})
    assert r.status_code == 200, r.text
    assert r.json()["amount"] == 28 + 175 + 174, r.json()["amount"]  # voucher must equal MRP total


# ---- TDS base
def test_tds_with_base():
    s = signup("services")
    party = s.post(f"{API}/ledgers", json={"name": "TEST_Client", "group": "sundry_debtors"}).json()["id"]
    r = s.post(f"{API}/tds/receipts", json={"party_ledger_id": party, "ledger_id": cash(s), "date": T, "gross": 11800, "tds": 1000, "tds_base": 10000, "section": "194J"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["tds_base"] == 10000 and d["net"] == 10800
    assert tb(s)["balanced"]


# ---- payroll duplicate (sequential + parallel)
def test_payroll_duplicate_month():
    s = signup("college")
    s.post(f"{API}/payroll/staff", json={"name": "TEST_Staff", "basic": 1000, "allowances": 0, "deductions": 0})
    body = {"month": T[:7], "date": T, "ledger_id": cash(s)}
    with cf.ThreadPoolExecutor(3) as ex:
        codes = [f.result().status_code for f in [ex.submit(s.post, f"{API}/payroll/runs", json=body) for _ in range(3)]]
    runs = s.get(f"{API}/payroll/runs").json()
    assert len([x for x in runs if x["month"] == T[:7]]) == 1, (codes, len(runs))
    assert s.post(f"{API}/payroll/runs", json=body).status_code == 400


def test_fee_parallel_overpay():
    s = signup("college")
    st = s.post(f"{API}/college/students", json={"name": "TEST_Stu", "installments": [{"label": "T1", "due_date": T, "amount": 1000}]}).json()
    body = {"student_id": st["id"], "date": T, "amount": 1000, "ledger_id": cash(s)}
    with cf.ThreadPoolExecutor(3) as ex:
        codes = [f.result().status_code for f in [ex.submit(s.post, f"{API}/college/fees", json=body) for _ in range(3)]]
    bal = [x for x in s.get(f"{API}/college/students").json() if x["id"] == st["id"]][0]["balance"]
    assert bal >= 0, (codes, bal)


# ---- recurring parallel
def test_recurring_parallel_once():
    s = signup("services")
    sales = [l["id"] for l in s.get(f"{API}/ledgers").json() if l["group"] == "sales"][0]
    party = s.post(f"{API}/ledgers", json={"name": "TEST_Client", "group": "sundry_debtors"}).json()["id"]
    r = s.post(f"{API}/recurring", json={"name": "TEST_Ret", "party_ledger_id": party, "account_ledger_id": sales,
                                          "items": [{"description": "SEO", "qty": 1, "rate": 1000, "gst_rate": 18}], "next_date": T})
    assert r.status_code == 200
    with cf.ThreadPoolExecutor(4) as ex:
        res = [f.result() for f in [ex.submit(s.post, f"{API}/recurring/run") for _ in range(4)]]
    total = sum(len(x.json()["created"]) for x in res if x.status_code == 200)
    assert total == 1, [x.status_code for x in res]
    rec = s.get(f"{API}/recurring").json()[0]
    assert len(rec["generated"]) == 1 and rec["next_date"] > T
