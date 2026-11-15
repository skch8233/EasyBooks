# Round 10: voucher project tagging + GST invoice fields, project-wise reports, project P&L summary, e-way bills, final accounts
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
    r = requests.post(f"{API}/auth/signup", json={"business_name": f"TEST_R10_{U}", "name": "TEST Owner", "email": f"test_r10_{U}_{uuid.uuid4().hex[:4]}@example.com",
                                                  "password": "secret1", "phone": "", "state": "Maharashtra", "gstin": ""})
    assert r.status_code == 200, r.text
    s = sess(r.json()["token"])
    bid = r.json()["user"]["business_id"]
    assert admin.post(f"{API}/erp/platform/{bid}/grant", json={"days": 365}).status_code == 200
    st = s.put(f"{API}/settings", json={"company_name": f"TEST_R10_{U}", "address": "1 Test Rd, Pune", "state": "27-Maharashtra", "gstin": "27AABCA4829K1Z4",
                                         "pan": "AABCA4829K", "business_type": "company", "cin": "U12345MH2020PTC123456"})
    assert st.status_code == 200, st.text
    led = {l["group"]: l["id"] for l in s.get(f"{API}/ledgers").json()}
    cust = s.post(f"{API}/ledgers", json={"name": f"TEST_Cust_{U}", "group": "sundry_debtors", "state": "29-Karnataka", "gstin": "29AAACH7194M1Z8"})
    assert cust.status_code == 200, cust.text
    c = s.post(f"{API}/erp/parties", json={"kind": "client", "company_name": f"TEST_cl_{U}", "state": "Maharashtra"}).json()
    p1 = s.post(f"{API}/erp/projects", json={"name": f"TEST_P1_{U}", "client_id": c["id"], "contract_value": 100000}).json()
    p2 = s.post(f"{API}/erp/projects", json={"name": f"TEST_P2_{U}", "client_id": c["id"], "contract_value": 100000}).json()
    return {"s": s, "admin": admin, "led": led, "cust": cust.json()["id"], "client": c, "p1": p1, "p2": p2, "state": {}}


def sales(W, project_id=None, fmt="goods", meta=None, gst_type="inter", rate=10000):
    return {"voucher_type": "sales", "date": TODAY, "party_ledger_id": W["cust"], "account_ledger_id": W["led"]["sales"], "gst_type": gst_type,
            "items": [{"description": "TEST_item", "hsn": "998313", "qty": 2, "rate": rate, "gst_rate": 18, "unit": "nos"}],
            "project_id": project_id, "invoice_format": fmt, "gst_meta": meta or {}}


class TestVoucherProject:
    def test_sales_voucher_stores_project_format_meta(self, W):
        s = W["s"]
        meta = {"place_of_supply": "29-Karnataka", "reverse_charge": "no", "transport_mode": "Road", "vehicle_no": "MH12AB1234", "contract_ref": "SOW-1"}
        r = s.post(f"{API}/vouchers", json=sales(W, W["p1"]["id"], "service", meta))
        assert r.status_code == 200, r.text
        vid = r.json()["id"]
        W["state"]["v1"] = vid
        g = s.get(f"{API}/vouchers/{vid}").json()
        assert g["project_id"] == W["p1"]["id"] and g["project_code"] == W["p1"]["code"]
        assert g["invoice_format"] == "service" and g["gst_meta"]["vehicle_no"] == "MH12AB1234"
        assert g["totals"]["igst"] == 3600

    def test_edit_keeps_fields(self, W):
        s, vid = W["s"], W["state"]["v1"]
        body = sales(W, W["p1"]["id"], "service", {"place_of_supply": "29-Karnataka", "vehicle_no": "MH12ZZ9999"}, rate=12000)
        r = s.put(f"{API}/vouchers/{vid}", json=body)
        assert r.status_code == 200, r.text
        g = s.get(f"{API}/vouchers/{vid}").json()
        assert g["project_id"] == W["p1"]["id"] and g["invoice_format"] == "service" and g["gst_meta"]["vehicle_no"] == "MH12ZZ9999"
        assert g["amount"] == 28320

    def test_bad_project_and_untagged(self, W):
        s = W["s"]
        assert s.post(f"{API}/vouchers", json=sales(W, "nope")).status_code == 400
        r = s.post(f"{API}/vouchers", json=sales(W, None, rate=5000))
        assert r.status_code == 200
        assert r.json().get("project_id") is None
        W["state"]["v0"] = r.json()["id"]

    def test_erp_invoice_auto_tags_project(self, W):
        s = W["s"]
        inv = s.post(f"{API}/erp/invoices", json={"date": TODAY, "client_id": W["client"]["id"], "project_id": W["p2"]["id"], "template": "gst_service",
                                                   "gst_meta": {"contract_ref": "MSA-1", "billing_period": "Oct"}, "retention_pct": 5,
                                                   "items": [{"description": "TEST_svc", "hsn": "998313", "unit": "nos", "qty": 1, "rate": 50000, "discount": 0, "gst_rate": 18}]})
        assert inv.status_code == 200, inv.text
        iid = inv.json()["id"]
        W["state"]["inv"] = iid
        f = s.post(f"{API}/erp/invoices/{iid}/finalize")
        assert f.status_code == 200, f.text
        d = s.get(f"{API}/erp/invoices/{iid}").json()
        assert d["gst_meta"]["contract_ref"] == "MSA-1" and d["template"] == "gst_service"
        vid = d.get("voucher_id")
        assert vid, d.keys()
        v = s.get(f"{API}/vouchers/{vid}").json()
        assert v["project_id"] == W["p2"]["id"] and v["invoice_format"] == "service"

    def test_erp_default_template_goods(self, W):
        assert W["s"].get(f"{API}/erp/settings").json()["default_invoice_template"] == "gst_goods"


class TestProjectReports:
    def test_tb_bs_balanced_per_project(self, W):
        s = W["s"]
        for pid in (None, W["p1"]["id"], W["p2"]["id"], "none"):
            prm = {"project_id": pid} if pid else {}
            tb = s.get(f"{API}/reports/trial-balance", params=prm).json()
            bs = s.get(f"{API}/reports/balance-sheet", params=prm).json()
            assert tb["balanced"] and bs["balanced"], pid

    def test_pl_project_split_sums(self, W):
        s = W["s"]
        net = lambda **p: s.get(f"{API}/reports/profit-loss", params=p).json()["net_profit"]
        allp, a, b, n = net(), net(project_id=W["p1"]["id"]), net(project_id=W["p2"]["id"]), net(project_id="none")
        assert a == 24000 and b == 50000 and n == 10000
        assert round(a + b + n, 2) == allp

    def test_register_project_filter(self, W):
        s = W["s"]
        reg = lambda **p: s.get(f"{API}/reports/register", params={"voucher_type": "sales", **p}).json()
        assert len(reg(project_id=W["p1"]["id"])["rows"]) == 1
        assert len(reg()["rows"]) == 3
        # "Not tagged" option in UI sends project_id=none
        assert len(reg(project_id="none")["rows"]) == 1, "register project_id=none should return untagged vouchers"

    def test_project_summary(self, W):
        s = W["s"]
        ps = s.get(f"{API}/reports/project-summary").json()
        pl = s.get(f"{API}/reports/profit-loss").json()
        assert ps["combined"]["net_profit"] == pl["net_profit"]
        assert round(sum(r["net_profit"] for r in ps["rows"]), 2) == ps["combined"]["net_profit"]
        codes = {r["code"] for r in ps["rows"]}
        assert W["p1"]["code"] in codes and W["p2"]["code"] in codes and "-" in codes


class TestEway:
    def test_save_list_number_writeback(self, W):
        s, vid = W["s"], W["state"]["v1"]
        r = s.post(f"{API}/eway-bills", json={"source": "voucher", "source_id": vid, "data": {"docNo": "S1"}, "ewb_json": {"version": "1.0.0621", "billLists": []}})
        assert r.status_code == 200, r.text
        eid = r.json()["id"]
        assert any(e["id"] == eid and e["status"] == "json_ready" for e in s.get(f"{API}/eway-bills").json())
        assert s.put(f"{API}/eway-bills/{eid}/number", json={"ewb_no": "12345678901A"}).status_code in (400, 422)
        assert s.put(f"{API}/eway-bills/{eid}/number", json={"ewb_no": "1234"}).status_code in (400, 422)
        ok = s.put(f"{API}/eway-bills/{eid}/number", json={"ewb_no": "381049281742", "ewb_date": TODAY})
        assert ok.status_code == 200
        assert s.get(f"{API}/vouchers/{vid}").json()["gst_meta"]["eway_bill_no"] == "381049281742"
        assert next(e for e in s.get(f"{API}/eway-bills").json() if e["id"] == eid)["status"] == "generated"
        assert s.put(f"{API}/eway-bills/xxx/number", json={"ewb_no": "381049281742"}).status_code == 404

    def test_erp_invoice_writeback(self, W):
        s, iid = W["s"], W["state"]["inv"]
        eid = s.post(f"{API}/eway-bills", json={"source": "erp_invoice", "source_id": iid, "data": {}, "ewb_json": {}}).json()["id"]
        assert s.put(f"{API}/eway-bills/{eid}/number", json={"ewb_no": "111122223333"}).status_code == 200
        assert s.get(f"{API}/erp/invoices/{iid}").json()["gst_meta"]["eway_bill_no"] == "111122223333"


class TestFinalAccounts:
    def _fa(self, W, **p):
        r = W["s"].get(f"{API}/reports/final-accounts", params={"to_date": TODAY, **p})
        assert r.status_code == 200, r.text
        return r.json()

    def test_company_schedule3(self, W):
        d = self._fa(W, purpose="company_audit")
        assert d["kind"] == "company" and d["business_type"] == "company" and d["balanced"]
        labels = [x["label"] for x in d["balance_sheet"]]
        assert "I. EQUITY AND LIABILITIES" in labels and "II. ASSETS" in labels
        assert any("VII." in x["label"] for x in d["profit_loss"])
        assert d["cin"].startswith("U12345")
        pl = W["s"].get(f"{API}/reports/profit-loss", params={"to_date": TODAY}).json()
        assert d["profit_loss"][-1]["cy"] == pl["net_profit"]

    def test_notes_tie_to_statement(self, W):
        d = self._fa(W, purpose="tax_audit", business_type="proprietorship")
        assert d["kind"] == "other" and d["balanced"]
        notes = {n["no"]: n for n in d["notes"]}
        for line in d["balance_sheet"] + d["profit_loss"]:
            if line.get("note"):
                assert notes[line["note"]]["cy"] == line["cy"], line
        assert min(notes) == 2
        assert any("44AB" in d["purpose_text"] for _ in [0])
        assert any("PAN" in p for p in d["policies"])

    def test_project_final_accounts_balanced(self, W):
        for pid in (W["p1"]["id"], W["p2"]["id"], "none"):
            d = self._fa(W, project_id=pid, business_type="partnership")
            assert d["balanced"], pid

    def test_company_audit_for_non_company(self, W):
        # API accepts any combination; UI restricts company_audit to company
        r = W["s"].get(f"{API}/reports/final-accounts", params={"to_date": TODAY, "business_type": "proprietorship", "purpose": "company_audit"})
        print("company_audit for proprietorship ->", r.status_code)

    def test_cleanup_cancel(self, W):
        s = W["s"]
        for k in ("v0",):
            s.post(f"{API}/vouchers/{W['state'][k]}/cancel", json={"reason": "TEST cleanup"})
