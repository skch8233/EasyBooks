import os
import uuid

import pytest
import requests

API = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/") + "/api"
P = {"from_date": "2026-04-01", "to_date": "2027-03-31"}


def biz(btype="company"):
    u = uuid.uuid4().hex[:8]
    r = requests.post(f"{API}/auth/signup", json={"business_name": f"TEST_dt_{u}", "name": "T", "email": f"dt_{u}@example.com", "password": "secret1", "phone": "", "state": "Maharashtra", "gstin": ""})
    assert r.status_code == 200, r.text
    s = requests.Session()
    s.headers["Authorization"] = "Bearer " + r.json()["token"]
    s.put(f"{API}/settings", json={"company_name": "DT Co", "state": "27-Maharashtra", "business_type": btype})
    leds = s.get(f"{API}/ledgers").json()
    g = lambda k: [l["id"] for l in leds if l["group"] == k][0]
    return s, g("bank"), g("capital"), [l["id"] for l in leds if l["group"] == "sales"][0]


def jv(s, d, dr, cr, amt):
    r = s.post(f"{API}/vouchers", json={"voucher_type": "journal", "date": d, "entries": [{"ledger_id": dr, "debit": amt}, {"ledger_id": cr, "credit": amt}]})
    assert r.status_code == 200, r.text
    return r.json()


def asset(s, name, method, rate, cost=0, opening=0):
    r = s.post(f"{API}/ledgers", json={"name": name, "group": "fixed_assets", "dep_method": method, "dep_rate": rate, "dep_cost": cost, "opening_balance": opening, "opening_type": "Dr"})
    assert r.status_code == 200, r.text
    return r.json()


def rows(s, p=P):
    d = s.get(f"{API}/depreciation", params=p).json()
    return {r["asset"]: r for r in d["rows"]}, d


@pytest.fixture(scope="module")
def W():
    s, bank, cap, sales = biz()
    jv(s, "2026-04-01", bank, cap, 1000000)
    comp = asset(s, "Computers", "slm", 20)
    furn = asset(s, "Furniture", "wdv", 10)
    jv(s, "2026-10-01", comp["id"], bank, 60000)
    jv(s, "2026-05-01", furn["id"], bank, 50000)
    jv(s, "2027-01-15", furn["id"], bank, 40000)
    return {"s": s, "bank": bank, "cap": cap, "sales": sales, "comp": comp, "furn": furn}


def test_ledger_fields_saved(W):
    led = [l for l in W["s"].get(f"{API}/ledgers").json() if l["id"] == W["comp"]["id"]][0]
    assert led["dep_method"] == "slm" and led["dep_rate"] == 20


def test_calcs(W):
    r, _ = rows(W["s"])
    assert r["Computers"]["depreciation"] == 5983.56
    assert r["Furniture"]["depreciation"] == 7000 and r["Furniture"]["additions_half_rate"] == 40000


def test_midyear_then_full_year_no_double(W):
    s = W["s"]
    half = {"from_date": "2026-04-01", "to_date": "2026-09-30"}
    h = s.post(f"{API}/depreciation/post", json=half)
    assert h.status_code == 200, h.text
    r, d = rows(s)
    assert r["Furniture"]["depreciation"] == 7000 and r["Furniture"]["deletions"] == 0
    assert d["posted"] is not None
    f = s.post(f"{API}/depreciation/post", json=P).json()
    assert f["amount"] == 12983.56
    vs = s.get(f"{API}/vouchers", params={"voucher_type": "journal", "status": "active"}).json()
    assert len([v for v in vs if (v.get("reference_no") or "") == "Depreciation"]) == 1
    r, d = rows(s)
    assert r["Computers"]["depreciation"] == 5983.56 and d["posted"]["amount"] == 12983.56
    s.post(f"{API}/depreciation/post", json=P)
    assert rows(s)[1]["posted"]["amount"] == 12983.56


def test_slm_second_year_uses_cost_and_part_sale():
    s, bank, cap, _ = biz()
    assert s.post(f"{API}/financial-years", json={"start_year": 2025}).status_code in (200, 400)
    jv(s, "2025-04-01", bank, cap, 500000)
    m = asset(s, "Plant", "slm", 10)
    jv(s, "2025-04-01", m["id"], bank, 100000)
    y1 = {"from_date": "2025-04-01", "to_date": "2026-03-31"}
    assert rows(s, y1)[0]["Plant"]["depreciation"] == 10000
    assert s.post(f"{API}/depreciation/post", json=y1).status_code == 200
    r = rows(s)[0]["Plant"]
    assert r["opening"] == 90000 and r["depreciation"] == 10000
    jv(s, "2026-10-01", bank, m["id"], 20000)
    r = rows(s)[0]["Plant"]
    assert 8000 < r["depreciation"] < 10000 and r["deletions"] == 20000


def test_validation(W):
    s = W["s"]
    assert s.get(f"{API}/depreciation", params={"from_date": "2027-04-01", "to_date": "2026-04-01"}).status_code == 400
    assert s.post(f"{API}/depreciation/post", json={"from_date": "2027-04-01", "to_date": "2026-04-01"}).status_code == 400
    assert s.get(f"{API}/tax-provision", params={**P, "rate": -1}).status_code == 422
    assert s.get(f"{API}/tax-provision", params={**P, "add_back": -5}).status_code == 422
    assert s.post(f"{API}/tax-provision/post", json={**P, "rate": -2}).status_code == 422
    assert s.post(f"{API}/tax-provision/post", json={"from_date": "2027-04-01", "to_date": "2026-04-01", "rate": 25}).status_code == 400


def test_tax_half_up_and_replace(W):
    s = W["s"]
    cust = s.post(f"{API}/ledgers", json={"name": "Cust", "group": "sundry_debtors"}).json()
    s.post(f"{API}/vouchers", json={"voucher_type": "sales", "date": "2026-06-01", "party_ledger_id": cust["id"], "account_ledger_id": W["sales"], "gst_type": "none",
                                    "items": [{"description": "x", "hsn": "1", "qty": 1, "rate": 112983.56 + 4938.5 / 0.25 - 100000, "gst_rate": 0}]})
    t = s.get(f"{API}/tax-provision", params={**P, "rate": 25}).json()
    assert t["tax"] == int(t["taxable"] * 0.25 + 0.5)
    a = s.post(f"{API}/tax-provision/post", json={**P, "rate": 25}).json()
    b = s.post(f"{API}/tax-provision/post", json={**P, "rate": 26}).json()
    t2 = s.get(f"{API}/tax-provision", params={**P, "rate": 26}).json()
    assert t2["posted"]["amount"] == b["amount"] and a["amount"] != b["amount"]
    fa = s.get(f"{API}/reports/final-accounts", params={**P, "business_type": "company", "purpose": "company_audit"}).json()
    assert fa["balanced"]
    lab = {r["label"]: r.get("cy") for r in fa["profit_loss"]}
    assert lab["(1) Current tax"] == b["amount"] and lab["Depreciation and amortisation expense"] == 12983.56
    assert any(n.get("schedule") for n in fa["notes"])


def test_tax_rupee_rounding_unit():
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from decimal import Decimal, ROUND_HALF_UP
    assert int(Decimal("1234.5").quantize(Decimal("1"), rounding=ROUND_HALF_UP)) == 1235


def test_misgrouped_depreciation_ledger():
    s, bank, cap, _ = biz()
    jv(s, "2026-04-01", bank, cap, 100000)
    s.post(f"{API}/ledgers", json={"name": "Depreciation", "group": "current_assets"})
    a = asset(s, "Tools", "wdv", 15)
    jv(s, "2026-04-01", a["id"], bank, 10000)
    assert s.post(f"{API}/depreciation/post", json=P).json()["amount"] == 1500
    fa = s.get(f"{API}/reports/final-accounts", params={**P, "business_type": "proprietorship", "purpose": "other"}).json()
    assert {r["label"]: r.get("cy") for r in fa["profit_loss"]}["Depreciation"] == 1500 and fa["balanced"]


def test_viewer_blocked(W):
    s = W["s"]
    u = uuid.uuid4().hex[:6]
    r = s.post(f"{API}/users", json={"name": "V", "email": f"viewer_{u}@example.com", "password": "secret1", "role": "viewer"})
    assert r.status_code == 200, r.text
    tok = requests.post(f"{API}/auth/login", json={"email": f"viewer_{u}@example.com", "password": "secret1"}).json()["token"]
    v = requests.Session()
    v.headers["Authorization"] = "Bearer " + tok
    assert v.get(f"{API}/depreciation", params=P).status_code == 200
    assert v.post(f"{API}/depreciation/post", json=P).status_code == 403
    assert v.post(f"{API}/tax-provision/post", json={**P, "rate": 25}).status_code == 403


def test_full_year_then_half_year_replaces_overlap():
    s, bank, cap, _ = biz()
    jv(s, "2026-04-01", bank, cap, 100000)
    a = asset(s, "Mach", "wdv", 10)
    jv(s, "2026-04-01", a["id"], bank, 10000)
    assert s.post(f"{API}/depreciation/post", json=P).json()["amount"] == 1000
    half = {"from_date": "2026-04-01", "to_date": "2026-09-30"}
    h = s.post(f"{API}/depreciation/post", json=half).json()
    assert h["amount"] == round(10000 * 0.10 * 183 / 365, 2)
    vs = [v for v in s.get(f"{API}/vouchers", params={"voucher_type": "journal", "status": "active"}).json() if v.get("reference_no") == "Depreciation"]
    assert len(vs) == 1


def test_short_period_by_days_and_proportional_sale():
    s, bank, cap, _ = biz()
    jv(s, "2026-04-01", bank, cap, 500000)
    a = asset(s, "Plant2", "slm", 10, cost=100000, opening=90000)
    q = {"from_date": "2026-04-01", "to_date": "2026-06-29"}
    r = rows(s, q)[0]["Plant2"]
    assert r["depreciation"] == round(100000 * 0.10 * 90 / 365, 2)
    jv(s, "2026-10-01", bank, a["id"], 18000)
    r = rows(s)[0]["Plant2"]
    part = 100000 * 18000 / 90000
    exp = (100000 - part) * 0.10 + part * 0.10 * 183 / 365
    assert abs(r["depreciation"] - exp) < 0.02


def test_cost_rolls_forward():
    s, bank, cap, _ = biz()
    assert s.post(f"{API}/financial-years", json={"start_year": 2025}).status_code in (200, 400)
    jv(s, "2025-04-01", bank, cap, 500000)
    a = asset(s, "Van", "slm", 20)
    jv(s, "2025-04-01", a["id"], bank, 50000)
    y1 = {"from_date": "2025-04-01", "to_date": "2026-03-31"}
    s.post(f"{API}/depreciation/post", json=y1)
    jv(s, "2026-04-01", a["id"], bank, 25000)
    r = rows(s)[0]["Van"]
    assert r["cost"] == 50000 and r["depreciation"] == 15000


def test_bad_calendar_date_tax_friendly(W):
    r = W["s"].post(f"{API}/tax-provision/post", json={"from_date": "2026-13-01", "to_date": "2027-03-31", "rate": 25})
    assert r.status_code == 400 and "date" in r.json()["detail"].lower()


def test_wrong_group_auto_never_reused():
    s, bank, cap, _ = biz()
    jv(s, "2026-04-01", bank, cap, 100000)
    s.post(f"{API}/ledgers", json={"name": "Depreciation", "group": "current_assets"})
    s.post(f"{API}/ledgers", json={"name": "Depreciation (auto)", "group": "sundry_creditors"})
    a = asset(s, "Tools2", "wdv", 15)
    jv(s, "2026-04-01", a["id"], bank, 10000)
    assert s.post(f"{API}/depreciation/post", json=P).status_code == 200
    led = [l for l in s.get(f"{API}/ledgers").json() if l.get("system_key") == "depreciation"]
    assert len(led) == 1 and led[0]["group"] == "indirect_expense" and led[0]["name"] == "Depreciation (auto 2)"
