# Easy Books Accounting - backend regression tests (auth, roles, vouchers/GST engine, reports, ledgers, FY, backup)
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = {"email": "admin@easybooks.in", "password": "Admin@123"}
D1 = "2026-05-15"
CREATED_VOUCHERS = []  # cancelled at session end (no delete endpoint by design)
CREATED_USERS = []     # deactivated at session end
CREATED_LEDGERS = []   # deactivated at session end


def login(email, password):
    return requests.post(f"{API}/auth/login", json={"email": email, "password": password})


@pytest.fixture(scope="session")
def admin():
    r = login(**ADMIN)
    if r.status_code != 200:
        pytest.skip(f"admin login failed {r.status_code} {r.text}")
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    yield s
    for vid in CREATED_VOUCHERS:
        s.post(f"{API}/vouchers/{vid}/cancel", json={"reason": "TEST cleanup"})
    for uid in CREATED_USERS:
        s.put(f"{API}/users/{uid}", json={"active": False})
    for lid in CREATED_LEDGERS:
        s.delete(f"{API}/ledgers/{lid}")


@pytest.fixture(scope="session")
def L(admin):
    return {l["name"]: l for l in admin.get(f"{API}/ledgers").json()}


def mk_user(admin, role):
    email = f"test_{role}_{uuid.uuid4().hex[:6]}@example.com"
    r = admin.post(f"{API}/users", json={"name": f"TEST {role}", "email": email, "password": "Test@123", "role": role})
    assert r.status_code == 200, r.text
    CREATED_USERS.append(r.json()["id"])
    t = login(email, "Test@123").json()["token"]
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {t}"})
    return s, email


def post_v(admin, payload, track=True):
    r = admin.post(f"{API}/vouchers", json=payload)
    if r.status_code == 200 and track:
        CREATED_VOUCHERS.append(r.json()["id"])
    return r


def entry_map(v):
    return {e["ledger_name"]: (e["debit"], e["credit"]) for e in v["entries"]}


# ---------- Auth ----------
class TestAuth:
    def test_login_ok(self):
        r = login(**ADMIN)
        assert r.status_code == 200
        d = r.json()
        assert d["user"]["role"] == "admin" and "password_hash" not in d["user"] and d["token"]

    def test_me_requires_auth(self):
        assert requests.get(f"{API}/auth/me").status_code == 401

    def test_lockout_after_5_fails(self, admin):
        _, email = mk_user(admin, "viewer")
        codes = [login(email, "wrong-pass").status_code for _ in range(5)]
        assert codes == [401] * 5
        r = login(email, "Test@123")  # correct password must be blocked now
        assert r.status_code == 429, r.text


# ---------- Roles ----------
class TestRoles:
    def test_viewer_cannot_write(self, admin, L):
        v, _ = mk_user(admin, "viewer")
        assert v.get(f"{API}/vouchers").status_code == 200
        r = v.post(f"{API}/vouchers", json={"voucher_type": "journal", "date": D1, "entries": []})
        assert r.status_code == 403
        assert v.post(f"{API}/ledgers", json={"name": "TEST_x", "group": "cash"}).status_code == 403

    def test_accountant_restrictions(self, admin):
        a, _ = mk_user(admin, "accountant")
        assert a.get(f"{API}/users").status_code == 403
        assert a.get(f"{API}/backup").status_code == 403
        assert a.put(f"{API}/settings", json={"company_name": "X"}).status_code == 403
        assert a.get(f"{API}/ledgers").status_code == 200


# ---------- Voucher engine + reports (sequential, delta-based) ----------
class TestAccounting:
    def test_sales_intra_gst(self, admin, L):
        tb0 = admin.get(f"{API}/reports/trial-balance").json()
        pl0 = admin.get(f"{API}/reports/profit-loss").json()
        rec0 = admin.get(f"{API}/reports/outstanding", params={"kind": "receivables"}).json()["total"]
        reg0 = admin.get(f"{API}/reports/register", params={"voucher_type": "sales"}).json()["totals"]
        nn = admin.get(f"{API}/vouchers/next-number", params={"voucher_type": "sales", "date": D1}).json()["voucher_no"]
        r = post_v(admin, {"voucher_type": "sales", "date": D1, "narration": "TEST_sale", "party_ledger_id": L["Sharma Traders"]["id"],
                           "account_ledger_id": L["Sales"]["id"], "gst_type": "intra",
                           "items": [{"description": "TEST item", "hsn": "8471", "qty": 10, "rate": 1000, "gst_rate": 5}]})
        assert r.status_code == 200, r.text
        v = r.json()
        assert v["voucher_no"] == nn and v["voucher_no"].startswith("SAL/2026-27/")
        em = entry_map(v)
        assert em["Sharma Traders"] == (10500, 0)
        assert em["Sales"] == (0, 10000)
        assert em["CGST"] == (0, 250) and em["SGST"] == (0, 250)
        assert v["totals"]["total"] == 10500
        # reports deltas
        tb = admin.get(f"{API}/reports/trial-balance").json()
        assert tb["balanced"] and tb["total_debit"] == tb["total_credit"]
        pl = admin.get(f"{API}/reports/profit-loss").json()
        assert round(pl["gross_profit"] - pl0["gross_profit"], 2) == 10000
        rec = admin.get(f"{API}/reports/outstanding", params={"kind": "receivables"}).json()["total"]
        assert round(rec - rec0, 2) == 10500
        reg = admin.get(f"{API}/reports/register", params={"voucher_type": "sales"}).json()["totals"]
        assert round(reg["total"] - reg0.get("total", 0), 2) == 10500 and round(reg["cgst"] - reg0.get("cgst", 0), 2) == 250
        # numbering increments
        nn2 = admin.get(f"{API}/vouchers/next-number", params={"voucher_type": "sales", "date": D1}).json()["voucher_no"]
        assert int(nn2.split("/")[-1]) == int(nn.split("/")[-1]) + 1
        TestAccounting.sale_id = v["id"]

    def test_sales_inter_igst(self, admin, L):
        r = post_v(admin, {"voucher_type": "sales", "date": D1, "party_ledger_id": L["Sharma Traders"]["id"], "account_ledger_id": L["Sales"]["id"],
                           "gst_type": "inter", "items": [{"qty": 10, "rate": 1000, "gst_rate": 18}]})
        assert r.status_code == 200, r.text
        em = entry_map(r.json())
        assert em["Sharma Traders"] == (11800, 0) and em["IGST"] == (0, 1800) and "CGST" not in em

    def test_purchase_dn_cn_directions(self, admin, L):
        base = {"date": D1, "gst_type": "intra", "items": [{"qty": 2, "rate": 500, "gst_rate": 12}]}
        p = post_v(admin, {**base, "voucher_type": "purchase", "party_ledger_id": L["Raj Electronics"]["id"], "account_ledger_id": L["Purchase"]["id"]})
        assert p.status_code == 200, p.text
        em = entry_map(p.json())
        assert em["Raj Electronics"] == (0, 1120) and em["Purchase"] == (1000, 0) and em["CGST"] == (60, 0) and em["SGST"] == (60, 0)
        assert p.json()["voucher_no"].startswith("PUR/2026-27/")
        dn = post_v(admin, {**base, "voucher_type": "debit_note", "party_ledger_id": L["Raj Electronics"]["id"], "account_ledger_id": L["Purchase"]["id"]})
        assert dn.status_code == 200, dn.text
        em = entry_map(dn.json())
        assert em["Raj Electronics"] == (1120, 0) and em["Purchase"] == (0, 1000) and em["CGST"] == (0, 60)
        cn = post_v(admin, {**base, "voucher_type": "credit_note", "party_ledger_id": L["Sharma Traders"]["id"], "account_ledger_id": L["Sales"]["id"]})
        assert cn.status_code == 200, cn.text
        em = entry_map(cn.json())
        assert em["Sharma Traders"] == (0, 1120) and em["Sales"] == (1000, 0) and em["SGST"] == (60, 0)

    def test_validation_rejections(self, admin, L):
        cash, bank, rent, cap = (L[n]["id"] for n in ("Cash", "HDFC Bank", "Rent Expense", "Capital Account"))
        cases = [
            ("journal", [{"ledger_id": rent, "debit": 100}, {"ledger_id": cap, "credit": 90}]),
            ("payment", [{"ledger_id": rent, "debit": 100}, {"ledger_id": cap, "credit": 100}]),
            ("contra", [{"ledger_id": cash, "debit": 100}, {"ledger_id": rent, "credit": 100}]),
            ("journal", [{"ledger_id": rent, "debit": 100, "credit": 100}, {"ledger_id": cap, "credit": 0, "debit": 0}]),
            ("receipt", [{"ledger_id": rent, "debit": 100}, {"ledger_id": cap, "credit": 100}]),
        ]
        for t, e in cases:
            r = post_v(admin, {"voucher_type": t, "date": D1, "entries": e})
            assert r.status_code == 400, f"{t} {e} -> {r.status_code} {r.text}"
        # sales with purchase ledger as account
        r = post_v(admin, {"voucher_type": "sales", "date": D1, "party_ledger_id": L["Sharma Traders"]["id"], "account_ledger_id": L["Purchase"]["id"],
                           "items": [{"qty": 1, "rate": 10, "gst_rate": 5}]})
        assert r.status_code == 400
        # date outside any FY
        r = post_v(admin, {"voucher_type": "contra", "date": "2001-01-01", "entries": [{"ledger_id": cash, "debit": 1}, {"ledger_id": bank, "credit": 1}]})
        assert r.status_code == 400

    def test_payment_receipt_contra_and_ledger_statement(self, admin, L):
        cash, bank, rent = L["Cash"]["id"], L["HDFC Bank"]["id"], L["Rent Expense"]["id"]
        st0 = admin.get(f"{API}/reports/ledger-statement", params={"ledger_id": cash}).json()
        assert st0["opening"] == 50000
        pm = post_v(admin, {"voucher_type": "payment", "date": D1, "entries": [{"ledger_id": rent, "debit": 5000}, {"ledger_id": cash, "credit": 5000}]})
        assert pm.status_code == 200, pm.text
        assert pm.json()["voucher_no"].startswith("PMT/")
        co = post_v(admin, {"voucher_type": "contra", "date": D1, "entries": [{"ledger_id": cash, "debit": 2000}, {"ledger_id": bank, "credit": 2000}]})
        assert co.status_code == 200, co.text
        rc = post_v(admin, {"voucher_type": "receipt", "date": D1, "entries": [{"ledger_id": bank, "debit": 1000}, {"ledger_id": L["Sharma Traders"]["id"], "credit": 1000}]})
        assert rc.status_code == 200, rc.text
        st = admin.get(f"{API}/reports/ledger-statement", params={"ledger_id": cash}).json()
        assert round(st["closing"] - st0["closing"], 2) == -3000
        run = st["opening"]
        for row in st["rows"]:
            run = round(run + row["debit"] - row["credit"], 2)
            assert row["balance"] == run
        assert st["closing"] == run
        # balance sheet balanced
        bs = admin.get(f"{API}/reports/balance-sheet").json()
        assert bs["balanced"] and bs["total_assets"] == bs["total_liabilities"], bs
        tb = admin.get(f"{API}/reports/trial-balance").json()
        assert tb["balanced"]
        pl = admin.get(f"{API}/reports/profit-loss").json()
        assert round(pl["net_profit"], 2) == round(bs["profit_loss"], 2)
        dash = admin.get(f"{API}/reports/dashboard", params={"from_date": "2026-04-01", "to_date": "2027-03-31"}).json()
        cash_led = [l for l in admin.get(f"{API}/ledgers", params={"group": "cash"}).json()]
        assert dash["cash_balance"] == round(sum(l["balance"] if l["balance_type"] == "Dr" else -l["balance"] for l in cash_led), 2)

    def test_edit_and_cancel_with_audit(self, admin, L):
        cash, rent = L["Cash"]["id"], L["Rent Expense"]["id"]
        r = post_v(admin, {"voucher_type": "journal", "date": D1, "narration": "TEST_edit", "entries": [{"ledger_id": rent, "debit": 700}, {"ledger_id": cash, "credit": 700}]})
        assert r.status_code == 200, r.text
        vid = r.json()["id"]
        before = admin.get(f"{API}/reports/ledger-statement", params={"ledger_id": rent}).json()["closing"]
        u = admin.put(f"{API}/vouchers/{vid}", json={"voucher_type": "journal", "date": D1, "narration": "TEST_edited",
                                                      "entries": [{"ledger_id": rent, "debit": 900}, {"ledger_id": cash, "credit": 900}]})
        assert u.status_code == 200, u.text
        after = admin.get(f"{API}/reports/ledger-statement", params={"ledger_id": rent}).json()["closing"]
        assert round(after - before, 2) == 200
        g = admin.get(f"{API}/vouchers/{vid}").json()
        assert g["narration"] == "TEST_edited" and "update" in [h["action"] for h in g["history"]]
        # type change rejected
        assert admin.put(f"{API}/vouchers/{vid}", json={"voucher_type": "payment", "date": D1, "entries": []}).status_code == 400
        c = admin.post(f"{API}/vouchers/{vid}/cancel", json={"reason": "TEST cancel"})
        assert c.status_code == 200
        g = admin.get(f"{API}/vouchers/{vid}").json()
        assert g["status"] == "cancelled" and "cancel" in [h["action"] for h in g["history"]]
        after2 = admin.get(f"{API}/reports/ledger-statement", params={"ledger_id": rent}).json()["closing"]
        assert round(after2 - before, 2) == -700
        assert admin.post(f"{API}/vouchers/{vid}/cancel", json={}).status_code == 400
        assert admin.put(f"{API}/vouchers/{vid}", json={"voucher_type": "journal", "date": D1, "entries": [{"ledger_id": rent, "debit": 1}, {"ledger_id": cash, "credit": 1}]}).status_code == 400
        assert admin.delete(f"{API}/vouchers/{vid}").status_code in (404, 405)
        lst = admin.get(f"{API}/vouchers", params={"q": "TEST_edited"}).json()
        assert any(x["id"] == vid and x["status"] == "cancelled" for x in lst)

    def test_list_filters(self, admin, L):
        rows = admin.get(f"{API}/vouchers", params={"voucher_type": "sales", "from_date": D1, "to_date": D1}).json()
        assert rows and all(r["voucher_type"] == "sales" and r["date"] == D1 for r in rows)
        rows = admin.get(f"{API}/vouchers", params={"ledger_id": L["Raj Electronics"]["id"]}).json()
        assert rows and all(any(e["ledger_id"] == L["Raj Electronics"]["id"] for e in r["entries"]) for r in rows)


# ---------- Ledgers ----------
class TestLedgers:
    def test_ledger_crud(self, admin, L):
        name = f"TEST_Ledger_{uuid.uuid4().hex[:5]}"
        r = admin.post(f"{API}/ledgers", json={"name": name, "group": "sundry_debtors", "opening_balance": 0, "gstin": "27abcde1234f1z5"})
        assert r.status_code == 200, r.text
        lid = r.json()["id"]
        CREATED_LEDGERS.append(lid)
        assert r.json()["gstin"] == "27ABCDE1234F1Z5"
        assert admin.post(f"{API}/ledgers", json={"name": name.lower(), "group": "cash"}).status_code == 400
        u = admin.put(f"{API}/ledgers/{lid}", json={"name": name + "_e", "group": "sundry_debtors", "phone": "999"})
        assert u.status_code == 200 and u.json()["phone"] == "999"
        assert any(l["id"] == lid and l["name"] == name + "_e" for l in admin.get(f"{API}/ledgers").json())
        assert admin.delete(f"{API}/ledgers/{lid}").status_code == 200
        assert not any(l["id"] == lid for l in admin.get(f"{API}/ledgers").json())

    def test_deactivate_blocked(self, admin, L):
        assert admin.delete(f"{API}/ledgers/{L['CGST']['id']}").status_code == 400  # system
        assert admin.delete(f"{API}/ledgers/{L['Sharma Traders']['id']}").status_code == 400  # has txns / or system
        assert admin.post(f"{API}/ledgers", json={"name": "TEST_bad", "group": "nope"}).status_code == 400


# ---------- FY / settings / backup ----------
class TestAdmin:
    def test_fy_lock_blocks_vouchers(self, admin, L):
        fys = admin.get(f"{API}/financial-years").json()
        fy = next(f for f in fys if f["name"] == "2026-27")
        try:
            assert admin.put(f"{API}/financial-years/{fy['id']}", json={"locked": True}).json()["locked"] is True
            r = post_v(admin, {"voucher_type": "contra", "date": D1, "entries": [{"ledger_id": L["Cash"]["id"], "debit": 1}, {"ledger_id": L["HDFC Bank"]["id"], "credit": 1}]})
            assert r.status_code == 400 and "locked" in r.text.lower()
        finally:
            assert admin.put(f"{API}/financial-years/{fy['id']}", json={"locked": False}).json()["locked"] is False

    def test_fy_create_duplicate_and_default(self, admin):
        fys = admin.get(f"{API}/financial-years").json()
        names = {f["name"] for f in fys}
        r = admin.post(f"{API}/financial-years", json={"start_year": 2026})
        assert r.status_code == 400
        if "2027-28" not in names:
            r = admin.post(f"{API}/financial-years", json={"start_year": 2027})
            assert r.status_code == 200 and r.json()["name"] == "2027-28"
        active = next(f for f in fys if f["is_active"])
        assert admin.put(f"{API}/financial-years/{active['id']}", json={"is_active": True}).json()["is_active"] is True
        assert sum(1 for f in admin.get(f"{API}/financial-years").json() if f["is_active"]) == 1

    def test_settings_gstin_validation(self, admin):
        s = admin.get(f"{API}/settings").json()
        assert admin.put(f"{API}/settings", json={**s, "gstin": "BADGSTIN"}).status_code == 400
        r = admin.put(f"{API}/settings", json=s)
        assert r.status_code == 200 and r.json()["gst_rates"] == sorted(s["gst_rates"])

    def test_backup_and_restore_validation(self, admin):
        b = admin.get(f"{API}/backup")
        assert b.status_code == 200
        cols = b.json()["collections"]
        assert isinstance(cols["vouchers"], list) and isinstance(cols["ledgers"], list) and "users" not in cols
        # only invalid payload tested (real restore replaces all data - manual check)
        assert admin.post(f"{API}/restore", json={"collections": {"ledgers": "x"}}).status_code == 400
