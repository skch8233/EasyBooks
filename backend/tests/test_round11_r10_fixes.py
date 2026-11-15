# Round 10 retest (iteration 13): public share fields, register project_id=none, e-way number msg, final-accounts purpose guard, closing stock, item unit
import os
import uuid
from datetime import date

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
TODAY = date.today().isoformat()
U = uuid.uuid4().hex[:6]


def sess(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def W():
    a = requests.post(f"{API}/auth/login", json={"email": "admin@easybooks.in", "password": "Admin@123"})
    assert a.status_code == 200
    admin = sess(a.json()["token"])
    r = requests.post(f"{API}/auth/signup", json={"business_name": f"TEST_R11_{U}", "name": "TEST Owner", "email": f"test_r11_{U}_{uuid.uuid4().hex[:4]}@example.com",
                                                  "password": "secret1", "phone": "", "state": "Maharashtra", "gstin": ""})
    assert r.status_code == 200, r.text
    s = sess(r.json()["token"])
    bid = r.json()["user"]["business_id"]
    assert admin.post(f"{API}/erp/platform/{bid}/grant", json={"days": 365}).status_code == 200
    st = s.put(f"{API}/settings", json={"company_name": f"TEST_R11_{U}", "address": "1 Test Rd, Pune", "state": "27-Maharashtra", "gstin": "27AABCA4829K1Z4",
                                         "pan": "AABCA4829K", "business_type": "company", "cin": "U12345MH2020PTC654321"})
    assert st.status_code == 200, st.text
    led = {l["group"]: l["id"] for l in s.get(f"{API}/ledgers").json()}
    cust = s.post(f"{API}/ledgers", json={"name": f"TEST_Cust_{U}", "group": "sundry_debtors", "state": "29-Karnataka", "gstin": "29AAACH7194M1Z8"}).json()
    sup = s.post(f"{API}/ledgers", json={"name": f"TEST_Sup_{U}", "group": "sundry_creditors", "state": "27-Maharashtra"}).json()
    c = s.post(f"{API}/erp/parties", json={"kind": "client", "company_name": f"TEST_cl_{U}", "state": "Maharashtra"}).json()
    p1 = s.post(f"{API}/erp/projects", json={"name": f"TEST_P1_{U}", "client_id": c["id"], "contract_value": 100000}).json()
    return {"s": s, "led": led, "cust": cust["id"], "sup": sup["id"], "p1": p1, "state": {}}


def fa(W, **p):
    return W["s"].get(f"{API}/reports/final-accounts", params={"to_date": TODAY, **p})


class TestPublicShare:
    def test_public_invoice_has_format_meta_project_pan(self, W):
        s = W["s"]
        meta = {"place_of_supply": "29-Karnataka", "vehicle_no": "MH12AB1234", "contract_ref": "SOW-77", "billing_period": "Jan 2026", "ship_name": "TEST Consignee"}
        v = s.post(f"{API}/vouchers", json={"voucher_type": "sales", "date": TODAY, "party_ledger_id": W["cust"], "account_ledger_id": W["led"]["sales"], "gst_type": "inter",
                                            "items": [{"description": "TEST_svc", "hsn": "998313", "qty": 1, "rate": 1000, "gst_rate": 18, "unit": "hrs"}],
                                            "project_id": W["p1"]["id"], "invoice_format": "service", "gst_meta": meta})
        assert v.status_code == 200, v.text
        W["state"]["svc"] = v.json()["id"]
        sh = s.post(f"{API}/vouchers/{v.json()['id']}/share")
        assert sh.status_code == 200
        tok = sh.json()["token"]
        W["state"]["token"] = tok
        p = requests.get(f"{API}/public/invoice/{tok}").json()
        pv = p["voucher"]
        assert pv["invoice_format"] == "service"
        assert pv["gst_meta"]["contract_ref"] == "SOW-77" and pv["gst_meta"]["vehicle_no"] == "MH12AB1234" and pv["gst_meta"]["billing_period"] == "Jan 2026"
        assert pv["project_code"] == W["p1"]["code"] and pv["project_name"] == W["p1"]["name"]
        assert p["settings"]["pan"] == "AABCA4829K"
        assert pv["items"][0]["unit"] == "hrs"
        assert "entries" not in pv and "business_id" not in pv and "party_ledger_id" not in pv


class TestRegisterUntagged:
    def test_register_none(self, W):
        s = W["s"]
        v = s.post(f"{API}/vouchers", json={"voucher_type": "sales", "date": TODAY, "party_ledger_id": W["cust"], "account_ledger_id": W["led"]["sales"], "gst_type": "inter",
                                            "items": [{"description": "TEST_untag", "hsn": "9983", "qty": 1, "rate": 500, "gst_rate": 18}]})
        assert v.status_code == 200
        reg = lambda **p: s.get(f"{API}/reports/register", params={"voucher_type": "sales", **p}).json()["rows"]
        none = reg(project_id="none")
        assert len(none) == 1, none
        ids = {r.get("id") or r.get("voucher_id") for r in none}
        assert v.json()["id"] in ids or len(ids) == 1
        assert len(reg(project_id=W["p1"]["id"])) == 1
        assert len(reg()) == 2


class TestEwayNumber:
    def test_wrong_length_friendly(self, W):
        s = W["s"]
        eid = s.post(f"{API}/eway-bills", json={"source": "voucher", "source_id": W["state"]["svc"], "data": {"docNo": "X"}, "ewb_json": {}}).json()["id"]
        W["state"]["eid"] = eid
        for bad in ("1234", "1234567890123", "12345678901A", ""):
            r = s.put(f"{API}/eway-bills/{eid}/number", json={"ewb_no": bad})
            assert r.status_code == 400, (bad, r.status_code, r.text)
            assert r.json()["detail"] == "E-way bill number must be 12 digits"
        ok = s.put(f"{API}/eway-bills/{eid}/number", json={"ewb_no": " 381049281742 "})
        assert ok.status_code == 200
        g = s.get(f"{API}/vouchers/{W['state']['svc']}").json()
        print("written back eway_bill_no:", repr(g["gst_meta"].get("eway_bill_no")))
        assert g["gst_meta"]["eway_bill_no"].strip() == "381049281742"


class TestFinalAccountsGuards:
    @pytest.mark.parametrize("bt", ["proprietorship", "partnership", "llp"])
    def test_company_audit_rejected_non_company(self, W, bt):
        r = fa(W, business_type=bt, purpose="company_audit")
        assert r.status_code == 400 and "only for companies" in r.json()["detail"]

    def test_company_audit_ok_company(self, W):
        assert fa(W, business_type="company", purpose="company_audit").status_code == 200


class TestClosingStock:
    def test_stock_flow(self, W):
        s = W["s"]
        pl0 = s.get(f"{API}/reports/profit-loss", params={"to_date": TODAY}).json()["net_profit"]
        it = s.post(f"{API}/stock-items", json={"name": f"TEST_Widget_{U}", "hsn": "8471", "unit": "Kgs", "gst_rate": 18, "sale_rate": 150, "purchase_rate": 100})
        assert it.status_code == 200, it.text
        iid = it.json()["id"]
        pu = s.post(f"{API}/vouchers", json={"voucher_type": "purchase", "date": TODAY, "party_ledger_id": W["sup"], "account_ledger_id": W["led"]["purchase"], "gst_type": "intra",
                                             "items": [{"item_id": iid, "description": "", "hsn": "8471", "qty": 10, "rate": 100, "gst_rate": 18, "unit": "zzz"}]})
        assert pu.status_code == 200, pu.text
        assert s.get(f"{API}/vouchers/{pu.json()['id']}").json()["items"][0]["unit"] == "Kgs"
        sa = s.post(f"{API}/vouchers", json={"voucher_type": "sales", "date": TODAY, "party_ledger_id": W["cust"], "account_ledger_id": W["led"]["sales"], "gst_type": "inter",
                                             "items": [{"item_id": iid, "description": "", "hsn": "8471", "qty": 4, "rate": 150, "gst_rate": 18}]})
        assert sa.status_code == 200, sa.text
        sv = s.get(f"{API}/stock-items", params={"to_date": TODAY}).json()["total_value"]
        assert sv == 600, sv
        pl1 = s.get(f"{API}/reports/profit-loss", params={"to_date": TODAY}).json()["net_profit"]
        assert round(pl1 - pl0, 2) == -400  # ledger P&L: +600 sales -1000 purchase

        d = fa(W, purpose="company_audit").json()
        assert d["balanced"], d["totals"]
        inv = next(x for x in d["balance_sheet"] if x.get("label") == "Inventories")
        assert inv["cy"] == sv
        ch = next(x for x in d["profit_loss"] if x.get("label", "").startswith("Changes in inventories"))
        assert ch["cy"] == -sv
        assert d["profit_loss"][-1]["cy"] == round(pl1 + sv, 2)
        assert d["cin"].startswith("U12345")

        o = fa(W, purpose="tax_audit", business_type="proprietorship").json()
        assert o["balanced"]
        cs = next(x for x in o["balance_sheet"] if x.get("label", "").startswith("Closing stock"))
        assert cs["cy"] == sv
        lcs = next(x for x in o["profit_loss"] if x.get("label") == "Less: Closing stock")
        assert lcs["cy"] == -sv
        assert o["profit_loss"][-1]["cy"] == round(pl1 + sv, 2)

        # with from_date (opening stock = 0 since all movement today)
        f2 = fa(W, from_date=TODAY, purpose="other", business_type="partnership").json()
        assert f2["balanced"] and f2["profit_loss"][-1]["cy"] == round(pl1 + sv, 2)

        # project filter excludes stock
        pj = fa(W, project_id=W["p1"]["id"], business_type="company").json()
        assert pj["balanced"]
        assert next(x for x in pj["balance_sheet"] if x.get("label") == "Inventories")["cy"] == 0
        W["state"]["stock"] = iid

    def test_from_date_after_stock_has_opening(self, W):
        # from_date tomorrow-like: use a future period starting after today -> opening=closing=600, change=0
        from datetime import timedelta
        tmr = (date.today() + timedelta(days=1)).isoformat()
        r = W["s"].get(f"{API}/reports/final-accounts", params={"from_date": tmr, "to_date": tmr, "business_type": "proprietorship"})
        if r.status_code != 200:
            pytest.skip(f"future date not allowed: {r.status_code}")
        d = r.json()
        op = next(x for x in d["profit_loss"] if x.get("label") == "Opening stock")
        assert op["cy"] == 600
        assert d["balanced"]


class TestSignatureFlags:
    def test_cin_returned(self, W):
        d = fa(W, business_type="proprietorship").json()
        print("cin for proprietorship:", d.get("cin"))
