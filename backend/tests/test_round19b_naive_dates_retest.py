# Round 14 Part 2 retest (iteration_29): naive dates across super/billing/data APIs, extend month/year/days from naive sub end, plan users_label, expired trial label
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
ENV = {k: v.strip('"') for k, v in (l.strip().split("=", 1) for l in open("/app/backend/.env") if "=" in l)}
DB = MongoClient(ENV["MONGO_URL"])[ENV["DB_NAME"]]
CREATED = []


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return s


@pytest.fixture(scope="module")
def sup():
    return login("admin@easybooks.in", "Admin@123")


def new_org():
    e = f"test_r19b_{uuid.uuid4().hex[:8]}@ex.in"
    r = requests.post(f"{API}/auth/signup", json={"industry_type": "wholesale", "industry_mode": "complete", "business_name": f"TEST_R19B {e[10:16]}",
                                                  "name": "TEST Owner", "email": e, "password": "secret12"})
    assert r.status_code == 200, r.text
    bid = r.json()["user"]["business_id"]
    CREATED.append(bid)
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return bid, s


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    for bid in CREATED:
        for c in ("users", "settings", "financial_years", "ledgers", "vouchers", "audit_logs", "subscription_ledger", "support_access_log"):
            DB[c].delete_many({"business_id": bid})
        DB.businesses.delete_one({"id": bid})


def naive(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).replace(tzinfo=None).isoformat()


@pytest.mark.parametrize("field,days", [("trial_ends", 10), ("trial_ends", -3), ("trial_ends", -20), ("subscription_ends", 50), ("subscription_ends", -30)])
def test_naive_dates_all_apis_200(sup, field, days):
    bid, s = new_org()
    upd = {field: naive(days)}
    if field == "subscription_ends":
        upd["plan"] = "wholesale_complete"
    DB.businesses.update_one({"id": bid}, {"$set": upd})
    for url in ("/super/orgs", "/super/overview", f"/super/orgs?q=TEST_R19B"):
        r = sup.get(API + url)
        assert r.status_code == 200, (url, r.text[:200])
    org = next(o for o in sup.get(f"{API}/super/orgs").json() if o["id"] == bid)
    r = s.get(f"{API}/billing/status")
    assert r.status_code == 200, r.text[:200]
    st = r.json()
    exp_status = ("trial" if field == "trial_ends" else "active") if days > 0 else "expired"
    assert org["status"] == exp_status and st["status"] == exp_status, (org, st)
    if days > 0:
        assert days - 1 <= st["days_left"] <= days + 1
    if days == -20:
        assert st.get("locked") is True
        assert org["plan_label"] == "Free Trial (expired)"
    if days == -3:
        assert st.get("grace") is True and not st.get("locked")
        assert org["plan_label"] == "Free Trial (expired)"
    # data APIs
    r = s.get(f"{API}/ledgers")
    assert r.status_code in (200, 423), r.text[:200]
    if days > -7:
        assert r.status_code == 200


@pytest.mark.parametrize("period,days,exp", [("month", 0, 30), ("year", 0, 365), ("days", 45, 45)])
def test_extend_from_naive_sub_end(sup, period, days, exp):
    bid, _ = new_org()
    base = datetime.now(timezone.utc) + timedelta(days=60)
    DB.businesses.update_one({"id": bid}, {"$set": {"plan": "wholesale_complete", "subscription_ends": base.replace(tzinfo=None).isoformat()}})
    r = sup.post(f"{API}/super/orgs/{bid}/extend", json={"period": period, "days": days, "method": "None"})
    assert r.status_code == 200, r.text[:200]
    new = datetime.fromisoformat(r.json()["new_expiry"])
    assert abs((new - base).total_seconds() - exp * 86400) < 120, (new, base)
    b = DB.businesses.find_one({"id": bid})
    assert b["subscription_ends"] == r.json()["new_expiry"]


def test_multi_plan_users_label_kept_after_edit(sup):
    key = "retail_complete_multi"
    orig = next(p for p in sup.get(f"{API}/super/plans").json() if p["key"] == key)
    assert orig["price"] == 8500 and orig["max_users"] == 8, orig
    try:
        r = sup.put(f"{API}/super/plans/{key}", json={"name": orig["name"], "price": 8600, "monthly_price": 0, "max_users": 8, "active": True, "modules": []})
        assert r.status_code == 200
        assert r.json()["users_label"] == "3 to 8 users", r.json()
        p = next(p for p in sup.get(f"{API}/super/plans").json() if p["key"] == key)
        assert p["users_label"] == "3 to 8 users"
    finally:
        DB.plan_settings.delete_many({"key": key})
