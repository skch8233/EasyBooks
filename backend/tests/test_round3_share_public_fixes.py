# Easy Books Round 3 - public plans, WhatsApp share + public invoice, and Round 2 fix retests (restore, expired 402, signup GSTIN, licence race, revoke audit, GSTR-1 counts, settings partial PUT)
import os
import uuid
import concurrent.futures as cf
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


def signup(prefix="r3", gstin=""):
    email = f"test_{prefix}_{uuid.uuid4().hex[:6]}@example.com"
    r = requests.post(f"{API}/auth/signup", json={"business_name": f"TEST_{prefix} Traders", "name": "TEST Owner", "email": email,
                                                  "password": "secret1", "state": "Maharashtra", "gstin": gstin})
    assert r.status_code == 200, r.text
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    s.user = r.json()["user"]
    s.email = email
    return s


def lmap(s):
    return {l["name"]: l for l in s.get(f"{API}/ledgers").json()}


@pytest.fixture(scope="module")
def A():
    return signup("r3a")


@pytest.fixture(scope="module")
def B():
    return signup("r3b")


@pytest.fixture(scope="module")
def admin():
    return sess(*ADMIN)


@pytest.fixture(scope="module")
def sales_A(A):
    L = lmap(A)
    party = A.post(f"{API}/ledgers", json={"name": "TEST_WA Party", "group": "sundry_debtors", "state": "Maharashtra", "phone": "98765 43210"}).json()
    d = A.get(f"{API}/financial-years").json()[0]["start_date"][:7] + "-10"
    body = {"voucher_type": "sales", "date": d, "party_ledger_id": party["id"], "account_ledger_id": L["Sales"]["id"], "gst_type": "intra",
            "items": [{"hsn": "1001", "description": "TEST rice", "qty": 2, "rate": 500, "gst_rate": 5}]}
    r = A.post(f"{API}/vouchers", json=body)
    assert r.status_code == 200, r.text
    return r.json()


# --- Public plans ---
class TestPublicPlans:
    def test_public_plans_no_auth(self):
        r = requests.get(f"{API}/public/plans")
        assert r.status_code == 200
        d = r.json()
        p = {x["key"]: x for x in d["plans"]}
        assert p["basic"]["price"] == 6500 and p["basic"]["total"] == 7670
        assert p["pro"]["price"] == 10000 and p["pro"]["total"] == 11800
        assert d["payments_enabled"] is False and d["trial_days"] == 30


# --- WhatsApp share + public invoice ---
class TestShare:
    def test_share_sales(self, A, sales_A):
        r = A.post(f"{API}/vouchers/{sales_A['id']}/share")
        assert r.status_code == 200, r.text
        d = r.json()
        assert isinstance(d["token"], str) and len(d["token"]) >= 16
        assert d["phone"] == "98765 43210"
        # idempotent token
        assert A.post(f"{API}/vouchers/{sales_A['id']}/share").json()["token"] == d["token"]

    def test_share_non_sales_400(self, A):
        L = lmap(A)
        r = A.post(f"{API}/vouchers", json={"voucher_type": "payment", "date": A.get(f"{API}/financial-years").json()[0]["start_date"],
                                            "entries": [{"ledger_id": L["Rent Expense"]["id"], "debit": 10}, {"ledger_id": L["Cash"]["id"], "credit": 10}]})
        assert r.status_code == 200, r.text
        assert A.post(f"{API}/vouchers/{r.json()['id']}/share").status_code == 400
        A.post(f"{API}/vouchers/{r.json()['id']}/cancel", json={"reason": "TEST cleanup"})

    def test_share_cross_tenant_404(self, B, sales_A):
        assert B.post(f"{API}/vouchers/{sales_A['id']}/share").status_code == 404
        assert requests.post(f"{API}/vouchers/{sales_A['id']}/share").status_code in (401, 403)

    def test_public_invoice(self, A, sales_A):
        tok = A.post(f"{API}/vouchers/{sales_A['id']}/share").json()["token"]
        r = requests.get(f"{API}/public/invoice/{tok}")
        assert r.status_code == 200, r.text
        d = r.json()
        v = d["voucher"]
        assert v["voucher_no"] == sales_A["voucher_no"] and v["totals"]["total"] == 1050
        assert "entries" not in v and "business_id" not in v and "share_token" not in v and "id" not in v
        assert d["settings"]["company_name"] == "TEST_r3a Traders"
        assert set(d["settings"]) <= {"company_name", "address", "state", "gstin", "phone", "email", "upi_id", "bank_name", "bank_account", "bank_ifsc", "invoice_terms", "has_logo"}
        assert d["party"]["name"] == "TEST_WA Party"
        assert requests.get(f"{API}/public/invoice/{tok}/logo").status_code == 404  # no logo uploaded

    def test_public_invalid_token(self):
        assert requests.get(f"{API}/public/invoice/notarealtoken123").status_code == 404
        assert requests.get(f"{API}/public/invoice/notarealtoken123/logo").status_code == 404

    def test_gupta_existing_token(self):
        R = sess(*RAVI)
        vs = R.get(f"{API}/vouchers", params={"voucher_type": "sales"}).json()
        vs = vs if isinstance(vs, list) else vs.get("items", vs.get("vouchers", []))
        v = next(x for x in vs if x["voucher_no"] == "SAL/2026-27/0002")
        tok = R.post(f"{API}/vouchers/{v['id']}/share").json()["token"]
        d = requests.get(f"{API}/public/invoice/{tok}").json()
        assert d["voucher"]["voucher_no"] == "SAL/2026-27/0002"
        assert d["settings"]["company_name"].startswith("Gupta")


# --- Restore fix ---
class TestRestore:
    def test_foreign_restore_400_and_intact(self, A, B):
        before_fy = A.get(f"{API}/financial-years").json()
        before_l = len(A.get(f"{API}/ledgers").json())
        bk = B.get(f"{API}/backup").json()
        r = A.post(f"{API}/restore", json={"collections": bk["collections"]})
        assert r.status_code == 400, r.text
        # strip business_id
        stripped = {c: ([{k: v for k, v in d.items() if k != "business_id"} for d in docs] if isinstance(docs, list) else docs)
                    for c, docs in bk["collections"].items()}
        r = A.post(f"{API}/restore", json={"collections": stripped})
        assert r.status_code == 400, r.text
        assert A.get(f"{API}/financial-years").json() == before_fy
        assert len(A.get(f"{API}/ledgers").json()) == before_l
        assert B.get(f"{API}/financial-years").status_code == 200 and len(B.get(f"{API}/financial-years").json()) == 1

    def test_own_restore_200(self, B):
        bk = B.get(f"{API}/backup").json()
        nl = len(bk["collections"]["ledgers"])
        r = B.post(f"{API}/restore", json={"collections": bk["collections"]})
        assert r.status_code == 200, r.text
        assert len(B.get(f"{API}/ledgers").json()) == nl
        assert len(B.get(f"{API}/financial-years").json()) == 1
        assert B.get(f"{API}/reports/trial-balance").json()["balanced"]


# --- Expired 402 ---
class TestExpiredWrites:
    def test_admin_writes_402(self):
        E = sess(*EXPIRED)
        s = E.get(f"{API}/settings").json()
        assert E.put(f"{API}/settings", json={"company_name": s["company_name"]}).status_code == 402
        assert E.post(f"{API}/settings/logo", files={"file": ("l.png", b"\x89PNG", "image/png")}).status_code == 402
        assert E.post(f"{API}/financial-years", json={"start_year": 2099}).status_code == 402
        fy = E.get(f"{API}/financial-years").json()[0]
        assert E.put(f"{API}/financial-years/{fy['id']}", json={"locked": fy.get("locked", False)}).status_code == 402
        assert E.post(f"{API}/users", json={"name": "TEST x", "email": f"test_e_{uuid.uuid4().hex[:5]}@example.com", "password": "secret1"}).status_code == 402
        users = E.get(f"{API}/users").json()
        assert E.put(f"{API}/users/{users[0]['id']}", json={"name": users[0]["name"]}).status_code == 402
        assert E.get(f"{API}/audit-logs").status_code == 200


# --- Signup GSTIN ---
class TestSignupGSTIN:
    def test_invalid_gstin_400(self):
        r = requests.post(f"{API}/auth/signup", json={"business_name": "TEST_bad", "name": "x", "email": f"test_g_{uuid.uuid4().hex[:5]}@example.com",
                                                      "password": "secret1", "gstin": "BADGSTIN"})
        assert r.status_code == 400


# --- Licence race + revoke audit ---
class TestLicence:
    def test_parallel_activation_and_revoke_audit(self, admin):
        C = signup("r3lic")
        r = admin.post(f"{API}/platform/businesses/{C.user['business_id']}/extend", json={"plan": "basic", "days": 30, "issue_licence": True})
        assert r.status_code == 200, r.text
        key = r.json()["licence_key"]
        def act(i):
            return requests.post(f"{API}/licence/activate", json={"key": key, "machine_id": f"TEST-PAR-{i}", "device_name": f"P{i}"}).status_code
        with cf.ThreadPoolExecutor(10) as ex:
            codes = list(ex.map(act, range(10)))
        print("codes", codes)
        assert codes.count(200) == 2 and codes.count(400) == 8
        lic = next(l for l in C.get(f"{API}/licences").json() if l["key"] == key)
        assert len(lic["activations"]) == 2
        assert admin.post(f"{API}/platform/licences/{lic['id']}/revoke").status_code == 200
        logs = C.get(f"{API}/audit-logs", params={"entity": "licence"}).json()
        assert any(l.get("action") == "revoke" for l in logs), logs


# --- GSTR-1 counts ---
class TestGSTR1Counts:
    def test_unique_counts(self, A):
        L = lmap(A)
        fy = A.get(f"{API}/financial-years").json()[0]
        month = fy["start_date"][:7]
        before = A.get(f"{API}/reports/gstr1", params={"month": month}).json()["summary"]
        reg = A.post(f"{API}/ledgers", json={"name": "TEST_R3B2B", "group": "sundry_debtors", "gstin": "27ABCDE1234F1Z5", "state": "Maharashtra"}).json()
        unreg = A.post(f"{API}/ledgers", json={"name": "TEST_R3B2C", "group": "sundry_debtors", "state": "Maharashtra"}).json()
        items = [{"hsn": "1", "qty": 1, "rate": 100, "gst_rate": 5}, {"hsn": "2", "qty": 1, "rate": 100, "gst_rate": 18}, {"hsn": "3", "qty": 1, "rate": 100, "gst_rate": 0}]
        vids = []
        for p in (reg, unreg):
            r = A.post(f"{API}/vouchers", json={"voucher_type": "sales", "date": f"{month}-20", "party_ledger_id": p["id"], "account_ledger_id": L["Sales"]["id"],
                                                "gst_type": "intra", "items": items})
            assert r.status_code == 200, r.text
            vids.append(r.json()["id"])
        s = A.get(f"{API}/reports/gstr1", params={"month": month}).json()["summary"]
        assert s["b2b_count"] - before["b2b_count"] == 1
        assert s["b2c_count"] - before["b2c_count"] == 1
        for vid in vids:
            A.post(f"{API}/vouchers/{vid}/cancel", json={"reason": "TEST cleanup"})


# --- Settings partial PUT ---
class TestSettingsPartial:
    def test_company_only_keeps_upi_bank(self, B):
        s = B.get(f"{API}/settings").json()
        full = {k: s.get(k, "") for k in ("company_name", "address", "state", "gstin", "phone", "email", "invoice_terms")}
        r = B.put(f"{API}/settings", json={**full, "gst_rates": s["gst_rates"], "upi_id": "test@okaxis", "bank_name": "SBI", "bank_account": "123456", "bank_ifsc": "sbin0000001", "invoice_terms": "TEST terms"})
        assert r.status_code == 200, r.text
        r = B.put(f"{API}/settings", json={"company_name": s["company_name"], "address": "TEST addr"})
        assert r.status_code == 200, r.text
        g = B.get(f"{API}/settings").json()
        assert g["upi_id"] == "test@okaxis" and g["bank_name"] == "SBI" and g["bank_account"] == "123456" and g["bank_ifsc"] == "SBIN0000001"
        assert g["invoice_terms"] == "TEST terms" and g["address"] == "TEST addr"
        assert g["gst_rates"] == s["gst_rates"]
