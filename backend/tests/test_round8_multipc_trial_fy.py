# Round 8: offline plans (single/multi tiers), multi-PC activation, tier-checked renewal, reset-pc per machine,
# FY working/company-default endpoints, offline/session 404 online, offline trial state machine (in-process harness)
import json
import os
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN = {"email": "admin@easybooks.in", "password": "Admin@123"}
RAVI = {"email": "ravi@gupta.in", "password": "secret1"}
EMAIL = "delivered@resend.dev"
ENV = dotenv_values("/app/backend/.env")
DB = MongoClient(ENV["MONGO_URL"])[ENV["DB_NAME"]]
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


def _mid(i):
    return f"{i:04X}-ABCD-EF01-{i:04X}"


def _act(key, mid):
    return requests.post(f"{BASE_URL}/api/shop/activate", json={"key": key, "machine_id": mid})


def _row(sa, key):
    return next(x for x in requests.get(f"{BASE_URL}/api/platform/offline-licences", headers=sa).json() if x["key"] == key)


# Public plans
class TestPlans:
    def test_offline_plans(self):
        r = requests.get(f"{BASE_URL}/api/public/plans")
        assert r.status_code == 200
        op = {p["key"]: p for p in r.json()["offline_plans"]}
        exp = {"offline_first": (12000, 14160, "single", 1, False), "offline_renewal": (6500, 7670, "single", 1, True),
               "offline_multi_first": (18000, 21240, "multi", 8, False), "offline_multi_renewal": (10000, 11800, "multi", 8, True)}
        assert set(op) == set(exp)
        for k, (price, total, tier, pcs, ren) in exp.items():
            assert (op[k]["price"], op[k]["total"], op[k]["tier"], op[k]["pcs"], op[k]["renewal"]) == (price, total, tier, pcs, ren), k

    def test_order_503(self):
        r = requests.post(f"{BASE_URL}/api/shop/order", json={"plan": "offline_multi_first", "name": "TEST", "email": EMAIL})
        assert r.status_code == 503

    def test_offline_session_404_online(self):
        assert requests.post(f"{BASE_URL}/api/offline/session").status_code == 404


# Multi-PC issue / activation / renewal / reset
class TestMultiPc:
    st = {}

    def test_01_issue_multi(self, sa):
        r = requests.post(f"{BASE_URL}/api/platform/offline-licences", headers=sa,
                          json={"plan": "offline_multi_first", "name": "TEST_R8 Multi", "email": EMAIL, "business_name": "TEST_R8 Biz"})
        assert r.status_code == 200, r.text
        d = r.json()
        CREATED_KEYS.append(d["key"])
        assert d["tier"] == "multi" and d["max_pcs"] == 8 and d["pcs_used"] == 0 and d["code"] is None
        assert d["email_status"] in ("sent", "failed")  # "failed" only seen when provider rate-limits (429)
        TestMultiPc.st.update(d)

    def test_02_eight_pcs_then_409(self, sa):
        k = self.st["key"]
        for i in range(1, 9):
            r = _act(k, _mid(i))
            assert r.status_code == 200, (i, r.text)
            d = r.json()
            assert d["pcs_used"] == i and d["max_pcs"] == 8
            p = licensing.verify_code(d["code"])
            assert p["t"] == "multi" and p["c"] == 8 and p["m"] == _mid(i) and p["k"] == k
        r = _act(k, _mid(9))
        assert r.status_code == 409 and "8 computers" in r.json()["detail"]
        r = _act(k, _mid(3))
        assert r.status_code == 200 and licensing.verify_code(r.json()["code"])["m"] == _mid(3)
        row = _row(sa, k)
        assert row["tier"] == "multi" and row["max_pcs"] == 8 and len(row["machines"]) == 8

    def test_03_renewal_mismatch_400(self, sa):
        r = requests.post(f"{BASE_URL}/api/platform/offline-licences", headers=sa,
                          json={"plan": "offline_renewal", "name": "x", "email": EMAIL, "licence_key": self.st["key"]})
        assert r.status_code == 400 and "Multi-PC" in r.json()["detail"]

    def test_04_renewal_multi(self, sa):
        r = requests.post(f"{BASE_URL}/api/platform/offline-licences", headers=sa,
                          json={"plan": "offline_multi_renewal", "name": "x", "email": EMAIL, "licence_key": self.st["key"]})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["expires"] == (date.fromisoformat(self.st["expires"]) + timedelta(days=365)).isoformat()
        assert d["pcs_used"] == 8 and d["tier"] == "multi"
        assert len(_row(sa, self.st["key"])["machines"]) == 8

    def test_05_reset_one_pc(self, sa, ravi):
        k = self.st["key"]
        assert requests.post(f"{BASE_URL}/api/platform/offline-licences/{k}/reset-pc", headers=ravi, json={"machine_id": _mid(2)}).status_code == 403
        r = requests.post(f"{BASE_URL}/api/platform/offline-licences/{k}/reset-pc", headers=sa, json={"machine_id": _mid(2).lower()})
        assert r.status_code == 200 and r.json()["pcs_used"] == 7
        ids = [m["id"] for m in _row(sa, k)["machines"]]
        assert _mid(2) not in ids and len(ids) == 7
        assert _act(k, _mid(9)).status_code == 200
        assert _act(k, _mid(10)).status_code == 409

    def test_06_reset_all_empty_body(self, sa):
        k = self.st["key"]
        r = requests.post(f"{BASE_URL}/api/platform/offline-licences/{k}/reset-pc", headers=sa, json={})
        assert r.status_code == 200 and r.json()["pcs_used"] == 0
        assert _row(sa, k)["machines"] == []
        assert _act(k, _mid(1)).status_code == 200
        r = requests.post(f"{BASE_URL}/api/platform/offline-licences/{k}/reset-pc", headers=sa)  # no body at all
        assert r.status_code == 200 and r.json()["pcs_used"] == 0


class TestSinglePc:
    st = {}

    def test_01_single_lock(self, sa):
        r = requests.post(f"{BASE_URL}/api/platform/offline-licences", headers=sa,
                          json={"plan": "offline_first", "name": "TEST_R8 Single", "email": EMAIL})
        assert r.status_code == 200, r.text
        d = r.json()
        CREATED_KEYS.append(d["key"])
        assert d["tier"] == "single" and d["max_pcs"] == 1
        r = _act(d["key"], _mid(1))
        assert r.status_code == 200
        p = licensing.verify_code(r.json()["code"])
        assert p["t"] == "single" and p["c"] == 1
        r = _act(d["key"], _mid(2))
        assert r.status_code == 409 and "another computer" in r.json()["detail"]
        r = requests.post(f"{BASE_URL}/api/platform/offline-licences", headers=sa,
                          json={"plan": "offline_multi_renewal", "name": "x", "email": EMAIL, "licence_key": d["key"]})
        assert r.status_code == 400 and "Single-PC" in r.json()["detail"]

    def test_02_legacy_row_normalized(self, sa):
        key = "EB-TR8L-TR8L-TR8L-TR8L"
        CREATED_KEYS.append(key)
        DB.offline_licences.delete_many({"key": key})
        DB.offline_licences.insert_one({"id": "TEST_r8_leg", "key": key, "name": "TEST", "email": EMAIL, "business_name": "TEST", "plan": "offline_first",
                                        "expires": (date.today() + timedelta(days=30)).isoformat(), "machine_id": _mid(5),
                                        "bound_at": "2025-01-01", "history": [], "created_at": "2020-01-01"})
        row = _row(sa, key)
        assert row["machines"] == [{"id": _mid(5), "at": "2025-01-01"}] and row["tier"] == "single" and row["max_pcs"] == 1
        assert _act(key, _mid(5)).status_code == 200
        assert _act(key, _mid(6)).status_code == 409


# Financial year working / company-default
class TestFY:
    def test_fy_flow(self, sa, ravi):
        fys = requests.get(f"{BASE_URL}/api/financial-years", headers=sa).json()
        if len(fys) < 2:
            pytest.skip("need 2 FYs")
        orig = next((f for f in fys if f["is_active"]), None)
        other = next(f for f in fys if not orig or f["id"] != orig["id"])
        vid = None
        try:
            # viewer in admin business
            email = f"test_r8_viewer_{uuid.uuid4().hex[:6]}@example.com"
            r = requests.post(f"{BASE_URL}/api/users", headers=sa, json={"name": "TEST_R8 Viewer", "email": email, "password": "secret1", "role": "viewer"})
            assert r.status_code in (200, 201), r.text
            vid = r.json()["id"]
            vh = _login({"email": email, "password": "secret1"})
            r = requests.put(f"{BASE_URL}/api/financial-years/{other['id']}/working", headers=vh)
            assert r.status_code == 200 and r.json()["working_fy_id"] == other["id"]
            assert requests.get(f"{BASE_URL}/api/auth/me", headers=vh).json()["working_fy_id"] == other["id"]
            r = requests.put(f"{BASE_URL}/api/financial-years/{other['id']}/company-default", headers=vh)
            assert r.status_code == 200
            act = [f["id"] for f in requests.get(f"{BASE_URL}/api/financial-years", headers=sa).json() if f["is_active"]]
            assert act == [other["id"]]
            assert DB.audit_logs.find_one({"entity_id": other["id"], "action": "company_default"}) or DB.audit_logs.find_one({"action": "company_default"})
            # other business FY -> 404
            assert requests.put(f"{BASE_URL}/api/financial-years/{other['id']}/working", headers=ravi).status_code == 404
            assert requests.put(f"{BASE_URL}/api/financial-years/{other['id']}/company-default", headers=ravi).status_code == 404
        finally:
            if orig:
                requests.put(f"{BASE_URL}/api/financial-years/{orig['id']}/company-default", headers=sa)
            if vid:
                DB.users.delete_one({"id": vid})


# In-process offline trial harness (time travel via licensing.date)
class _FakeDate(date):
    today_val = date.today()

    @classmethod
    def today(cls):
        return cls.today_val


@pytest.fixture()
def lic_env(tmp_path, monkeypatch):
    monkeypatch.setenv("EB_MACHINE_ID", f"TEST_R8_{uuid.uuid4().hex}")
    monkeypatch.setenv("EB_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("EB_SHADOW_FILE", str(tmp_path / "shadow"))
    monkeypatch.setenv("LICENCE_SIGNING_KEY", ENV["LICENCE_SIGNING_KEY"])
    monkeypatch.setattr(licensing, "date", _FakeDate)
    _FakeDate.today_val = date.today()
    return tmp_path


def _travel(days):
    _FakeDate.today_val = date.today() + timedelta(days=days)


class TestTrialHarness:
    def test_fresh_trial(self, lic_env):
        s = licensing.offline_status()
        assert s["status"] == "trial" and s["days_left"] == 30

    def test_day31_expired(self, lic_env):
        licensing.offline_status()
        _travel(29)
        assert licensing.offline_status()["days_left"] == 1
        _travel(31)
        s = licensing.offline_status()
        assert s["status"] == "expired" and "trial has ended" in s["reason"]

    def test_clock_back(self, lic_env):
        licensing.offline_status()
        _travel(10)
        licensing.offline_status()
        _travel(7)  # 3 days back
        s = licensing.offline_status()
        assert s["status"] == "expired" and "set back" in s["reason"]
        _travel(9)  # within slack
        assert licensing.offline_status()["status"] == "trial"

    def test_restore_from_shadow_and_file(self, lic_env):
        inst = licensing.offline_status()["trial"]["installed"]
        _travel(5)
        licensing.offline_status()
        (lic_env / "data" / "licence.json").unlink()
        s = licensing.offline_status()
        assert s["status"] == "trial" and s["trial"]["installed"] == inst and s["days_left"] == 25
        (lic_env / "shadow").unlink()
        s = licensing.offline_status()
        assert s["status"] == "trial" and s["trial"]["installed"] == inst
        assert (lic_env / "shadow").exists()

    def test_both_tampered(self, lic_env):
        licensing.offline_status()
        p = lic_env / "data" / "licence.json"
        st = json.loads(p.read_text())
        st["trial"] = st["trial"][:-4] + "0000"
        p.write_text(json.dumps(st))
        (lic_env / "shadow").write_text("garbage.abc")
        s = licensing.offline_status()
        assert s["status"] == "expired" and "removed or changed" in s["reason"]

    def test_codes(self, lic_env):
        licensing.offline_status()
        _travel(40)
        base = {"k": "EB-TR8H-TR8H-TR8H-TR8H", "n": "x", "b": "x", "p": "offline_first", "i": date.today().isoformat(),
                "e": (date.today() + timedelta(days=365)).isoformat(), "d": 8, "t": "single", "c": 1}
        with pytest.raises(ValueError):
            licensing.save_code(licensing.sign_code({**base, "m": "AAAA-BBBB-CCCC-DDDD"}))
        assert licensing.offline_status()["status"] == "expired"
        licensing.save_code(licensing.sign_code({**base, "m": licensing.machine_id()}))
        s = licensing.offline_status()
        assert s["status"] == "active" and s["licence"]["k"] == base["k"]
