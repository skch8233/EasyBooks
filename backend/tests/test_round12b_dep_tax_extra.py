# Round 12 extra: depreciation & income-tax provision edge cases (testing agent iteration 15)
import os
import uuid

import pytest
import requests

API = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/") + "/api"
P = {"from_date": "2026-04-01", "to_date": "2027-03-31"}


def biz(btype="company"):
    u = uuid.uuid4().hex[:8]
    r = requests.post(f"{API}/auth/signup", json={"business_name": f"TEST_dtx_{u}", "name": "T", "email": f"dtx_{u}@example.com", "password": "secret1", "phone": "", "state": "Maharashtra", "gstin": ""})
    assert r.status_code == 200, r.text
    s = requests.Session()
    s.headers["Authorization"] = "Bearer " + r.json()["token"]
    s.put(f"{API}/settings", json={"company_name": "DTX Co", "state": "27-Maharashtra", "business_type": btype})
    leds = s.get(f"{API}/ledgers").json()
    g = lambda k: [l["id"] for l in leds if l["group"] == k][0]
    return s, g("bank"), g("capital"), g("sales")


def jv(s, d, dr, cr, amt):
    r = s.post(f"{API}/vouchers", json={"voucher_type": "journal", "date": d, "entries": [{"ledger_id": dr, "debit": amt}, {"ledger_id": cr, "credit": amt}]})
    assert r.status_code == 200, r.text
    return r.json()


def asset(s, name, method, rate, cost=0, opening=0):
    r = s.post(f"{API}/ledgers", json={"name": name, "group": "fixed_assets", "dep_method": method, "dep_rate": rate, "dep_cost": cost, "opening_balance": opening, "opening_type": "Dr"})
    assert r.status_code == 200, r.text
    return r.json()


def dep_vouchers(s):
    vs = s.get(f"{API}/vouchers", params={"voucher_type": "journal", "status": "active"}).json()
    return [v for v in vs if (v.get("reference_no") or "") == "Depreciation"]


# Ledger dep fields: create -> PUT -> GET persistence
def test_ledger_dep_fields_update_persist():
    s, *_ = biz()
    a = asset(s, "TEST_Mach", "wdv", 15)
    body = {**a, "dep_method": "slm", "dep_rate": 12.5, "dep_cost": 75000}
    r = s.put(f"{API}/ledgers/{a['id']}", json=body)
    assert r.status_code == 200, r.text
    led = [l for l in s.get(f"{API}/ledgers").json() if l["id"] == a["id"]][0]
    assert led["dep_method"] == "slm" and led["dep_rate"] == 12.5 and led["dep_cost"] == 75000


# Tax rounds half-up: taxable 1001 @ 50% = 500.5 -> 501
def test_tax_half_up_exact():
    s, bank, cap, sales = biz()
    jv(s, "2026-06-01", bank, sales, 1001)
    t = s.get(f"{API}/tax-provision", params={**P, "rate": 50}).json()
    assert t["pbt"] == 1001 and t["tax"] == 501
    p = s.post(f"{API}/tax-provision/post", json={**P, "rate": 50})
    assert p.status_code == 200 and p.json()["amount"] == 501


# Validation: rate > 60, negative deductions, bad calendar date, > 1 year
def test_validation_extra():
    s, *_ = biz()
    assert s.get(f"{API}/tax-provision", params={**P, "rate": 61}).status_code == 422
    assert s.get(f"{API}/tax-provision", params={**P, "deductions": -1}).status_code == 422
    assert s.post(f"{API}/tax-provision/post", json={**P, "rate": 25, "add_back": -1}).status_code == 422
    assert s.post(f"{API}/tax-provision/post", json={**P, "rate": 25, "deductions": -1}).status_code == 422
    assert s.get(f"{API}/depreciation", params={"from_date": "2026-04-01", "to_date": "2027-12-31"}).status_code == 400


def test_bad_calendar_date_tax_post_not_500():
    s, *_ = biz()
    r = s.post(f"{API}/tax-provision/post", json={"from_date": "2026-13-01", "to_date": "2027-03-31", "rate": 25})
    assert r.status_code in (400, 422), f"{r.status_code} {r.text[:200]}"


def test_bad_calendar_date_dep_post_not_500():
    s, *_ = biz()
    r = s.post(f"{API}/depreciation/post", json={"from_date": "2026-04-01", "to_date": "2027-02-30"})
    assert r.status_code in (400, 422), f"{r.status_code} {r.text[:200]}"


# Full year posted first, then half-year re-post should not double-count
def test_full_then_half_no_double():
    s, bank, cap, _ = biz()
    jv(s, "2026-04-01", bank, cap, 100000)
    a = asset(s, "TEST_Tools", "wdv", 10)
    jv(s, "2026-04-01", a["id"], bank, 10000)
    assert s.post(f"{API}/depreciation/post", json=P).json()["amount"] == 1000
    s.post(f"{API}/depreciation/post", json={"from_date": "2026-04-01", "to_date": "2026-09-30"})
    full = s.get(f"{API}/depreciation", params=P).json()
    total_posted = sum(v["amount"] for v in dep_vouchers(s))
    assert total_posted <= 1000.01, f"double count: active dep vouchers total {total_posted}, posted={full['posted']}"


# SLM with explicit original cost in year 2 (opening WDV 90000, cost 100000)
def test_slm_dep_cost_opening():
    s, bank, cap, _ = biz()
    a = asset(s, "TEST_Plant2", "slm", 10, cost=100000, opening=90000)
    r = {x["asset"]: x for x in s.get(f"{API}/depreciation", params=P).json()["rows"]}["TEST_Plant2"]
    assert r["depreciation"] == 10000 and r["closing"] == 80000


# Company final accounts lines + BS provisions + balanced; viewer can GET tax-provision
def test_company_final_accounts_lines():
    s, bank, cap, sales = biz("company")
    jv(s, "2026-04-01", bank, cap, 200000)
    a = asset(s, "TEST_Comp", "wdv", 40)
    jv(s, "2026-04-02", a["id"], bank, 50000)
    jv(s, "2026-06-01", bank, sales, 100000)
    assert s.post(f"{API}/depreciation/post", json=P).json()["amount"] == 20000
    t = s.post(f"{API}/tax-provision/post", json={**P, "rate": 25.168}).json()
    assert t["amount"] == round(80000 * 0.25168)
    fa = s.get(f"{API}/reports/final-accounts", params={**P, "business_type": "company", "purpose": "company_audit"}).json()
    assert fa["balanced"]
    labels = [r["label"] for r in fa["profit_loss"]]
    lab = {r["label"]: r.get("cy") for r in fa["profit_loss"]}
    assert lab["Depreciation and amortisation expense"] == 20000
    assert "VI. Tax expense" in labels and lab["(1) Current tax"] == t["amount"] and lab["(2) Deferred tax"] == 0
    assert any(l.startswith("VII") for l in labels), labels
    bs = str(fa.get("balance_sheet"))
    assert "Short-term provisions" in bs
    assert any(n.get("schedule") for n in fa["notes"])


def test_non_company_final_accounts_lines():
    s, bank, cap, sales = biz("partnership")
    jv(s, "2026-04-01", bank, cap, 200000)
    a = asset(s, "TEST_Furn", "wdv", 10)
    jv(s, "2026-04-02", a["id"], bank, 50000)
    jv(s, "2026-06-01", bank, sales, 100000)
    s.post(f"{API}/depreciation/post", json=P)
    t = s.post(f"{API}/tax-provision/post", json={**P, "rate": 31.2}).json()
    fa = s.get(f"{API}/reports/final-accounts", params={**P, "business_type": "partnership", "purpose": "other"}).json()
    assert fa["balanced"]
    lab = {r["label"]: r.get("cy") for r in fa["profit_loss"]}
    assert lab["Depreciation"] == 5000
    assert lab["Net profit / (loss) before tax"] == 95000
    assert lab["Less: Provision for income tax"] == t["amount"] == round(95000 * 0.312)
    assert lab["Net profit / (loss) after tax transferred to capital account"] == 95000 - t["amount"]
