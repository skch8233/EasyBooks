# Round 6 (updated R8: list rows expose machines[]): one-PC lock (shop/activate, reset-pc), purchase emails (issue, resend, renewal), GST invoices
import os
import re
import sys
from datetime import date, timedelta

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN = {"email": "admin@easybooks.in", "password": "Admin@123"}
RAVI = {"email": "ravi@gupta.in", "password": "secret1"}
EMAIL = "delivered@resend.dev"
PC_A, PC_B = "A1B2-C3D4-E5F6-0789", "1111-2222-3333-4444"
ENV = dotenv_values("/app/backend/.env")
DB = MongoClient(ENV["MONGO_URL"])[ENV["DB_NAME"]]
INV_RE = re.compile(r"^HS/\d{4}-\d{2}/\d{5}$")
CREATED_KEYS = []

sys.path.insert(0, "/app/backend")
os.environ.setdefault("LICENCE_PUBLIC_KEY", ENV["LICENCE_PUBLIC_KEY"])
import licensing  # noqa: E402


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds)
    if r.status_code != 200:
        pytest.skip(f"login failed {creds['email']}: {r.status_code}")
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def sa():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def ravi():
    return _login(RAVI)


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    yield
    if CREATED_KEYS:
        DB.offline_licences.delete_many({"key": {"$in": CREATED_KEYS}})
        DB.hs_invoices.delete_many({"licence_key": {"$in": CREATED_KEYS}})


def _row(sa, key):
    return next(x for x in requests.get(f"{BASE_URL}/api/platform/offline-licences", headers=sa).json() if x["key"] == key)


def _activate(key, mid):
    return requests.post(f"{BASE_URL}/api/shop/activate", json={"key": key, "machine_id": mid})


class TestPcLockEmail:
    st = {}

    # Issue -> email + invoice
    def test_01_issue(self, sa):
        r = requests.post(f"{BASE_URL}/api/platform/offline-licences", headers=sa,
                          json={"plan": "offline_first", "name": "TEST_R6 Buyer", "email": EMAIL, "business_name": "TEST_R6 Biz", "gstin": "29abcde1234f1z5"})
        assert r.status_code == 200, r.text
        d = r.json()
        CREATED_KEYS.append(d["key"])
        assert d["code"] is None and d["machine_id"] is None
        assert INV_RE.match(d["invoice_no"]), d["invoice_no"]
        assert d["email_status"] == "sent" and d["email"] == EMAIL
        TestPcLockEmail.st.update(d)

    def test_02_list_and_invoice(self, sa):
        row = _row(sa, self.st["key"])
        assert row["machines"] == [] and row.get("code") is None
        assert row["last_invoice"] == self.st["invoice_no"]
        assert row["last_email"]["status"] == "sent" and row["last_email"]["to"] == EMAIL
        assert row["gstin"] == "29ABCDE1234F1Z5"
        inv = DB.hs_invoices.find_one({"number": self.st["invoice_no"]})
        assert inv and inv["licence_key"] == self.st["key"] and inv["source"] == "manual"
        assert [t[0] for t in inv["taxes"]] == ["CGST @9%", "SGST @9%"]
        assert [t[1] for t in inv["taxes"]] == [1080, 1080] and inv["total"] == 14160 and inv["base"] == 12000
        assert inv["buyer"]["gstin"] == "29ABCDE1234F1Z5" and inv["sac"] == "997331"
        assert inv["email"]["status"] == "sent"

    # Activation validation
    def test_03_activate_validation(self):
        k = self.st["key"]
        assert _activate(k, "ZZZZ-ZZZZ-ZZZZ-ZZZZ").status_code == 400
        assert _activate(k, "A1B2C3D4E5F60789").status_code == 400
        assert _activate(k, "abc").status_code in (400, 422)
        assert _activate("EB-ZZZZ-ZZZZ-ZZZZ-ZZZZ", PC_A).status_code == 404
        assert requests.post(f"{BASE_URL}/api/shop/activate", json={"key": k}).status_code == 422

    def test_04_first_pc_binds(self, sa):
        r = _activate(self.st["key"].lower(), PC_A.lower())
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["machine_id"] == PC_A and d["code"].startswith("EBOL1.")
        p = licensing.verify_code(d["code"])
        assert p["m"] == PC_A and p["k"] == self.st["key"] and p["e"] == self.st["expires"] and p["d"] == 8
        assert [m["id"] for m in _row(sa, self.st["key"])["machines"]] == [PC_A]

    def test_05_same_pc_again_and_other_pc_409(self):
        r = _activate(self.st["key"], PC_A)
        assert r.status_code == 200 and licensing.verify_code(r.json()["code"])["m"] == PC_A
        r = _activate(self.st["key"], PC_B)
        assert r.status_code == 409 and "another computer" in r.json()["detail"]

    # Reset PC
    def test_06_reset_auth(self, ravi):
        k = self.st["key"]
        assert requests.post(f"{BASE_URL}/api/platform/offline-licences/{k}/reset-pc", headers=ravi).status_code == 403
        assert requests.post(f"{BASE_URL}/api/platform/offline-licences/{k}/reset-pc").status_code in (401, 403)
        assert requests.post(f"{BASE_URL}/api/platform/offline-licences/{k}/resend", headers=ravi).status_code == 403

    def test_07_reset_then_new_pc(self, sa):
        k = self.st["key"]
        r = requests.post(f"{BASE_URL}/api/platform/offline-licences/{k}/reset-pc", headers=sa)
        assert r.status_code == 200 and r.json()["ok"] is True
        row = _row(sa, k)
        assert row["machines"] == [] and row.get("code") is None
        r = _activate(k, PC_B)
        assert r.status_code == 200 and licensing.verify_code(r.json()["code"])["m"] == PC_B
        assert _activate(k, PC_A).status_code == 409
        assert requests.post(f"{BASE_URL}/api/platform/offline-licences/EB-ZZZZ-ZZZZ-ZZZZ-ZZZZ/reset-pc", headers=sa).status_code == 404

    # Resend email
    def test_08_resend(self, sa):
        r = requests.post(f"{BASE_URL}/api/platform/offline-licences/{self.st['key']}/resend", headers=sa)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "sent" and r.json()["to"] == EMAIL
        assert requests.post(f"{BASE_URL}/api/platform/offline-licences/EB-ZZZZ-ZZZZ-ZZZZ-ZZZZ/resend", headers=sa).status_code == 404

    # Renewal on a bound licence
    def test_09_renewal_bound(self, sa):
        r = requests.post(f"{BASE_URL}/api/platform/offline-licences", headers=sa,
                          json={"plan": "offline_renewal", "name": "x", "email": EMAIL, "licence_key": self.st["key"]})
        assert r.status_code == 200, r.text
        d = r.json()
        exp = (date.fromisoformat(self.st["expires"]) + timedelta(days=365)).isoformat()
        assert d["key"] == self.st["key"] and d["expires"] == exp and d["machine_id"] == PC_B
        p = licensing.verify_code(d["code"])
        assert p["m"] == PC_B and p["e"] == exp and p["p"] == "offline_renewal"
        assert d["invoice_no"] != self.st["invoice_no"] and INV_RE.match(d["invoice_no"])
        assert d["email_status"] == "sent"
        inv = DB.hs_invoices.find_one({"number": d["invoice_no"]})
        assert inv["base"] == 6500 and inv["total"] == 7670
        row = _row(sa, d["key"])
        assert row["last_invoice"] == d["invoice_no"] and row["expires"] == exp

    # Expired licence cannot be activated (record inserted directly, no email)
    def test_10_expired_400(self):
        key = "EB-TR6X-TR6X-TR6X-TR6X"
        CREATED_KEYS.append(key)
        DB.offline_licences.insert_one({"id": "TEST_r6_exp", "key": key, "name": "TEST", "email": EMAIL, "business_name": "TEST", "plan": "offline_first",
                                        "expires": (date.today() - timedelta(days=1)).isoformat(), "code": None, "machine_id": None, "history": [], "created_at": "2020-01-01"})
        r = _activate(key, PC_A)
        assert r.status_code == 400 and "expired" in r.json()["detail"]
        # legacy row without machine_id field binds too
        DB.offline_licences.update_one({"key": key}, {"$set": {"expires": (date.today() + timedelta(days=5)).isoformat()}, "$unset": {"machine_id": ""}})
        assert _activate(key, PC_A).status_code == 200


# Tax split unit check (IGST when states differ)
class TestTaxes:
    def test_igst_cgst(self, monkeypatch):
        monkeypatch.setenv("MONGO_URL", ENV["MONGO_URL"])
        monkeypatch.setenv("DB_NAME", ENV["DB_NAME"])
        import emailer
        monkeypatch.setenv("SELLER_GSTIN", "27AAAAA0000A1Z5")
        assert emailer._taxes(12000, "29ABCDE1234F1Z5") == [("IGST @18%", 2160.0)]
        assert [n for n, _ in emailer._taxes(12000, "27ABCDE1234F1Z5")] == ["CGST @9%", "SGST @9%"]
        assert [n for n, _ in emailer._taxes(12000, "")] == ["CGST @9%", "SGST @9%"]
        monkeypatch.setenv("SELLER_GSTIN", "")
        assert [n for n, _ in emailer._taxes(12000, "29ABCDE1234F1Z5")] == ["CGST @9%", "SGST @9%"]
