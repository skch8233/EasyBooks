# Easy Books Round 2 - signup/multi-tenant isolation, plan limits, expired read-only, billing, platform, licences, GSTR-1/3B, branding
import os
import uuid
import struct
import zlib
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = ("admin@easybooks.in", "Admin@123")
RAVI = ("ravi@gupta.in", "secret1")
EXPIRED = ("expired@test.in", "secret1")


def sess(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, f"{email} login {r.status_code} {r.text}"
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    s.user = r.json()["user"]
    return s


def signup(prefix="biz"):
    email = f"test_{prefix}_{uuid.uuid4().hex[:6]}@example.com"
    r = requests.post(f"{API}/auth/signup", json={"business_name": f"TEST_{prefix} Traders", "name": "TEST Owner", "email": email,
                                                  "password": "secret1", "state": "Maharashtra", "gstin": ""})
    assert r.status_code == 200, r.text
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    s.user = r.json()["user"]
    s.email = email
    return s


def png_bytes():
    raw = b"\x00\xff\x00\x00"
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


@pytest.fixture(scope="module")
def A():
    return signup("a")


@pytest.fixture(scope="module")
def B():
    return signup("b")


@pytest.fixture(scope="module")
def admin():
    return sess(*ADMIN)


def lmap(s):
    return {l["name"]: l for l in s.get(f"{API}/ledgers").json()}


# --- Signup ---
class TestSignup:
    def test_signup_trial_seeded(self, A):
        st = A.get(f"{API}/billing/status").json()
        assert st["status"] == "trial" and st["max_users"] == 2 and 29 <= st["days_left"] <= 30
        names = set(lmap(A))
        assert {"Cash", "Sales", "Purchase", "CGST", "SGST", "IGST"} <= names
        fys = A.get(f"{API}/financial-years").json()
        assert len(fys) == 1 and fys[0]["is_active"]
        assert A.user["role"] == "admin" and not A.user.get("is_superadmin")

    def test_duplicate_email(self, A):
        r = requests.post(f"{API}/auth/signup", json={"business_name": "X", "name": "X", "email": A.email.upper(), "password": "secret1"})
        assert r.status_code == 400

    def test_signup_validation(self):
        r = requests.post(f"{API}/auth/signup", json={"business_name": " ", "name": "x", "email": "test_x@example.com", "password": "secret1"})
        assert r.status_code == 400
        r = requests.post(f"{API}/auth/signup", json={"business_name": "x", "name": "x", "email": "test_y@example.com", "password": "123"})
        assert r.status_code == 400


# --- Isolation ---
class TestIsolation:
    def test_cross_tenant(self, A, B):
        LA = lmap(A)
        r = A.post(f"{API}/ledgers", json={"name": "TEST_Cust A", "group": "sundry_debtors"})
        assert r.status_code == 200, r.text
        cust = r.json()
        r = A.post(f"{API}/vouchers", json={"voucher_type": "sales", "date": "2026-01-10" if False else "2025-10-10", "party_ledger_id": cust["id"],
                                            "account_ledger_id": LA["Sales"]["id"], "gst_type": "intra",
                                            "items": [{"qty": 1, "rate": 100, "gst_rate": 18}]})
        if r.status_code == 400 and "financial year" in r.text.lower():
            fy = A.get(f"{API}/financial-years").json()[0]
            r = A.post(f"{API}/vouchers", json={"voucher_type": "sales", "date": fy["start_date"], "party_ledger_id": cust["id"],
                                                "account_ledger_id": LA["Sales"]["id"], "gst_type": "intra",
                                                "items": [{"qty": 1, "rate": 100, "gst_rate": 18}]})
        assert r.status_code == 200, r.text
        vid = r.json()["id"]
        # B cannot see
        assert "TEST_Cust A" not in lmap(B)
        assert B.get(f"{API}/vouchers/{vid}").status_code == 404
        assert all(v["id"] != vid for v in B.get(f"{API}/vouchers").json())
        assert B.put(f"{API}/ledgers/{cust['id']}", json={"name": "hack", "group": "sundry_debtors"}).status_code == 404
        assert B.delete(f"{API}/ledgers/{cust['id']}").status_code == 404
        assert B.post(f"{API}/vouchers/{vid}/cancel", json={"reason": "x"}).status_code == 404
        # B using A's ledger ids in its own voucher should fail
        LB = lmap(B)
        fyb = B.get(f"{API}/financial-years").json()[0]
        r = B.post(f"{API}/vouchers", json={"voucher_type": "sales", "date": fyb["start_date"], "party_ledger_id": cust["id"],
                                            "account_ledger_id": LB["Sales"]["id"], "gst_type": "intra", "items": [{"qty": 1, "rate": 100, "gst_rate": 18}]})
        assert r.status_code in (400, 404, 422), r.text
        tb = B.get(f"{API}/reports/trial-balance").json()
        assert tb["total_debit"] == 0
        assert B.get(f"{API}/reports/ledger-statement", params={"ledger_id": cust["id"]}).status_code in (404, 400)
        # users / audit / settings
        assert all(u["email"] != A.email for u in B.get(f"{API}/users").json())
        assert all(l.get("entity_id") != vid for l in B.get(f"{API}/audit-logs").json())
        assert B.get(f"{API}/settings").json()["company_name"].startswith("TEST_b")
        fya = A.get(f"{API}/financial-years").json()[0]
        assert B.put(f"{API}/financial-years/{fya['id']}", json={"locked": True}).status_code == 404
        bk = B.get(f"{API}/backup").json()
        assert all(v["id"] != vid for v in bk["collections"]["vouchers"])
        assert A.post(f"{API}/vouchers/{vid}/cancel", json={"reason": "TEST cleanup"}).status_code == 200


# --- User limits ---
class TestUserLimit:
    def test_trial_limit_2(self, A):
        r = A.post(f"{API}/users", json={"name": "TEST u1", "email": f"test_u1_{uuid.uuid4().hex[:5]}@example.com", "password": "secret1", "role": "viewer"})
        assert r.status_code == 200, r.text
        uid = r.json()["id"]
        r = A.post(f"{API}/users", json={"name": "TEST u2", "email": f"test_u2_{uuid.uuid4().hex[:5]}@example.com", "password": "secret1", "role": "viewer"})
        assert r.status_code == 400 and "2" in r.json()["detail"]
        # deactivate frees, reactivate blocked when full
        assert A.put(f"{API}/users/{uid}", json={"active": False}).status_code == 200
        r2 = A.post(f"{API}/users", json={"name": "TEST u3", "email": f"test_u3_{uuid.uuid4().hex[:5]}@example.com", "password": "secret1", "role": "viewer"})
        assert r2.status_code == 200
        assert A.put(f"{API}/users/{uid}", json={"active": True}).status_code == 400


# --- Expired ---
class TestExpired:
    def test_expired_read_only(self):
        E = sess(*EXPIRED)
        st = E.get(f"{API}/billing/status").json()
        assert st["status"] == "expired"
        L = lmap(E)
        assert E.get(f"{API}/vouchers").status_code == 200
        assert E.get(f"{API}/reports/trial-balance").status_code == 200
        r = E.post(f"{API}/ledgers", json={"name": "TEST_exp", "group": "sundry_debtors"})
        assert r.status_code == 402, r.text
        r = E.post(f"{API}/vouchers", json={"voucher_type": "payment", "date": "2026-05-01",
                                            "entries": [{"ledger_id": L["Rent Expense"]["id"], "debit": 10}, {"ledger_id": L["Cash"]["id"], "credit": 10}]})
        assert r.status_code == 402, r.text
        assert E.post(f"{API}/billing/order", json={"plan": "basic"}).status_code == 503


# --- Billing ---
class TestBilling:
    def test_plans(self, A):
        d = A.get(f"{API}/billing/plans").json()
        p = {x["key"]: x for x in d["plans"]}
        assert p["basic"]["total"] == 7670 and p["pro"]["total"] == 11800
        assert p["basic"]["max_users"] == 2 and p["pro"]["max_users"] == 8
        assert d["payments_enabled"] is False
        assert A.post(f"{API}/billing/order", json={"plan": "pro"}).status_code == 503
        assert A.post(f"{API}/billing/order", json={"plan": "gold"}).status_code == 422


# --- Platform + licences ---
class TestPlatformLicence:
    def test_non_super_403(self, A):
        assert A.get(f"{API}/platform/businesses").status_code == 403
        assert A.post(f"{API}/platform/businesses/x/extend", json={"plan": "basic"}).status_code == 403
        assert A.post(f"{API}/platform/licences/x/revoke").status_code == 403

    def test_extend_and_licence_flow(self, admin, B):
        bid = B.user["business_id"]
        rows = admin.get(f"{API}/platform/businesses").json()
        assert any(b["id"] == bid and b["status"] == "trial" for b in rows)
        r = admin.post(f"{API}/platform/businesses/{bid}/extend", json={"plan": "basic", "days": 20, "issue_licence": True})
        assert r.status_code == 200, r.text
        key = r.json()["licence_key"]
        assert key.startswith("EB-")
        st = B.get(f"{API}/billing/status").json()
        assert st["status"] == "active" and st["plan"] == "basic" and st["max_users"] == 2
        lics = B.get(f"{API}/licences").json()
        lic = next(l for l in lics if l["key"] == key)
        assert lic["max_devices"] == 2 and lic["alert"] is True and lic["state"] == "active"
        # other business can't see it
        assert all(l["key"] != key for l in admin.get(f"{API}/licences").json())
        # activation
        a1 = requests.post(f"{API}/licence/activate", json={"key": key.lower(), "machine_id": "TEST-M1", "device_name": "PC1"})
        assert a1.status_code == 200 and a1.json()["valid"] and a1.json()["devices_used"] == 1
        assert requests.post(f"{API}/licence/activate", json={"key": key, "machine_id": "TEST-M1"}).json()["devices_used"] == 1
        assert requests.post(f"{API}/licence/activate", json={"key": key, "machine_id": "TEST-M2"}).status_code == 200
        assert requests.post(f"{API}/licence/activate", json={"key": key, "machine_id": "TEST-M3"}).status_code == 400
        v = requests.post(f"{API}/licence/validate", json={"key": key, "machine_id": "TEST-M2"}).json()
        assert v["valid"] and v["alert"] and 19 <= v["days_left"] <= 20
        v = requests.post(f"{API}/licence/validate", json={"key": key, "machine_id": "TEST-NOPE"}).json()
        assert v["valid"] is False
        assert requests.post(f"{API}/licence/validate", json={"key": "EB-XXXX-XXXX-XXXX-XXXX", "machine_id": "m"}).status_code == 404
        # deactivate frees slot; other tenant can't deactivate
        assert admin.post(f"{API}/licences/{lic['id']}/deactivate-device", json={"machine_id": "TEST-M1"}).status_code == 404
        assert B.post(f"{API}/licences/{lic['id']}/deactivate-device", json={"machine_id": "TEST-M1"}).status_code == 200
        assert requests.post(f"{API}/licence/activate", json={"key": key, "machine_id": "TEST-M3"}).status_code == 200
        # revoke -> invalid
        assert admin.post(f"{API}/platform/licences/{lic['id']}/revoke").status_code == 200
        v = requests.post(f"{API}/licence/validate", json={"key": key, "machine_id": "TEST-M2"}).json()
        assert v["valid"] is False and v["state"] == "revoked"
        a = requests.post(f"{API}/licence/activate", json={"key": key, "machine_id": "TEST-M9"}).json()
        assert a["valid"] is False

    def test_extend_validation(self, admin, B):
        assert admin.post(f"{API}/platform/businesses/{B.user['business_id']}/extend", json={"plan": "basic", "days": 0}).status_code == 400
        assert admin.post(f"{API}/platform/businesses/nonexistent/extend", json={"plan": "basic", "days": 5}).status_code in (401, 404)


# --- GST returns ---
class TestGST:
    def test_gupta_oct_2026(self):
        R = sess(*RAVI)
        g3 = R.get(f"{API}/reports/gstr3b", params={"month": "2026-10"}).json()
        print("GSTR3B", g3)
        assert g3["outward_taxable"]["cgst"] == 112.5 and g3["outward_taxable"]["sgst"] == 112.5
        assert g3["itc"]["igst"] == 80
        assert g3["cash_payable"] == {"igst": 0.0, "cgst": 32.5, "sgst": 112.5}
        assert g3["itc_utilised"]["cgst"] == 80
        g1 = R.get(f"{API}/reports/gstr1", params={"month": "2026-10"}).json()
        print("GSTR1 summary", g1["summary"])
        assert "b2b" in g1 and "b2c" in g1 and "cdn" in g1 and "hsn" in g1
        n = g1["summary"]["net"]
        assert n["cgst"] == 112.5 and n["sgst"] == 112.5

    def test_bad_month(self, A):
        assert A.get(f"{API}/reports/gstr1", params={"month": "2026-13"}).status_code == 422
        assert A.get(f"{API}/reports/gstr3b").status_code == 422

    def test_gstr_computation_new_business(self, A):
        L = lmap(A)
        fy = A.get(f"{API}/financial-years").json()[0]
        month = fy["start_date"][:7]
        d = f"{month}-15"
        reg = A.post(f"{API}/ledgers", json={"name": "TEST_B2B", "group": "sundry_debtors", "gstin": "27ABCDE1234F1Z5", "state": "Maharashtra"}).json()
        unreg = A.post(f"{API}/ledgers", json={"name": "TEST_B2C", "group": "sundry_debtors", "state": "Gujarat"}).json()
        sup = A.post(f"{API}/ledgers", json={"name": "TEST_SUP", "group": "sundry_creditors", "gstin": "24ABCDE1234F1Z5"}).json()
        base = lambda t, p, acc, gt, items: {"voucher_type": t, "date": d, "party_ledger_id": p, "account_ledger_id": acc, "gst_type": gt, "items": items}
        vids = []
        for body in [base("sales", reg["id"], L["Sales"]["id"], "intra", [{"hsn": "1001", "qty": 10, "rate": 100, "gst_rate": 18}]),
                     base("sales", unreg["id"], L["Sales"]["id"], "inter", [{"hsn": "1002", "qty": 1, "rate": 1000, "gst_rate": 5},
                                                                                {"hsn": "1003", "qty": 1, "rate": 200, "gst_rate": 0}]),
                     base("credit_note", reg["id"], L["Sales"]["id"], "intra", [{"hsn": "1001", "qty": 1, "rate": 100, "gst_rate": 18}]),
                     base("purchase", sup["id"], L["Purchase"]["id"], "inter", [{"hsn": "2001", "qty": 1, "rate": 2000, "gst_rate": 12}]),
                     base("debit_note", sup["id"], L["Purchase"]["id"], "inter", [{"hsn": "2001", "qty": 1, "rate": 500, "gst_rate": 12}])]:
            r = A.post(f"{API}/vouchers", json=body)
            assert r.status_code == 200, r.text
            vids.append(r.json()["id"])
        g1 = A.get(f"{API}/reports/gstr1", params={"month": month}).json()
        assert len(g1["b2b"]) == 1 and g1["b2b"][0]["gstin"] == "27ABCDE1234F1Z5" and g1["b2b"][0]["cgst"] == 90
        b2c = {(r["place_of_supply"], r["rate"]): r for r in g1["b2c"]}
        assert b2c[("Gujarat", 5)]["igst"] == 50 and b2c[("Gujarat", 0)]["taxable"] == 200
        assert len(g1["cdn"]) == 1 and g1["cdn"][0]["taxable"] == 100
        n = g1["summary"]["net"]
        assert n["taxable"] == 1000 + 1200 - 100 and n["cgst"] == 81 and n["igst"] == 50
        hsn = {h["hsn"]: h for h in g1["hsn"]}
        assert hsn["1001"]["qty"] == 9 and hsn["1001"]["taxable"] == 900
        g3 = A.get(f"{API}/reports/gstr3b", params={"month": month}).json()
        print("NEW GSTR3B", g3)
        assert g3["outward_taxable"]["taxable"] == 2000 - 100 + 0 or g3["outward_taxable"]["taxable"] == 1900
        assert g3["outward_nil"]["taxable"] == 200
        assert g3["itc"]["igst"] == 240 - 60
        # liab: igst 50, cgst 81, sgst 81 ; itc igst 180 -> igst 50, cgst 81, sgst 49 -> cash sgst 32
        assert g3["cash_payable"] == {"igst": 0.0, "cgst": 0.0, "sgst": 32.0}
        assert g3["total_cash_payable"] == 32
        for vid in vids:
            A.post(f"{API}/vouchers/{vid}/cancel", json={"reason": "TEST cleanup"})


# --- Branding ---
class TestBranding:
    def test_settings_upi_and_logo(self, A):
        s = A.get(f"{API}/settings").json()
        body = {k: s.get(k, "") for k in ("company_name", "address", "state", "gstin", "phone", "email", "bank_name", "bank_account", "bank_ifsc", "invoice_terms")}
        body["gst_rates"] = s["gst_rates"]
        r = A.put(f"{API}/settings", json={**body, "upi_id": "not-a-upi"})
        assert r.status_code == 400
        r = A.put(f"{API}/settings", json={**body, "upi_id": "testshop@okhdfcbank", "bank_ifsc": "hdfc0001234", "bank_name": "HDFC"})
        assert r.status_code == 200 and r.json()["upi_id"] == "testshop@okhdfcbank" and r.json()["bank_ifsc"] == "HDFC0001234"
        assert A.get(f"{API}/settings/logo").status_code == 404
        r = A.post(f"{API}/settings/logo", files={"file": ("a.txt", b"hello", "text/plain")})
        assert r.status_code == 400
        r = A.post(f"{API}/settings/logo", files={"file": ("big.png", b"0" * (2 * 1024 * 1024 + 10), "image/png")})
        assert r.status_code == 400
        r = A.post(f"{API}/settings/logo", files={"file": ("logo.png", png_bytes(), "image/png")})
        assert r.status_code == 200, r.text
        g = A.get(f"{API}/settings/logo")
        assert g.status_code == 200 and g.headers["content-type"].startswith("image/png") and g.content == png_bytes()

    def test_logo_isolated(self, B):
        assert B.get(f"{API}/settings/logo").status_code == 404


# --- Regression on new business ---
class TestRegressionNewBiz:
    def test_tb_bs(self, B):
        tb = B.get(f"{API}/reports/trial-balance").json()
        assert tb["balanced"]
        assert B.get(f"{API}/reports/balance-sheet").status_code == 200
        assert B.get(f"{API}/reports/profit-loss").status_code == 200
        assert B.get(f"{API}/reports/dashboard", params={"from_date": "2026-04-01", "to_date": "2027-03-31"}).status_code == 200
