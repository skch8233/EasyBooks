# Round 5: offline plans, shop (Razorpay disabled), superadmin offline licences, download info
import os
import base64
import json
from datetime import date, timedelta

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN = {"email": "admin@easybooks.in", "password": "Admin@123"}
RAVI = {"email": "ravi@gupta.in", "password": "secret1"}


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


CREATED_KEYS = []


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    """Delete only what this module created (offline licence keys + the test download link)."""
    yield
    from pymongo import MongoClient
    from dotenv import dotenv_values
    env = dotenv_values("/app/backend/.env")
    db = MongoClient(env["MONGO_URL"])[env["DB_NAME"]]
    if CREATED_KEYS:
        db.offline_licences.delete_many({"key": {"$in": CREATED_KEYS}})
        db.hs_invoices.delete_many({"licence_key": {"$in": CREATED_KEYS}})
    db.app_releases.delete_many({"id": "offline-windows", "url": "https://example.com/TEST_EasyBooks.exe"})


def _payload(code):
    body = code.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))


# Public plans
class TestPublicPlans:
    def test_offline_plans(self):
        r = requests.get(f"{BASE_URL}/api/public/plans")
        assert r.status_code == 200
        d = r.json()
        op = {p["key"]: p for p in d["offline_plans"]}
        assert op["offline_first"]["price"] == 12000 and op["offline_first"]["total"] == 14160
        assert op["offline_renewal"]["price"] == 6500 and op["offline_renewal"]["total"] == 7670
        assert op["offline_first"]["gst"] == 2160
        assert d["payments_enabled"] is False
        assert len(d["plans"]) >= 1


# Shop without Razorpay
class TestShopDisabled:
    def test_order_503(self):
        r = requests.post(f"{BASE_URL}/api/shop/order", json={"plan": "offline_first", "name": "TEST_buyer", "email": "test_buyer@example.com"})
        assert r.status_code == 503
        assert "not enabled" in r.json()["detail"]

    def test_order_renewal_503(self):
        r = requests.post(f"{BASE_URL}/api/shop/order", json={"plan": "offline_renewal", "name": "TEST_b", "email": "t@example.com", "licence_key": "bad"})
        assert r.status_code == 503

    def test_order_invalid_plan_422(self):
        r = requests.post(f"{BASE_URL}/api/shop/order", json={"plan": "nope", "name": "x", "email": "t@example.com"})
        assert r.status_code == 422

    def test_verify_503(self):
        r = requests.post(f"{BASE_URL}/api/shop/verify", json={"razorpay_order_id": "o", "razorpay_payment_id": "p", "razorpay_signature": "s"})
        assert r.status_code == 503


# Superadmin offline licences
class TestOfflineLicences:
    state = {}

    def test_issue_first(self, sa):
        r = requests.post(f"{BASE_URL}/api/platform/offline-licences", headers=sa,
                          json={"plan": "offline_first", "name": "TEST_Offline Buyer", "email": "delivered@resend.dev", "business_name": "TEST_Off Biz"})
        assert r.status_code == 200, r.text
        d = r.json()
        import re
        assert re.match(r"^EB-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$", d["key"])
        assert d["code"] is None  # Round 6: code only after PC binding
        assert d["expires"] == (date.today() + timedelta(days=365)).isoformat()
        assert d["business_name"] == "TEST_Off Biz"
        TestOfflineLicences.state.update(d)
        CREATED_KEYS.append(d["key"])

    def test_list(self, sa):
        r = requests.get(f"{BASE_URL}/api/platform/offline-licences", headers=sa)
        assert r.status_code == 200
        rows = r.json()
        row = next(x for x in rows if x["key"] == self.state["key"])
        assert row["email"] == "delivered@resend.dev"
        assert "history" not in row and "_id" not in row

    def test_renew_extends(self, sa):
        r = requests.post(f"{BASE_URL}/api/platform/offline-licences", headers=sa,
                          json={"plan": "offline_renewal", "name": "x", "email": "delivered@resend.dev", "licence_key": self.state["key"].lower()})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["key"] == self.state["key"]
        exp = date.fromisoformat(self.state["expires"]) + timedelta(days=365)
        assert d["expires"] == exp.isoformat()
        assert d["name"] == "TEST_Offline Buyer"  # original name kept
        assert d["code"] is None and d["plan"] == "offline_renewal"
        rows = requests.get(f"{BASE_URL}/api/platform/offline-licences", headers=sa).json()
        assert next(x for x in rows if x["key"] == d["key"])["expires"] == exp.isoformat()

    def test_renew_unknown_404(self, sa):
        r = requests.post(f"{BASE_URL}/api/platform/offline-licences", headers=sa,
                          json={"plan": "offline_renewal", "name": "x", "email": "t@example.com", "licence_key": "EB-ZZZZ-ZZZZ-ZZZZ-ZZZZ"})
        assert r.status_code == 404

    def test_non_super_403(self, ravi):
        r = requests.post(f"{BASE_URL}/api/platform/offline-licences", headers=ravi,
                          json={"plan": "offline_first", "name": "x", "email": "t@example.com"})
        assert r.status_code == 403
        assert requests.get(f"{BASE_URL}/api/platform/offline-licences", headers=ravi).status_code == 403

    def test_no_auth_401(self):
        assert requests.get(f"{BASE_URL}/api/platform/offline-licences").status_code in (401, 403)

    def test_online_offline_endpoints(self, sa):
        r = requests.get(f"{BASE_URL}/api/offline/status")
        assert r.status_code == 200 and r.json()["offline"] is False
        r = requests.post(f"{BASE_URL}/api/offline/licence", headers=sa, json={"code": "EBOL1.x.y"})
        assert r.status_code == 400 and "offline version" in r.json()["detail"]


# Download info
class TestDownload:
    def test_non_http_400(self, sa):
        r = requests.put(f"{BASE_URL}/api/platform/download", headers=sa, json={"url": "ftp://example.com/x.exe"})
        assert r.status_code == 400

    def test_non_super_403(self, ravi):
        r = requests.put(f"{BASE_URL}/api/platform/download", headers=ravi, json={"url": "https://example.com/x.exe"})
        assert r.status_code == 403

    def test_set_and_get(self, sa):
        body = {"url": "https://example.com/TEST_EasyBooks.exe", "version": "1.2.3", "size": "80 MB", "notes": "TEST"}
        r = requests.put(f"{BASE_URL}/api/platform/download", headers=sa, json=body)
        assert r.status_code == 200
        assert r.json()["url"] == body["url"]
        g = requests.get(f"{BASE_URL}/api/shop/download").json()
        assert g["url"] == body["url"] and g["version"] == "1.2.3" and g["size"] == "80 MB"
        assert "_id" not in g
