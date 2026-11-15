# Round 9 ERP Phase A: gating, parties, projects, quotations, invoices, payments, notes, permissions, regression
import os
import uuid
from datetime import date, timedelta

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


def line(desc="TEST_work", qty=1, rate=10000, disc=0, gst=18):
    return {"description": desc, "hsn": "9954", "unit": "nos", "qty": qty, "rate": rate, "discount": disc, "gst_rate": gst}


def mk_party(s, kind="client", **kw):
    body = {"kind": kind, "company_name": f"TEST_{kind}_{uuid.uuid4().hex[:6]}", "state": "", **kw}
    r = s.post(f"{API}/erp/parties", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def mk_project(s, client_id, **kw):
    r = s.post(f"{API}/erp/projects", json={"name": f"TEST_proj_{uuid.uuid4().hex[:5]}", "client_id": client_id, "contract_value": 500000, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def mk_invoice(s, cid, pid, items=None, **kw):
    r = s.post(f"{API}/erp/invoices", json={"date": TODAY, "client_id": cid, "project_id": pid, "items": items or [line()], **kw})
    assert r.status_code == 200, r.text
    return r.json()


def cash_ledger(s):
    return next(l["id"] for l in s.get(f"{API}/ledgers").json() if l["group"] == "cash")


# ---------- gating ----------
class TestGating:
    def test_no_erp_business_402(self):
        s = login("ravi@gupta.in", "secret1")
        st = s.get(f"{API}/erp/status")
        assert st.status_code == 200 and st.json()["active"] is False
        for path in ("/erp/dashboard", "/erp/parties", "/erp/projects", "/erp/invoices", "/erp/settings"):
            assert s.get(f"{API}{path}").status_code == 402, path

    def test_superadmin_grant_and_inter_state_igst(self, admin):
        r = requests.post(f"{API}/auth/signup", json={"business_name": f"TEST_ERP_Biz_{U}", "name": "TEST Owner", "email": f"test_erp_{U}@example.com",
                                                      "password": "secret1", "phone": "", "state": "Maharashtra", "gstin": ""})
        assert r.status_code == 200, r.text
        s = requests.Session()
        s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
        assert s.get(f"{API}/erp/parties").status_code == 402
        bid = r.json()["user"]["business_id"]
        # non-superadmin cannot grant
        assert s.post(f"{API}/erp/platform/{bid}/grant", json={"days": 365}).status_code == 403
        g = admin.post(f"{API}/erp/platform/{bid}/grant", json={"days": 365})
        assert g.status_code == 200 and g.json()["erp_ends"] > TODAY
        assert s.get(f"{API}/erp/status").json()["active"] is True
        # inter-state client -> IGST
        c = mk_party(s, state="Karnataka")
        p = mk_project(s, c["id"])
        inv = mk_invoice(s, c["id"], p["id"])
        assert inv["gst_type"] == "inter"
        assert inv["totals"]["igst"] == 1800 and inv["totals"]["cgst"] == 0
        c2 = mk_party(s, state="Maharashtra")
        p2 = mk_project(s, c2["id"])
        inv2 = mk_invoice(s, c2["id"], p2["id"])
        assert inv2["gst_type"] == "intra" and inv2["totals"]["cgst"] == 900 and inv2["totals"]["sgst"] == 900
        fin = s.post(f"{API}/erp/invoices/{inv['id']}/finalize")
        assert fin.status_code == 200, fin.text
        v = s.get(f"{API}/vouchers/{fin.json()['voucher_id']}").json()
        assert v.get("gst_type") == "inter"


# ---------- parties ----------
class TestParties:
    def test_validation_and_ledger(self, admin):
        bad = admin.post(f"{API}/erp/parties", json={"kind": "client", "company_name": f"TEST_bad_{U}", "gstin": "12345"})
        assert bad.status_code == 400 and "GSTIN" in bad.json()["detail"]
        bad = admin.post(f"{API}/erp/parties", json={"kind": "client", "company_name": f"TEST_bad_{U}", "pan": "ABC"})
        assert bad.status_code == 400 and "PAN" in bad.json()["detail"]
        c = mk_party(admin, gstin="27abcde1234f1z5", pan="abcde1234f", opening_balance=1000)
        assert c["gstin"] == "27ABCDE1234F1Z5" and c["pan"] == "ABCDE1234F"
        dup = admin.post(f"{API}/erp/parties", json={"kind": "client", "company_name": c["company_name"].lower()})
        assert dup.status_code == 400
        v = mk_party(admin, "vendor")
        leds = {l["id"]: l for l in admin.get(f"{API}/ledgers").json()}
        assert leds[c["ledger_id"]]["group"] == "sundry_debtors"
        assert leds[v["ledger_id"]]["group"] == "sundry_creditors"
        # update
        u = admin.put(f"{API}/erp/parties/{c['id']}", json={"kind": "client", "company_name": c["company_name"], "mobile": "9999999999", "state": "Goa"})
        assert u.status_code == 200 and u.json()["mobile"] == "9999999999"
        assert admin.get(f"{API}/erp/parties/{c['id']}").json()["state"] == "Goa"
        # delete blocked when used, allowed when unused
        mk_project(admin, c["id"])
        assert admin.delete(f"{API}/erp/parties/{c['id']}").status_code == 400
        assert admin.delete(f"{API}/erp/parties/{v['id']}").status_code == 200
        assert all(p["id"] != v["id"] for p in admin.get(f"{API}/erp/parties?kind=vendor").json())


# ---------- projects ----------
class TestProjects:
    def test_codes_update_dashboard(self, admin):
        c = mk_party(admin)
        p = mk_project(admin, c["id"])
        assert p["code"].startswith("PRJ-") and len(p["code"]) == 8
        code = f"TST{U}".upper()
        m = mk_project(admin, c["id"], code=code.lower())
        assert m["code"] == code
        dup = admin.post(f"{API}/erp/projects", json={"name": "TEST_x", "client_id": c["id"], "code": code})
        assert dup.status_code == 400
        inv = mk_invoice(admin, c["id"], m["id"])
        upd = admin.put(f"{API}/erp/projects/{m['id']}", json={"name": "TEST_Renamed", "client_id": c["id"], "code": code, "contract_value": 500000,
                                                              "status": "Running", "progress": 40})
        assert upd.status_code == 200 and upd.json()["status"] == "Running"
        assert admin.get(f"{API}/erp/invoices/{inv['id']}").json()["project_name"] == "TEST_Renamed"
        assert admin.delete(f"{API}/erp/projects/{m['id']}").status_code == 400
        # dashboard numbers
        i2 = mk_invoice(admin, c["id"], m["id"], items=[line(rate=20000)])
        for i in (inv, i2):
            assert admin.post(f"{API}/erp/invoices/{i['id']}/finalize").status_code == 200
        admin.post(f"{API}/erp/invoices/{inv['id']}/payments", json={"date": TODAY, "amount": 5000, "ledger_id": cash_ledger(admin)})
        d = admin.get(f"{API}/erp/projects/{m['id']}").json()
        n = d["numbers"]
        assert n["billed"] == 11800 + 23600
        assert n["received"] == 5000
        bal = sum(i["balance"] for i in admin.get(f"{API}/erp/invoices?project_id={m['id']}").json() if i["status"] == "finalized")
        assert n["outstanding"] == bal == 30400
        assert n["balance_to_bill"] == 500000 - 30000
        assert n["profit"] == 30000
        # empty project deletable
        assert admin.delete(f"{API}/erp/projects/{p['id']}").status_code == 200


# ---------- quotations ----------
class TestQuotations:
    def test_quote_lifecycle(self, admin):
        c = mk_party(admin)
        p = mk_project(admin, c["id"])
        body = {"date": TODAY, "valid_until": (date.today() + timedelta(days=15)).isoformat(), "client_id": c["id"], "project_id": p["id"],
                "items": [line(qty=2, rate=1000, disc=10)], "subject": "TEST_quote"}
        q = admin.post(f"{API}/erp/quotations", json=body).json()
        assert q["number"].startswith("QT/") and q["status"] == "draft"
        assert q["totals"]["taxable"] == 1800 and q["totals"]["total"] == 2124
        e = admin.put(f"{API}/erp/quotations/{q['id']}", json={**body, "items": [line(qty=3, rate=1000)]})
        assert e.status_code == 200 and e.json()["totals"]["taxable"] == 3000 and e.json()["number"] == q["number"]
        assert admin.post(f"{API}/erp/quotations/{q['id']}/status", json={"status": "sent"}).json()["status"] == "sent"
        assert admin.post(f"{API}/erp/quotations/{q['id']}/status", json={"status": "accepted"}).json()["status"] == "accepted"
        assert admin.delete(f"{API}/erp/quotations/{q['id']}").status_code == 400
        # convert to sales order then invoice
        so = admin.post(f"{API}/erp/quotations/{q['id']}/convert", json={"to": "sales_order"})
        assert so.status_code == 200 and so.json()["sales_order_no"].startswith("SO/")
        ci = admin.post(f"{API}/erp/quotations/{q['id']}/convert", json={"to": "invoice"})
        assert ci.status_code == 200
        inv = admin.get(f"{API}/erp/invoices/{ci.json()['invoice_id']}").json()
        assert inv["status"] == "draft" and inv["number"] is None and inv["totals"]["taxable"] == 3000 and inv["project_id"] == p["id"]
        assert admin.get(f"{API}/erp/quotations/{q['id']}").json()["status"] == "converted"
        # duplicate gets new number, is draft and is not pre-linked to old sales order
        d = admin.post(f"{API}/erp/quotations/{q['id']}/duplicate").json()
        assert d["number"] != q["number"] and d["status"] == "draft"
        assert not d.get("sales_order_no"), f"duplicate copied sales_order_no {d.get('sales_order_no')}"

    def test_cancel_delete_expire_convert_project(self, admin):
        c = mk_party(admin)
        body = {"date": TODAY, "client_id": c["id"], "items": [line()]}
        q = admin.post(f"{API}/erp/quotations", json=body).json()
        assert admin.post(f"{API}/erp/quotations/{q['id']}/cancel", json={"reason": ""}).status_code == 422
        assert admin.post(f"{API}/erp/quotations/{q['id']}/cancel", json={"reason": "TEST cancel"}).status_code == 200
        assert admin.get(f"{API}/erp/quotations/{q['id']}").json()["status"] == "cancelled"
        q2 = admin.post(f"{API}/erp/quotations", json=body).json()
        assert admin.delete(f"{API}/erp/quotations/{q2['id']}").status_code == 200
        assert admin.get(f"{API}/erp/quotations/{q2['id']}").status_code == 404
        # expired
        past = (date.today() - timedelta(days=40)).isoformat()
        q3 = admin.post(f"{API}/erp/quotations", json={**body, "date": past, "valid_until": (date.today() - timedelta(days=1)).isoformat()}).json()
        assert admin.post(f"{API}/erp/quotations/{q3['id']}/status", json={"status": "sent"}).json()["status"] == "expired"
        assert any(x["id"] == q3["id"] for x in admin.get(f"{API}/erp/quotations?status=expired").json())
        # convert to project
        assert admin.post(f"{API}/erp/quotations/{q3['id']}/convert", json={"to": "project"}).status_code == 400
        admin.post(f"{API}/erp/quotations/{q3['id']}/status", json={"status": "accepted"})
        cp = admin.post(f"{API}/erp/quotations/{q3['id']}/convert", json={"to": "project", "project_name": "TEST_conv_proj"})
        assert cp.status_code == 200
        pr = admin.get(f"{API}/erp/projects/{cp.json()['project_id']}").json()
        assert pr["name"] == "TEST_conv_proj" and pr["contract_value"] == 10000


# ---------- invoices ----------
class TestInvoices:
    def test_finalize_voucher_billing_math(self, admin):
        c = mk_party(admin, email="delivered@resend.dev")
        p = mk_project(admin, c["id"])
        i1 = mk_invoice(admin, c["id"], p["id"], items=[line(qty=2, rate=50000)], retention_pct=5, advance_adjust=10000, deductions=1000)
        assert i1["number"] is None
        t = i1["totals"]
        assert t["total"] == 118000 and t["retention"] == 5900 and t["net_payable"] == 118000 - 5900 - 10000 - 1000
        f1 = admin.post(f"{API}/erp/invoices/{i1['id']}/finalize").json()
        assert f1["number"].startswith("INV/") and f1["status"] == "finalized" and f1["balance"] == t["net_payable"]
        v = admin.get(f"{API}/vouchers/{f1['voucher_id']}").json()
        assert v["voucher_type"] == "sales" and v["party_ledger_id"] == c["ledger_id"]
        vt = v.get("total") or v.get("grand_total") or v.get("totals", {}).get("total")
        assert round(float(vt), 2) == 118000, v.keys()
        assert admin.post(f"{API}/erp/invoices/{i1['id']}/finalize").status_code == 400
        assert admin.delete(f"{API}/erp/invoices/{i1['id']}").status_code == 400
        # second invoice previous/cumulative
        i2 = mk_invoice(admin, c["id"], p["id"], items=[line(rate=10000)])
        assert i2["billing"]["previous"] == 118000 and i2["billing"]["cumulative"] == 129800
        # email (single)
        em = admin.post(f"{API}/erp/invoices/{i1['id']}/email")
        assert em.status_code == 200 and em.json()["to"] == "delivered@resend.dev"
        # payments partial, full, overpay
        cash = cash_ledger(admin)
        assert admin.post(f"{API}/erp/invoices/{i1['id']}/payments", json={"date": TODAY, "amount": 999999, "ledger_id": cash}).status_code == 400
        pp = admin.post(f"{API}/erp/invoices/{i1['id']}/payments", json={"date": TODAY, "amount": 50000, "ledger_id": cash}).json()
        assert pp["pay_status"] == "partial" and pp["balance"] == t["net_payable"] - 50000
        rv = admin.get(f"{API}/vouchers/{pp['payments'][0]['voucher_id']}").json()
        assert rv["voucher_type"] == "receipt"
        # cancel blocked with payments
        assert admin.post(f"{API}/erp/invoices/{i1['id']}/cancel", json={"reason": "TEST reason"}).status_code == 400
        # credit note / debit note
        cn = admin.post(f"{API}/erp/invoices/{i1['id']}/notes", json={"kind": "credit", "date": TODAY, "reason": "TEST short", "items": [line(rate=1000)]})
        assert cn.status_code == 200 and cn.json()["number"].startswith("ECN/")
        assert admin.get(f"{API}/vouchers/{cn.json()['voucher_id']}").json()["voucher_type"] == "credit_note"
        dn = admin.post(f"{API}/erp/invoices/{i1['id']}/notes", json={"kind": "debit", "date": TODAY, "reason": "TEST extra", "items": [line(rate=500)]})
        dn_ok = dn.status_code == 200
        assert dn_ok and dn.json()["number"].startswith("EDN/"), dn.text
        assert admin.get(f"{API}/vouchers/{dn.json()['voucher_id']}").json()["voucher_type"] == "sales"
        g = admin.get(f"{API}/erp/invoices/{i1['id']}").json()
        assert g["balance"] == round(t["net_payable"] - 50000 - 1180 + (590 if dn_ok else 0), 2)
        full = admin.post(f"{API}/erp/invoices/{i1['id']}/payments", json={"date": TODAY, "amount": g["balance"], "ledger_id": cash}).json()
        assert full["pay_status"] == "paid" and full["balance"] == 0
        assert dn_ok, f"Debit note failed: {dn.text}"

    def test_numbers_edit_cancel_duplicate_overdue(self, admin):
        c = mk_party(admin)
        p = mk_project(admin, c["id"])
        num = f"TEST-INV-{U}"
        a = mk_invoice(admin, c["id"], p["id"], number=num)
        assert admin.post(f"{API}/erp/invoices", json={"date": TODAY, "client_id": c["id"], "project_id": p["id"], "items": [line()], "number": num}).status_code in (200, 400)
        fa = admin.post(f"{API}/erp/invoices/{a['id']}/finalize").json()
        assert fa["number"] == num
        assert admin.post(f"{API}/erp/invoices", json={"date": TODAY, "client_id": c["id"], "project_id": p["id"], "items": [line()], "number": num}).status_code == 400
        # edit finalized -> version + voucher updated
        e = admin.put(f"{API}/erp/invoices/{a['id']}", json={"date": TODAY, "client_id": c["id"], "project_id": p["id"], "items": [line(rate=20000)]})
        assert e.status_code == 200, e.text
        g = admin.get(f"{API}/erp/invoices/{a['id']}").json()
        assert len(g["versions"]) == 1 and g["totals"]["total"] == 23600 and g["number"] == num
        v = admin.get(f"{API}/vouchers/{g['voucher_id']}").json()
        vt = v.get("total") or v.get("grand_total") or v.get("totals", {}).get("total")
        assert round(float(vt), 2) == 23600
        # cancel requires reason, cancels voucher, number never reused
        assert admin.post(f"{API}/erp/invoices/{a['id']}/cancel", json={"reason": ""}).status_code == 422
        assert admin.post(f"{API}/erp/invoices/{a['id']}/cancel", json={"reason": "TEST wrong"}).status_code == 200
        assert admin.get(f"{API}/vouchers/{g['voucher_id']}").json()["status"] == "cancelled"
        assert admin.get(f"{API}/erp/invoices/{a['id']}").json()["status"] == "cancelled"
        assert admin.put(f"{API}/erp/invoices/{a['id']}", json={"date": TODAY, "client_id": c["id"], "project_id": p["id"], "items": [line()]}).status_code == 400
        assert admin.post(f"{API}/erp/invoices", json={"date": TODAY, "client_id": c["id"], "project_id": p["id"], "items": [line()], "number": num}).status_code == 400
        # duplicate -> draft
        d = admin.post(f"{API}/erp/invoices/{a['id']}/duplicate").json()
        assert d["status"] == "draft" and d["number"] is None and d["totals"]["total"] == 23600
        assert admin.delete(f"{API}/erp/invoices/{d['id']}").status_code == 200
        assert admin.get(f"{API}/erp/invoices/{d['id']}").status_code == 404
        # overdue
        past = (date.today() - timedelta(days=10)).isoformat()
        o = mk_invoice(admin, c["id"], p["id"], due_date=past)
        admin.post(f"{API}/erp/invoices/{o['id']}/finalize")
        assert any(x["id"] == o["id"] for x in admin.get(f"{API}/erp/invoices?overdue=true").json())
        # net negative rejected
        bad = admin.post(f"{API}/erp/invoices", json={"date": TODAY, "client_id": c["id"], "project_id": p["id"], "items": [line()], "advance_adjust": 999999})
        assert bad.status_code == 400


# ---------- permissions ----------
class TestPermissions:
    def test_roles(self, admin):
        users = {}
        for role in ("viewer", "data_entry", "project_manager", "accountant"):
            email = f"test_{role}_{U}@example.com"
            r = admin.post(f"{API}/users", json={"name": f"TEST {role}", "email": email, "password": "secret1", "role": role})
            assert r.status_code == 200, r.text
            users[role] = (r.json()["id"], login(email, "secret1"))
        try:
            vw, de, pm, ac = (users[r][1] for r in ("viewer", "data_entry", "project_manager", "accountant"))
            c = mk_party(admin)
            p = mk_project(admin, c["id"])
            assert vw.get(f"{API}/erp/projects").status_code == 200
            assert vw.post(f"{API}/erp/parties", json={"kind": "client", "company_name": f"TEST_v_{U}"}).status_code == 403
            inv = mk_invoice(de, c["id"], p["id"])
            assert de.post(f"{API}/erp/invoices/{inv['id']}/finalize").status_code == 403
            q = de.post(f"{API}/erp/quotations", json={"date": TODAY, "client_id": c["id"], "items": [line()]}).json()
            assert de.post(f"{API}/erp/quotations/{q['id']}/status", json={"status": "accepted"}).status_code == 403
            assert de.post(f"{API}/erp/quotations/{q['id']}/cancel", json={"reason": "TEST no"}).status_code == 403
            assert pm.post(f"{API}/erp/quotations/{q['id']}/status", json={"status": "accepted"}).json()["status"] == "accepted"
            assert pm.post(f"{API}/erp/invoices/{inv['id']}/finalize").status_code == 403
            f = ac.post(f"{API}/erp/invoices/{inv['id']}/finalize")
            assert f.status_code == 200, f.text
            assert ac.put(f"{API}/erp/invoices/{inv['id']}", json={"date": TODAY, "client_id": c["id"], "project_id": p["id"], "items": [line(rate=5)]}).status_code == 403
            assert ac.post(f"{API}/erp/invoices/{inv['id']}/cancel", json={"reason": "TEST acc cancel"}).status_code == 200
            # new roles cannot create vouchers directly
            for s in (pm, de, vw):
                assert s.post(f"{API}/vouchers", json={"voucher_type": "receipt", "date": TODAY, "entries": []}).status_code == 403
            # permission matrix change takes effect
            st = admin.get(f"{API}/erp/settings").json()
            orig = {k: st[k] for k in ("industry", "quotation_prefix", "invoice_prefix", "default_quote_template", "default_invoice_template",
                                       "authorized_signatory", "quote_terms", "permissions")}
            perms = {**orig["permissions"], "finalize": ["admin", "accountant", "data_entry"]}
            try:
                r = admin.put(f"{API}/erp/settings", json={**orig, "permissions": perms})
                assert r.status_code == 200 and "data_entry" in r.json()["permissions"]["finalize"]
                assert ac.put(f"{API}/erp/settings", json={**orig, "permissions": perms}).status_code == 403
                inv2 = mk_invoice(de, c["id"], p["id"])
                assert de.post(f"{API}/erp/invoices/{inv2['id']}/finalize").status_code == 200
            finally:
                admin.put(f"{API}/erp/settings", json=orig)
        finally:
            for uid, _ in users.values():
                admin.put(f"{API}/users/{uid}", json={"active": False})


# ---------- regression ----------
class TestRegression:
    def test_trial_balance_and_backup(self, admin):
        tb = admin.get(f"{API}/reports/trial-balance").json()
        assert round(tb["total_debit"], 2) == round(tb["total_credit"], 2)
        b = admin.get(f"{API}/backup")
        assert b.status_code == 200
        txt = b.text
        for col in ("erp_parties", "erp_projects", "erp_quotations", "erp_invoices", "erp_notes"):
            assert col in txt
        d = admin.get(f"{API}/erp/dashboard").json()
        # Phase B now posts purchases/expenses, so only check the keys exist
        assert d["purchases"] >= 0 and d["expenses"] >= 0 and d["projects"] >= 1
