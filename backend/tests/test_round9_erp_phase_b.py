# Round 9 ERP Phase B: PR -> RFQ -> vendor quotes -> comparative -> PO -> GRN -> purchase bill -> payment, expenses, permissions
import os
import uuid
from datetime import date

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
TODAY = date.today().isoformat()
U = uuid.uuid4().hex[:6]


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    return s


@pytest.fixture(scope="module")
def admin():
    return login("admin@easybooks.in", "Admin@123")


def mk_party(s, kind, **kw):
    r = s.post(f"{API}/erp/parties", json={"kind": kind, "company_name": f"TEST_{kind}_{uuid.uuid4().hex[:6]}", "state": "", **kw})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def setup(admin):
    c = mk_party(admin, "client")
    v1 = mk_party(admin, "vendor", email="delivered@resend.dev")
    v2 = mk_party(admin, "vendor")
    p = admin.post(f"{API}/erp/projects", json={"name": f"TEST_projB_{U}", "client_id": c["id"], "contract_value": 900000})
    assert p.status_code == 200, p.text
    return {"client": c, "v1": v1, "v2": v2, "project": p.json()}


def items():
    return [{"description": "TEST_Cement bags", "unit": "bag", "qty": 100}, {"description": "TEST_Steel", "unit": "kg", "qty": 50}]


def ledger(s, group):
    return next(l["id"] for l in s.get(f"{API}/ledgers").json() if l["group"] == group)


def tb_ok(s):
    tb = s.get(f"{API}/reports/trial-balance").json()
    assert round(tb["total_debit"], 2) == round(tb["total_credit"], 2), tb


def approved_po(admin, setup, qty=10, rate=100):
    po = admin.post(f"{API}/erp/pos", json={"date": TODAY, "project_id": setup["project"]["id"], "vendor_id": setup["v1"]["id"],
                                          "items": [{"description": "TEST_item", "unit": "nos", "qty": qty, "rate": rate, "gst_rate": 18}]})
    assert po.status_code == 200, po.text
    a = admin.post(f"{API}/erp/pos/{po.json()['id']}/approve")
    assert a.status_code == 200 and a.json()["status"] == "approved"
    return a.json()


# ---------- PR ----------
class TestPR:
    def test_pr_lifecycle(self, admin, setup):
        pid = setup["project"]["id"]
        r = admin.post(f"{API}/erp/prs", json={"project_id": pid, "date": TODAY, "items": items()})
        assert r.status_code == 200, r.text
        pr = r.json()
        assert pr["status"] == "draft" and pr["number"].startswith("PR/") and pr["project_code"] == setup["project"]["code"]
        assert admin.get(f"{API}/erp/prs/{pr['id']}").json()["items"][0]["qty"] == 100
        # cannot approve a draft
        assert admin.post(f"{API}/erp/prs/{pr['id']}/action", json={"action": "approve"}).status_code == 400
        assert admin.post(f"{API}/erp/prs/{pr['id']}/action", json={"action": "submit"}).json()["status"] == "submitted"
        assert admin.delete(f"{API}/erp/prs/{pr['id']}").status_code == 400  # only drafts
        rj = admin.post(f"{API}/erp/prs/{pr['id']}/action", json={"action": "reject", "note": "TEST too much"})
        assert rj.json()["status"] == "rejected"
        # rejected -> edit -> draft -> submit -> approve
        assert admin.put(f"{API}/erp/prs/{pr['id']}", json={"project_id": pid, "date": TODAY, "items": items()}).json()["status"] == "draft"
        admin.post(f"{API}/erp/prs/{pr['id']}/action", json={"action": "submit"})
        assert admin.post(f"{API}/erp/prs/{pr['id']}/action", json={"action": "approve"}).json()["status"] == "approved"
        setup["pr"] = pr
        # draft delete and cancel
        d = admin.post(f"{API}/erp/prs", json={"project_id": pid, "date": TODAY, "items": items()}).json()
        assert admin.delete(f"{API}/erp/prs/{d['id']}").status_code == 200
        assert admin.get(f"{API}/erp/prs/{d['id']}").status_code == 404
        d2 = admin.post(f"{API}/erp/prs", json={"project_id": pid, "date": TODAY, "items": items()}).json()
        assert admin.post(f"{API}/erp/prs/{d2['id']}/cancel", json={"reason": "TEST cancel"}).status_code == 200
        assert admin.get(f"{API}/erp/prs/{d2['id']}").json()["status"] == "cancelled"
        # validation
        assert admin.post(f"{API}/erp/prs", json={"project_id": pid, "date": TODAY, "items": []}).status_code == 422
        assert admin.post(f"{API}/erp/prs", json={"project_id": pid, "date": TODAY, "items": [{"description": "x", "qty": 0}]}).status_code == 422


# ---------- RFQ + comparative + PO ----------
class TestRFQ:
    def test_rfq_compare_select_po(self, admin, setup):
        pid, v1, v2 = setup["project"]["id"], setup["v1"]["id"], setup["v2"]["id"]
        pr = setup.get("pr")
        body = {"project_id": pid, "date": TODAY, "vendor_ids": [v1, v2], "items": items(), **({"pr_id": pr["id"]} if pr else {})}
        r = admin.post(f"{API}/erp/rfqs", json=body)
        assert r.status_code == 200, r.text
        rfq = r.json()
        assert rfq["status"] == "open" and len(rfq["vendors"]) == 2
        if pr:
            assert admin.get(f"{API}/erp/prs/{pr['id']}").json()["status"] == "rfq"
        # client is not a vendor
        assert admin.post(f"{API}/erp/rfqs", json={**body, "vendor_ids": [setup["client"]["id"]], "pr_id": None}).status_code == 400
        # v1: cheaper on item 0, v2 cheaper on item 1 and lower total
        q1 = admin.post(f"{API}/erp/rfqs/{rfq['id']}/quotes", json={"vendor_id": v1, "date": TODAY, "lines": [{"rate": 300}, {"rate": 80}]})
        assert q1.status_code == 200, q1.text
        q2 = admin.post(f"{API}/erp/rfqs/{rfq['id']}/quotes", json={"vendor_id": v2, "date": TODAY, "lines": [{"rate": 320, "discount": 0}, {"rate": 40}]})
        assert q2.status_code == 200
        view = q2.json()
        cmp = view["comparison"]
        assert cmp["rows"][0]["lowest_vendor_id"] == v1 and cmp["rows"][1]["lowest_vendor_id"] == v2
        # totals: v1 = 30000+4000 = 34000*1.18 ; v2 = 32000+2000 = 34000? make v2 lower via discount
        q2 = admin.post(f"{API}/erp/rfqs/{rfq['id']}/quotes", json={"vendor_id": v2, "date": TODAY, "lines": [{"rate": 320, "discount": 10}, {"rate": 40}]}).json()
        cmp = q2["comparison"]
        assert len(q2["quotes"]) == 2  # upsert, not duplicate
        assert cmp["vendors"][0]["vendor_id"] == v2
        lowest = cmp["lowest_quote_id"]
        other = next(q["id"] for q in q2["quotes"] if q["id"] != lowest)
        # wrong line count
        assert admin.post(f"{API}/erp/rfqs/{rfq['id']}/quotes", json={"vendor_id": v1, "date": TODAY, "lines": [{"rate": 1}]}).status_code == 400
        # create-po before select
        assert admin.post(f"{API}/erp/rfqs/{rfq['id']}/create-po").status_code == 400
        # non-lowest needs reason
        assert admin.post(f"{API}/erp/rfqs/{rfq['id']}/select", json={"quote_id": other}).status_code == 400
        s = admin.post(f"{API}/erp/rfqs/{rfq['id']}/select", json={"quote_id": other, "reason": "TEST better delivery"})
        assert s.status_code == 200 and s.json()["status"] == "selected" and s.json()["lowest"] is False
        s = admin.post(f"{API}/erp/rfqs/{rfq['id']}/select", json={"quote_id": lowest})
        assert s.status_code == 200 and s.json()["selected_vendor_id"] == v2
        # quotes locked after selection
        assert admin.post(f"{API}/erp/rfqs/{rfq['id']}/quotes", json={"vendor_id": v1, "date": TODAY, "lines": [{"rate": 1}, {"rate": 1}]}).status_code == 400
        # send: v1 has email
        snd = admin.post(f"{API}/erp/rfqs/{rfq['id']}/send")
        assert snd.status_code in (200, 503), snd.text
        po = admin.post(f"{API}/erp/rfqs/{rfq['id']}/create-po")
        assert po.status_code == 200, po.text
        po = po.json()
        assert po["status"] == "draft" and po["vendor_id"] == v2 and po["number"].startswith("PO/")
        assert po["items"][0]["discount"] == 10 and po["totals"]["total"] == q2["quotes"][0]["totals"]["total"]
        r2 = admin.get(f"{API}/erp/rfqs/{rfq['id']}").json()
        assert r2["status"] == "ordered" and r2["po_number"] == po["number"]
        assert admin.post(f"{API}/erp/rfqs/{rfq['id']}/create-po").status_code == 400
        assert admin.post(f"{API}/erp/rfqs/{rfq['id']}/cancel", json={"reason": "TEST x"}).status_code == 400

    def test_send_no_email(self, admin, setup):
        r = admin.post(f"{API}/erp/rfqs", json={"project_id": setup["project"]["id"], "date": TODAY, "vendor_ids": [setup["v2"]["id"]], "items": items()}).json()
        s = admin.post(f"{API}/erp/rfqs/{r['id']}/send")
        assert s.status_code == 400 and "email" in s.json()["detail"]
        assert admin.post(f"{API}/erp/rfqs/{r['id']}/cancel", json={"reason": "TEST cancel"}).status_code == 200


# ---------- PO / GRN ----------
class TestPOGRN:
    def test_po_crud_and_actions(self, admin, setup):
        po = admin.post(f"{API}/erp/pos", json={"date": TODAY, "project_id": setup["project"]["id"], "vendor_id": setup["v1"]["id"], "template": "modern",
                                               "items": [{"description": "TEST_A", "qty": 2, "rate": 1000, "gst_rate": 18}]})
        assert po.status_code == 200, po.text
        po = po.json()
        assert po["totals"]["total"] == 2360 and po["template"] == "modern"
        u = admin.put(f"{API}/erp/pos/{po['id']}", json={"date": TODAY, "project_id": setup["project"]["id"], "vendor_id": setup["v1"]["id"],
                                                         "items": [{"description": "TEST_A", "qty": 3, "rate": 1000, "gst_rate": 18}]})
        assert u.status_code == 200 and u.json()["totals"]["total"] == 3540
        assert admin.get(f"{API}/erp/pos/{po['id']}").json()["items"][0]["qty"] == 3
        # client as vendor rejected
        assert admin.post(f"{API}/erp/pos", json={"date": TODAY, "project_id": setup["project"]["id"], "vendor_id": setup["client"]["id"],
                                                 "items": [{"description": "x", "qty": 1, "rate": 1}]}).status_code == 400
        # GRN on draft PO not allowed
        assert admin.post(f"{API}/erp/grns", json={"po_id": po["id"], "date": TODAY, "lines": [{"line": 0, "received": 1, "accepted": 1}]}).status_code == 400
        assert admin.post(f"{API}/erp/pos/{po['id']}/approve").json()["status"] == "approved"
        assert admin.put(f"{API}/erp/pos/{po['id']}", json={"date": TODAY, "project_id": setup["project"]["id"], "vendor_id": setup["v1"]["id"],
                                                            "items": [{"description": "x", "qty": 1, "rate": 1}]}).status_code == 400
        dup = admin.post(f"{API}/erp/pos/{po['id']}/duplicate")
        assert dup.status_code == 200 and dup.json()["status"] == "draft" and dup.json()["number"] != po["number"] and dup.json()["totals"]["total"] == 3540
        assert admin.delete(f"{API}/erp/pos/{dup.json()['id']}").status_code == 200
        assert admin.post(f"{API}/erp/pos/{po['id']}/cancel", json={"reason": "TEST cancel"}).status_code == 200

    def test_grn_partial_full_cancel(self, admin, setup):
        po = approved_po(admin, setup, qty=10)
        # over pending
        r = admin.post(f"{API}/erp/grns", json={"po_id": po["id"], "date": TODAY, "lines": [{"line": 0, "received": 11, "accepted": 11}]})
        assert r.status_code == 400
        # accepted+rejected != received
        assert admin.post(f"{API}/erp/grns", json={"po_id": po["id"], "date": TODAY, "lines": [{"line": 0, "received": 5, "accepted": 3, "rejected": 1}]}).status_code == 400
        g1 = admin.post(f"{API}/erp/grns", json={"po_id": po["id"], "date": TODAY, "challan_no": "TEST_CH1", "lines": [{"line": 0, "received": 5, "accepted": 4, "rejected": 1}]})
        assert g1.status_code == 200, g1.text
        g1 = g1.json()
        assert g1["number"].startswith("GRN/") and g1["accepted_value"] == 400
        v = admin.get(f"{API}/erp/pos/{po['id']}").json()
        assert v["items"][0]["accepted"] == 4 and v["items"][0]["pending"] == 6 and v["items"][0]["rejected"] == 1 and v["receipt_status"] == "partial"
        assert any(x["id"] == po["id"] for x in admin.get(f"{API}/erp/pos?pending=true").json())
        assert admin.post(f"{API}/erp/pos/{po['id']}/cancel", json={"reason": "TEST"}).status_code == 400  # blocked after receipt
        g2 = admin.post(f"{API}/erp/grns", json={"po_id": po["id"], "date": TODAY, "lines": [{"line": 0, "received": 6, "accepted": 6}]}).json()
        assert admin.get(f"{API}/erp/pos/{po['id']}").json()["receipt_status"] == "received"
        assert any(g["id"] == g1["id"] for g in admin.get(f"{API}/erp/grns", params={"po_id": po["id"]}).json())
        assert admin.post(f"{API}/erp/grns/{g2['id']}/cancel", json={"reason": "TEST wrong"}).status_code == 200
        v = admin.get(f"{API}/erp/pos/{po['id']}").json()
        assert v["items"][0]["pending"] == 6 and v["receipt_status"] == "partial"
        assert admin.post(f"{API}/erp/grns/{g2['id']}/cancel", json={"reason": "TEST again"}).status_code == 400
        assert admin.post(f"{API}/erp/pos/{po['id']}/close").json()["status"] == "closed"
        # GRN on closed PO
        assert admin.post(f"{API}/erp/grns", json={"po_id": po["id"], "date": TODAY, "lines": [{"line": 0, "received": 1, "accepted": 1}]}).status_code == 400


# ---------- Bills ----------
class TestBills:
    def test_bill_post_pay_cancel(self, admin, setup):
        po = approved_po(admin, setup, qty=10, rate=100)
        g = admin.post(f"{API}/erp/grns", json={"po_id": po["id"], "date": TODAY, "lines": [{"line": 0, "received": 6, "accepted": 6}]}).json()
        vinv = f"TEST_VI_{uuid.uuid4().hex[:5]}"
        base = {"vendor_id": setup["v1"]["id"], "project_id": setup["project"]["id"], "po_id": po["id"], "grn_ids": [g["id"]],
                "vendor_invoice_no": vinv, "vendor_invoice_date": TODAY}
        line = lambda q: [{"description": "TEST_item", "qty": q, "rate": 100, "gst_rate": 18, "po_line": 0}]
        assert admin.post(f"{API}/erp/bills", json={**base, "items": line(7)}).status_code == 400  # > accepted
        assert admin.post(f"{API}/erp/bills", json={**base, "vendor_invoice_no": "", "items": line(1)}).status_code == 400
        r = admin.post(f"{API}/erp/bills", json={**base, "items": line(6)})
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["status"] == "draft" and b["totals"]["total"] == 708 and b["po_number"] == po["number"]
        # duplicate vendor invoice no (case-insensitive) for same vendor
        dup = admin.post(f"{API}/erp/bills", json={**base, "vendor_invoice_no": vinv.lower(), "po_id": None, "grn_ids": [], "items": line(1)})
        assert dup.status_code == 400 and "already" in dup.json()["detail"]
        # draft counts toward billed limit
        assert admin.post(f"{API}/erp/bills", json={**base, "vendor_invoice_no": vinv + "b", "items": line(1)}).status_code == 400
        tb_ok(admin)
        p = admin.post(f"{API}/erp/bills/{b['id']}/post")
        assert p.status_code == 200, p.text
        p = p.json()
        assert p["status"] == "posted" and p["voucher_no"] and p["pay_status"] == "unpaid" and p["balance"] == 708
        vch = admin.get(f"{API}/vouchers/{p['voucher_id']}")
        assert vch.status_code == 200 and vch.json()["voucher_type"] == "purchase" and abs(vch.json().get("total", 708) - 708) < 0.01
        assert admin.get(f"{API}/erp/pos/{po['id']}").json()["items"][0]["billed_qty"] == 6
        tb_ok(admin)
        cash = ledger(admin, "cash")
        assert admin.post(f"{API}/erp/bills/{b['id']}/payments", json={"date": TODAY, "amount": 800, "ledger_id": cash}).status_code == 400
        assert admin.post(f"{API}/erp/bills/{b['id']}/payments", json={"date": TODAY, "amount": 10, "ledger_id": ledger(admin, "purchase")}).status_code == 400
        pay = admin.post(f"{API}/erp/bills/{b['id']}/payments", json={"date": TODAY, "amount": 300, "ledger_id": cash, "reference": "TEST_ref"})
        assert pay.status_code == 200, pay.text
        assert pay.json()["pay_status"] == "partial" and pay.json()["balance"] == 408
        tb_ok(admin)
        # GRN cannot be cancelled once billed
        assert admin.post(f"{API}/erp/grns/{g['id']}/cancel", json={"reason": "TEST"}).status_code == 400
        assert admin.post(f"{API}/erp/bills/{b['id']}/cancel", json={"reason": "TEST"}).status_code == 400  # has payments
        assert any(x["id"] == b["id"] for x in admin.get(f"{API}/erp/bills?pending=true").json())

    def test_bill_cancel_reverses_voucher(self, admin, setup):
        po = approved_po(admin, setup, qty=5, rate=200)
        admin.post(f"{API}/erp/grns", json={"po_id": po["id"], "date": TODAY, "lines": [{"line": 0, "received": 5, "accepted": 5}]})
        b = admin.post(f"{API}/erp/bills", json={"vendor_id": setup["v1"]["id"], "project_id": setup["project"]["id"], "po_id": po["id"],
                                                "vendor_invoice_no": f"TEST_VC_{U}", "vendor_invoice_date": TODAY,
                                                "items": [{"description": "TEST_item", "qty": 5, "rate": 200, "gst_rate": 18, "po_line": 0}]}).json()
        p = admin.post(f"{API}/erp/bills/{b['id']}/post").json()
        assert admin.post(f"{API}/erp/bills/{b['id']}/post").status_code == 400
        c = admin.post(f"{API}/erp/bills/{b['id']}/cancel", json={"reason": "TEST wrong bill"})
        assert c.status_code == 200, c.text
        assert admin.get(f"{API}/erp/bills/{b['id']}").json()["status"] == "cancelled"
        vch = admin.get(f"{API}/vouchers/{p['voucher_id']}").json()
        assert vch.get("status") == "cancelled" or vch.get("cancelled") is True, vch
        tb_ok(admin)
        # after cancel, same vendor invoice no can be reused and qty is free again
        b2 = admin.post(f"{API}/erp/bills", json={"vendor_id": setup["v1"]["id"], "project_id": setup["project"]["id"], "po_id": po["id"],
                                                 "vendor_invoice_no": f"TEST_VC_{U}", "vendor_invoice_date": TODAY,
                                                 "items": [{"description": "TEST_item", "qty": 5, "rate": 200, "gst_rate": 18, "po_line": 0}]})
        assert b2.status_code == 200, b2.text
        assert admin.delete(f"{API}/erp/bills/{b2.json()['id']}").status_code == 200


# ---------- Expenses ----------
class TestExpenses:
    def test_expense_flow(self, admin, setup):
        cats = admin.get(f"{API}/erp/expense-categories").json()
        assert "Labour" in cats
        cash = ledger(admin, "cash")
        body = {"project_id": setup["project"]["id"], "date": TODAY, "category": "Transport", "paid_to": f"TEST_driver_{U}", "amount": 1000,
                "gst_rate": 5, "payment_ledger_id": cash}
        r = admin.post(f"{API}/erp/expenses", json=body)
        assert r.status_code == 200, r.text
        e = r.json()
        assert e["status"] == "draft" and e["totals"]["total"] == 1050 and e["number"].startswith("EXP/")
        assert admin.post(f"{API}/erp/expenses", json={**body, "amount": 0}).status_code == 422
        assert admin.post(f"{API}/erp/expenses", json={**body, "payment_ledger_id": ledger(admin, "purchase")}).status_code == 400
        u = admin.put(f"{API}/erp/expenses/{e['id']}", json={**body, "amount": 2000})
        assert u.status_code == 200 and u.json()["totals"]["total"] == 2100
        p = admin.post(f"{API}/erp/expenses/{e['id']}/post")
        assert p.status_code == 200, p.text
        assert p.json()["status"] == "posted" and p.json()["voucher_no"]
        tb_ok(admin)
        lst = admin.get(f"{API}/erp/expenses", params={"category": "Transport", "project_id": setup["project"]["id"]}).json()
        assert any(x["id"] == e["id"] for x in lst)
        assert admin.put(f"{API}/erp/expenses/{e['id']}", json=body).status_code == 400
        assert admin.delete(f"{API}/erp/expenses/{e['id']}").status_code == 400
        c = admin.post(f"{API}/erp/expenses/{e['id']}/cancel", json={"reason": "TEST cancel"})
        assert c.status_code == 200, c.text
        tb_ok(admin)
        assert admin.get(f"{API}/erp/expense-documents").status_code == 200
        d = admin.post(f"{API}/erp/expenses", json=body).json()
        assert admin.delete(f"{API}/erp/expenses/{d['id']}").status_code == 200


# ---------- Permissions ----------
class TestPermissions:
    def test_viewer_and_data_entry(self, admin, setup):
        users = {}
        for role in ("viewer", "data_entry"):
            email = f"test_{role}_b_{U}@example.com"
            r = admin.post(f"{API}/users", json={"name": f"TEST {role}", "email": email, "password": "secret1", "role": role})
            assert r.status_code == 200, r.text
            users[role] = (r.json()["id"], login(email, "secret1"))
        try:
            vw, de = users["viewer"][1], users["data_entry"][1]
            pid = setup["project"]["id"]
            assert vw.get(f"{API}/erp/prs").status_code == 200
            assert vw.get(f"{API}/erp/pos").status_code == 200
            assert vw.post(f"{API}/erp/prs", json={"project_id": pid, "date": TODAY, "items": items()}).status_code == 403
            assert vw.post(f"{API}/erp/pos", json={"date": TODAY, "project_id": pid, "vendor_id": setup["v1"]["id"],
                                                  "items": [{"description": "x", "qty": 1, "rate": 1}]}).status_code == 403
            assert vw.post(f"{API}/erp/expenses", json={"project_id": pid, "date": TODAY, "category": "Fuel", "paid_to": "x", "amount": 1,
                                                       "payment_ledger_id": ledger(admin, "cash")}).status_code == 403
            pr = de.post(f"{API}/erp/prs", json={"project_id": pid, "date": TODAY, "items": items()})
            assert pr.status_code == 200, pr.text
            assert de.post(f"{API}/erp/prs/{pr.json()['id']}/action", json={"action": "submit"}).status_code == 200
            assert de.post(f"{API}/erp/prs/{pr.json()['id']}/action", json={"action": "approve"}).status_code == 403
            assert vw.post(f"{API}/erp/prs/{pr.json()['id']}/action", json={"action": "approve"}).status_code == 403
            po = de.post(f"{API}/erp/pos", json={"date": TODAY, "project_id": pid, "vendor_id": setup["v1"]["id"], "items": [{"description": "x", "qty": 1, "rate": 1}]})
            assert po.status_code == 200
            assert de.post(f"{API}/erp/pos/{po.json()['id']}/approve").status_code == 403
            admin.delete(f"{API}/erp/pos/{po.json()['id']}")
        finally:
            for uid, _ in users.values():
                admin.put(f"{API}/users/{uid}", json={"active": False})

    def test_trial_balance(self, admin):
        tb_ok(admin)
