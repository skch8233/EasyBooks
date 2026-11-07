# Easy Books Round 4 - Stock items (CRUD, on-hand, movements, voucher item_id) and Payment reminders (FIFO overdue, send, public pay)
import os
import uuid
from datetime import date, timedelta
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
TODAY = date.today()


def ds(days_ago):
    return (TODAY - timedelta(days=days_ago)).isoformat()


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    return s


def signup(prefix):
    email = f"test_{prefix}_{uuid.uuid4().hex[:6]}@example.com"
    r = requests.post(f"{API}/auth/signup", json={"business_name": f"TEST_{prefix} Traders", "name": "TEST Owner", "email": email,
                                                  "password": "secret1", "state": "Maharashtra", "gstin": ""})
    assert r.status_code == 200, r.text
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    s.email = email
    return s


def lmap(s):
    return {l["name"]: l for l in s.get(f"{API}/ledgers").json()}


@pytest.fixture(scope="module")
def A():
    return signup("r4a")


@pytest.fixture(scope="module")
def B():
    return signup("r4b")


@pytest.fixture(scope="module")
def ctx(A):
    L = lmap(A)
    cust = A.post(f"{API}/ledgers", json={"name": "TEST_Cust", "group": "sundry_debtors", "state": "Maharashtra", "phone": "9876543210"}).json()
    supp = A.post(f"{API}/ledgers", json={"name": "TEST_Supp", "group": "sundry_creditors", "state": "Maharashtra"}).json()
    return {"L": L, "cust": cust, "supp": supp}


def item_voucher(s, ctx, vtype, item_id, qty, rate, d=None, desc=""):
    party = ctx["cust"]["id"] if vtype in ("sales", "credit_note") else ctx["supp"]["id"]
    acct = ctx["L"]["Sales"]["id"] if vtype in ("sales", "credit_note") else ctx["L"]["Purchase"]["id"]
    return {"voucher_type": vtype, "date": d or ds(1), "party_ledger_id": party, "account_ledger_id": acct, "gst_type": "intra",
            "items": [{"item_id": item_id, "description": desc, "hsn": "1507", "qty": qty, "rate": rate, "gst_rate": 5}]}


def get_item(s, sid):
    return next(i for i in s.get(f"{API}/stock-items").json()["items"] if i["id"] == sid)


class TestStock:
    st = {}

    def test_create_and_dup(self, A):
        r = A.post(f"{API}/stock-items", json={"name": "TEST_Rice", "hsn": "1006", "unit": "Kg", "gst_rate": 5, "sale_rate": 60,
                                               "purchase_rate": 45, "opening_qty": 10, "opening_rate": 40, "reorder_level": 5})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["name"] == "TEST_Rice" and isinstance(d["id"], str) and "_id" not in d
        TestStock.st["rice"] = d["id"]
        assert A.post(f"{API}/stock-items", json={"name": " test_rice "}).status_code == 400
        it = get_item(A, d["id"])
        assert it["on_hand"] == 10 and it["avg_cost"] == 40 and it["value"] == 400 and it["low"] is False

    def test_flow_on_hand(self, A, ctx):
        sid = TestStock.st["rice"]
        r = A.post(f"{API}/vouchers", json=item_voucher(A, ctx, "purchase", sid, 20, 50, ds(5)))
        assert r.status_code == 200, r.text
        assert r.json()["items"][0]["description"] == "TEST_Rice" and r.json()["items"][0]["unit"] == "Kg"
        assert r.json()["items"][0]["item_id"] == sid
        it = get_item(A, sid)
        assert it["on_hand"] == 30 and it["avg_cost"] == round(1400 / 30, 2)
        sale = A.post(f"{API}/vouchers", json=item_voucher(A, ctx, "sales", sid, 8, 60, ds(4))).json()
        TestStock.st["sale"] = sale
        assert get_item(A, sid)["on_hand"] == 22
        assert A.post(f"{API}/vouchers", json=item_voucher(A, ctx, "credit_note", sid, 2, 60, ds(3))).status_code == 200
        assert get_item(A, sid)["on_hand"] == 24
        assert A.post(f"{API}/vouchers", json=item_voucher(A, ctx, "debit_note", sid, 3, 50, ds(2))).status_code == 200
        it = get_item(A, sid)
        assert it["on_hand"] == 21 and it["sold_qty"] == 8 and it["purchased_qty"] == 20

    def test_movements(self, A):
        sid = TestStock.st["rice"]
        m = A.get(f"{API}/stock-items/{sid}/movements").json()
        assert m["opening"] == 10 and m["closing"] == 21 and len(m["rows"]) == 4
        assert [r["balance"] for r in m["rows"]] == [30, 22, 24, 21]
        assert m["rows"][0]["in_qty"] == 20 and m["rows"][1]["out_qty"] == 8
        m2 = A.get(f"{API}/stock-items/{sid}/movements", params={"from_date": ds(3)}).json()
        assert m2["opening"] == 22 and m2["closing"] == 21 and len(m2["rows"]) == 2

    def test_edit_and_cancel(self, A, ctx):
        sid, sale = TestStock.st["rice"], TestStock.st["sale"]
        r = A.put(f"{API}/vouchers/{sale['id']}", json=item_voucher(A, ctx, "sales", sid, 18, 60, ds(4)))
        assert r.status_code == 200, r.text
        it = get_item(A, sid)
        assert it["on_hand"] == 11
        r = A.post(f"{API}/vouchers/{sale['id']}/cancel", json={"reason": "TEST cancel"})
        assert r.status_code == 200, r.text
        assert get_item(A, sid)["on_hand"] == 29

    def test_low_and_negative(self, A, ctx):
        sid = TestStock.st["rice"]
        A.post(f"{API}/vouchers", json=item_voucher(A, ctx, "sales", sid, 25, 60, ds(1)))
        it = get_item(A, sid)
        assert it["on_hand"] == 4 and it["low"] is True and it["negative"] is False
        A.post(f"{API}/vouchers", json=item_voucher(A, ctx, "sales", sid, 6, 60, ds(1)))
        d = A.get(f"{API}/stock-items").json()
        it = next(i for i in d["items"] if i["id"] == sid)
        assert it["on_hand"] == -2 and it["negative"] is True and it["value"] == 0 and d["low_count"] >= 1

    def test_bad_item_ids(self, A, B, ctx):
        bitem = B.post(f"{API}/stock-items", json={"name": "TEST_B item"}).json()
        TestStock.st["b_item"] = bitem["id"]
        assert A.post(f"{API}/vouchers", json=item_voucher(A, ctx, "sales", "bogus-id", 1, 10)).status_code == 400
        assert A.post(f"{API}/vouchers", json=item_voucher(A, ctx, "sales", bitem["id"], 1, 10)).status_code == 400

    def test_isolation(self, A, B):
        sid = TestStock.st["rice"]
        assert all(i["id"] != sid for i in B.get(f"{API}/stock-items").json()["items"])
        assert B.put(f"{API}/stock-items/{sid}", json={"name": "hack"}).status_code == 404
        assert B.get(f"{API}/stock-items/{sid}/movements").status_code == 404
        assert B.delete(f"{API}/stock-items/{sid}").status_code == 404

    def test_update_and_delete(self, A):
        sid = TestStock.st["rice"]
        other = A.post(f"{API}/stock-items", json={"name": "TEST_Dal"}).json()
        assert A.put(f"{API}/stock-items/{sid}", json={"name": "test_dal"}).status_code == 400
        r = A.put(f"{API}/stock-items/{sid}", json={"name": "TEST_Rice", "unit": "Kg", "reorder_level": 1, "opening_qty": 10, "opening_rate": 40, "gst_rate": 5})
        assert r.status_code == 200 and r.json()["reorder_level"] == 1
        assert A.delete(f"{API}/stock-items/{sid}").status_code == 400
        assert A.delete(f"{API}/stock-items/{other['id']}").status_code == 200
        assert all(i["id"] != other["id"] for i in A.get(f"{API}/stock-items").json()["items"])
        assert A.post(f"{API}/stock-items", json={"name": "TEST_Dal"}).status_code == 200

    def test_tb_balanced(self, A):
        tb = A.get(f"{API}/reports/trial-balance").json()
        assert tb["balanced"]


class TestReminders:
    st = {}

    def test_fifo_overdue(self, A, ctx):
        L = ctx["L"]
        c = A.post(f"{API}/ledgers", json={"name": "TEST_Late", "group": "sundry_debtors", "state": "Maharashtra", "phone": "09123456789", "credit_days": 15}).json()
        assert c["credit_days"] == 15
        TestReminders.st["c"] = c
        def sale(d, rate):
            b = {"voucher_type": "sales", "date": d, "party_ledger_id": c["id"], "account_ledger_id": L["Sales"]["id"], "gst_type": "none",
                 "items": [{"description": "TEST x", "qty": 1, "rate": rate, "gst_rate": 0}]}
            r = A.post(f"{API}/vouchers", json=b)
            assert r.status_code == 200, r.text
            return r.json()
        sale(ds(40), 1000)
        sale(ds(30), 2000)
        sale(ds(5), 500)
        r = A.post(f"{API}/vouchers", json={"voucher_type": "receipt", "date": ds(2), "entries": [{"ledger_id": L["Cash"]["id"], "debit": 1500}, {"ledger_id": c["id"], "credit": 1500}]})
        assert r.status_code == 200, r.text
        d = A.get(f"{API}/reminders/overdue").json()
        row = next(x for x in d["customers"] if x["ledger_id"] == c["id"])
        assert row["outstanding"] == 2000 and row["overdue_amount"] == 1500
        assert len(row["bills"]) == 2 and row["bills"][0]["pending"] == 1500 and row["bills"][0]["days_overdue"] == 15
        assert row["bills"][0]["due_date"] == (TODAY - timedelta(days=15)).isoformat()
        assert row["bills"][1]["overdue"] is False and row["max_days_overdue"] == 15
        assert row["last_reminded_at"] is None

    def test_default_credit_days(self, A, ctx):
        L = ctx["L"]
        s = A.get(f"{API}/settings").json()
        body = {k: v for k, v in s.items() if k not in ("business_id", "id", "logo", "logo_path", "updated_at", "created_at")}
        r = A.put(f"{API}/settings", json={**body, "default_credit_days": 10})
        assert r.status_code == 200, r.text
        assert r.json()["default_credit_days"] == 10
        c = A.post(f"{API}/ledgers", json={"name": "TEST_Default", "group": "sundry_debtors", "state": "Maharashtra"}).json()
        A.post(f"{API}/vouchers", json={"voucher_type": "sales", "date": ds(20), "party_ledger_id": c["id"], "account_ledger_id": L["Sales"]["id"],
                                         "gst_type": "none", "items": [{"description": "TEST y", "qty": 1, "rate": 700, "gst_rate": 0}]})
        row = next(x for x in A.get(f"{API}/reminders/overdue").json()["customers"] if x["ledger_id"] == c["id"])
        assert row["credit_days"] == 10 and row["overdue_amount"] == 700 and row["max_days_overdue"] == 10
        TestReminders.st["nodue_ledger"] = ctx["supp"]["id"]

    def test_send_and_public(self, A):
        c = TestReminders.st["c"]
        r = A.post(f"{API}/reminders/{c['id']}/send")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["overdue_amount"] == 1500 and d["phone"] == "09123456789" and len(d["bills"]) == 1 and d["token"]
        TestReminders.st["token"] = d["token"]
        row = next(x for x in A.get(f"{API}/reminders/overdue").json()["customers"] if x["ledger_id"] == c["id"])
        assert row["last_reminded_at"] and row["reminder_count"] == 1
        p = requests.get(f"{API}/public/pay/{d['token']}")
        assert p.status_code == 200
        pj = p.json()
        assert pj["customer"] == "TEST_Late" and pj["overdue_amount"] == 1500 and pj["outstanding"] == 2000 and len(pj["bills"]) == 2
        assert "business_id" not in str(pj) and "ledger_id" not in str(pj)
        assert requests.get(f"{API}/public/pay/invalidtoken123").status_code == 404

    def test_send_nothing_overdue(self, A, ctx):
        assert A.post(f"{API}/reminders/{ctx['supp']['id']}/send").status_code == 400
        assert A.post(f"{API}/reminders/bogus/send").status_code in (400, 404)

    def test_send_cross_tenant(self, B):
        assert B.post(f"{API}/reminders/{TestReminders.st['c']['id']}/send").status_code in (400, 404)

    def test_viewer_403(self, A):
        email = f"test_v4_{uuid.uuid4().hex[:5]}@example.com"
        r = A.post(f"{API}/users", json={"name": "TEST v", "email": email, "password": "secret1", "role": "viewer"})
        assert r.status_code == 200, r.text
        v = login(email, "secret1")
        assert v.post(f"{API}/reminders/{TestReminders.st['c']['id']}/send").status_code == 403
        assert v.get(f"{API}/reminders/overdue").status_code == 200
        assert v.post(f"{API}/stock-items", json={"name": "TEST_v"}).status_code == 403

    def test_expired_402(self):
        E = login("expired@test.in", "secret1")
        assert E.post(f"{API}/reminders/anything/send").status_code == 402
        assert E.post(f"{API}/stock-items", json={"name": "TEST_e"}).status_code == 402
        assert E.get(f"{API}/stock-items").status_code == 200

    def test_paid_in_full(self, A, ctx):
        c = TestReminders.st["c"]
        r = A.post(f"{API}/vouchers", json={"voucher_type": "receipt", "date": ds(0), "entries": [{"ledger_id": ctx["L"]["Cash"]["id"], "debit": 2000}, {"ledger_id": c["id"], "credit": 2000}]})
        assert r.status_code == 200, r.text
        pj = requests.get(f"{API}/public/pay/{TestReminders.st['token']}").json()
        assert pj["overdue_amount"] == 0 and pj["outstanding"] == 0 and pj["bills"] == []
        assert all(x["ledger_id"] != c["id"] for x in A.get(f"{API}/reminders/overdue").json()["customers"])
        assert A.post(f"{API}/reminders/{c['id']}/send").status_code == 400
        assert A.get(f"{API}/reports/trial-balance").json()["balanced"]

    def test_ravi_late_payer(self):
        R = login("ravi@gupta.in", "secret1")
        d = R.get(f"{API}/reminders/overdue").json()
        lp = [x for x in d["customers"] if x["name"] == "Late Payer"]
        assert lp and lp[0]["overdue_amount"] > 0 and lp[0]["credit_days"] == 15
        assert any(i["name"] == "Sunflower Oil 1L" for i in R.get(f"{API}/stock-items").json()["items"])
