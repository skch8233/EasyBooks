# Round 14 Part 2 - Super Admin (overview, orgs, extend fixes 1-5, config, suspend/lock/grace, support view, plans, payments)
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"


def _env():
    d = {}
    for line in open("/app/backend/.env"):
        if "=" in line:
            k, v = line.strip().split("=", 1)
            d[k] = v.strip('"')
    return d


ENV = _env()
DB = MongoClient(ENV["MONGO_URL"])[ENV["DB_NAME"]]
CREATED = []  # business ids created by this module
CREATED_PLANS = []


def login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return s


@pytest.fixture(scope="module")
def sup():
    return login("admin@easybooks.in", "Admin@123")


def new_org(industry="wholesale", mode="complete"):
    e = f"test_sa_{uuid.uuid4().hex[:10]}@ex.in"
    r = requests.post(f"{API}/auth/signup", json={"industry_type": industry, "industry_mode": mode, "business_name": f"TEST_SA {industry} {e[8:14]}",
                                                  "name": "TEST Owner", "email": e, "password": "secret12"})
    assert r.status_code == 200, r.text
    bid = r.json()["user"]["business_id"]
    CREATED.append(bid)
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return bid, s


def iso(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    yield
    for bid in CREATED:
        for c in ("users", "settings", "financial_years", "ledgers", "vouchers", "audit_logs", "subscription_ledger", "support_access_log"):
            DB[c].delete_many({"business_id": bid})
        DB.businesses.delete_one({"id": bid})
    for k in CREATED_PLANS:
        DB.plan_settings.delete_many({"key": k})


# ---------- access ----------
def test_non_super_403():
    s = login("ravi@gupta.in", "secret1")
    for p in ("overview", "orgs", "plans", "payments", "support-log"):
        assert s.get(f"{API}/super/{p}").status_code == 403, p


def test_overview_shape(sup):
    d = sup.get(f"{API}/super/overview").json()
    for k in ("total_orgs", "active_paid", "expiring_7d", "revenue_month", "revenue_year", "industries"):
        assert k in d
    assert len(d["industries"]) == 5


def test_demo_hidden_and_filters(sup):
    rows = sup.get(f"{API}/super/orgs").json()
    demo_ids = {b["id"] for b in DB.businesses.find({"demo": True}, {"id": 1})}
    assert not demo_ids & {r["id"] for r in rows}
    bid, _ = new_org("hospital")
    name = DB.businesses.find_one({"id": bid})["name"]
    r = sup.get(f"{API}/super/orgs", params={"q": name}).json()
    assert [x["id"] for x in r] == [bid]
    assert all(x["industry_type"] == "hospital" for x in sup.get(f"{API}/super/orgs", params={"industry": "hospital"}).json())
    assert all(x["status"] == "trial" for x in sup.get(f"{API}/super/orgs", params={"status": "trial"}).json())


# ---------- fix 3 ----------
def test_expiring_excludes_no_end_date(sup):
    before = sup.get(f"{API}/super/overview").json()["expiring_7d"]
    bid, _ = new_org()
    DB.businesses.update_one({"id": bid}, {"$set": {"trial_ends": iso(3)}})
    assert sup.get(f"{API}/super/overview").json()["expiring_7d"] == before + 1
    DB.businesses.update_one({"id": bid}, {"$set": {"trial_ends": iso(40)}})
    assert sup.get(f"{API}/super/overview").json()["expiring_7d"] == before


# ---------- fix 1 ----------
def test_extend_blank_reference_rejected(sup):
    bid, _ = new_org()
    b0 = DB.businesses.find_one({"id": bid}, {"_id": 0})
    r = sup.post(f"{API}/super/orgs/{bid}/extend", json={"period": "year", "amount": 5000, "method": "UPI", "reference": "  "})
    assert r.status_code == 400
    b1 = DB.businesses.find_one({"id": bid}, {"_id": 0})
    assert b1.get("subscription_ends") == b0.get("subscription_ends") and b1.get("plan") == b0.get("plan")
    assert DB.subscription_ledger.count_documents({"business_id": bid}) == 0
    # cash with blank ref ok
    r = sup.post(f"{API}/super/orgs/{bid}/extend", json={"period": "month", "amount": 500, "method": "Cash"})
    assert r.status_code == 200, r.text
    assert DB.subscription_ledger.count_documents({"business_id": bid}) == 1


# ---------- fix 2 ----------
def test_trial14_missing_trial_ends(sup):
    bid, _ = new_org()
    DB.businesses.update_one({"id": bid}, {"$unset": {"trial_ends": ""}})
    r = sup.post(f"{API}/super/orgs/{bid}/extend", json={"period": "trial14", "method": "None"})
    assert r.status_code == 200, r.text
    assert r.json()["new_expiry"] > iso(13)


def test_trial14_naive_trial_ends(sup):
    bid, _ = new_org()
    DB.businesses.update_one({"id": bid}, {"$set": {"trial_ends": "2027-03-01T00:00:00"}})
    r = sup.post(f"{API}/super/orgs/{bid}/extend", json={"period": "trial14", "method": "None"})
    assert r.status_code == 200, r.text
    assert r.json()["new_expiry"].startswith("2027-03-15")


def test_year_extend_naive_subscription_ends(sup):
    bid, _ = new_org()
    DB.businesses.update_one({"id": bid}, {"$set": {"plan": "wholesale_complete", "subscription_ends": "2027-03-01T00:00:00"}})
    r = sup.post(f"{API}/super/orgs/{bid}/extend", json={"period": "month", "method": "None"})
    DB.businesses.update_one({"id": bid}, {"$set": {"subscription_ends": iso(100)}})
    assert r.status_code == 200, r.text[:200]


def test_orgs_list_survives_naive_trial_ends(sup):
    # status_of/_days_left with a naive ISO stored date should not crash the list
    bid, _ = new_org()
    DB.businesses.update_one({"id": bid}, {"$set": {"trial_ends": "2026-12-01T00:00:00"}})
    r = sup.get(f"{API}/super/orgs")
    DB.businesses.update_one({"id": bid}, {"$set": {"trial_ends": iso(30)}})
    assert r.status_code == 200, r.text[:200]


# ---------- fix 5 ----------
def test_trial14_expired_paid_and_active_paid(sup):
    bid, _ = new_org()
    DB.businesses.update_one({"id": bid}, {"$set": {"plan": "wholesale_complete", "subscription_ends": iso(-20)}})
    r = sup.post(f"{API}/super/orgs/{bid}/extend", json={"period": "trial14", "method": "None"})
    assert r.status_code == 200, r.text
    b = DB.businesses.find_one({"id": bid})
    assert iso(13.9) < b["subscription_ends"] < iso(14.1)
    st = sup.get(f"{API}/super/orgs", params={"q": b["name"]}).json()[0]
    assert st["status"] == "active"
    # now active paid -> refused
    r = sup.post(f"{API}/super/orgs/{bid}/extend", json={"period": "trial14", "method": "None"})
    assert r.status_code == 400
    assert DB.businesses.find_one({"id": bid})["subscription_ends"] == b["subscription_ends"]


# ---------- fix 4 ----------
def test_extend_suspended_requires_flag(sup):
    bid, s = new_org()
    assert sup.post(f"{API}/super/orgs/{bid}/suspend", json={"reason": "TEST nonpayment"}).status_code == 200
    assert s.get(f"{API}/ledgers").status_code == 423
    r = sup.post(f"{API}/super/orgs/{bid}/extend", json={"period": "year", "amount": 1000, "method": "UPI", "reference": "UTR1"})
    assert r.status_code == 400
    assert DB.businesses.find_one({"id": bid}).get("suspended")
    assert DB.subscription_ledger.count_documents({"business_id": bid}) == 0
    r = sup.post(f"{API}/super/orgs/{bid}/extend", json={"period": "year", "amount": 1000, "method": "UPI", "reference": "UTR1", "lift_suspension": True})
    assert r.status_code == 200, r.text
    assert r.json()["suspension_lifted"] is True
    assert not DB.businesses.find_one({"id": bid}).get("suspended")
    acts = [a.get("action") for a in DB.audit_logs.find({"business_id": bid})]
    assert "unsuspend" in acts
    ext = DB.audit_logs.find_one({"business_id": bid, "action": "manual_extend"})
    assert "suspension lifted" in (ext.get("note") or "")
    assert s.get(f"{API}/ledgers").status_code == 200


def test_lift_flag_on_non_suspended_is_false(sup):
    bid, _ = new_org()
    r = sup.post(f"{API}/super/orgs/{bid}/extend", json={"period": "month", "method": "None", "lift_suspension": True})
    assert r.status_code == 200 and r.json()["suspension_lifted"] is False


def test_custom_days_and_bounds(sup):
    bid, _ = new_org()
    assert sup.post(f"{API}/super/orgs/{bid}/extend", json={"period": "days", "days": 0, "method": "None"}).status_code == 400
    r = sup.post(f"{API}/super/orgs/{bid}/extend", json={"period": "days", "days": 45, "method": "None", "plan": "wholesale_complete_multi"})
    assert r.status_code == 200 and r.json()["days"] == 45
    assert sup.post(f"{API}/super/orgs/{bid}/extend", json={"period": "month", "method": "None", "plan": "retail_complete"}).status_code in (200, 400)


# ---------- suspend / reactivate / grace / lock ----------
def test_suspend_reactivate(sup):
    bid, s = new_org()
    sup.post(f"{API}/super/orgs/{bid}/suspend", json={"reason": "TEST"})
    r = s.get(f"{API}/ledgers")
    assert r.status_code == 423 and "suspended" in r.json()["detail"].lower()
    assert s.get(f"{API}/billing/status").json()["status"] == "suspended"
    assert sup.post(f"{API}/super/orgs/{bid}/reactivate").status_code == 200
    assert s.get(f"{API}/ledgers").status_code == 200


def test_grace_and_lock(sup):
    bid, s = new_org()
    DB.businesses.update_one({"id": bid}, {"$set": {"trial_ends": iso(-3)}})
    assert s.get(f"{API}/ledgers").status_code == 200
    w = s.post(f"{API}/ledgers", json={"name": "TEST_L", "group": "sundry_debtor"})
    assert w.status_code == 402, w.text
    DB.businesses.update_one({"id": bid}, {"$set": {"trial_ends": iso(-8)}})
    r = s.get(f"{API}/ledgers")
    assert r.status_code == 423 and "Subscription Expired" in r.json()["detail"]
    assert s.get(f"{API}/billing/status").status_code == 200


# ---------- config ----------
def test_config_updates_billing_status(sup):
    bid, s = new_org("wholesale", "billing")
    r = sup.put(f"{API}/super/orgs/{bid}/config", json={"industry_type": "retail", "industry_mode": "complete", "plan": "retail_complete_multi",
                                                        "max_users_override": 5, "erp": True})
    assert r.status_code == 200, r.text
    b = s.get(f"{API}/billing/status").json()
    assert b["business"]["industry_type"] == "retail" and b["business"]["plan"] == "retail_complete_multi"
    assert b["max_users"] == 5 and b["business"]["modules"]["erp"] is True
    assert sup.put(f"{API}/super/orgs/{bid}/config", json={"industry_type": "retail", "plan": "nope"}).status_code == 400


# ---------- support view ----------
def test_support_view(sup):
    bid, _ = new_org()
    assert sup.post(f"{API}/super/orgs/{bid}/support-view", json={"reason": ""}).status_code == 422
    r = sup.post(f"{API}/super/orgs/{bid}/support-view", json={"reason": "TEST ticket 42"})
    assert r.status_code == 200
    sv = requests.Session()
    sv.headers["Authorization"] = f"Bearer {r.json()['token']}"
    me = sv.get(f"{API}/auth/me").json()
    assert me["business_id"] == bid and me["role"] == "viewer" and me.get("support_view")
    assert sv.get(f"{API}/ledgers").status_code == 200
    assert sv.post(f"{API}/ledgers", json={"name": "TEST_SV", "group": "sundry_debtor"}).status_code == 403
    log = sup.get(f"{API}/super/support-log").json()
    assert any(l["business_id"] == bid and l["reason"] == "TEST ticket 42" for l in log)


# ---------- plans ----------
def test_edit_plan_price_and_restore(sup):
    key = "retail_complete_multi"
    orig = next(p for p in sup.get(f"{API}/super/plans").json() if p["key"] == key)
    try:
        r = sup.put(f"{API}/super/plans/{key}", json={"name": orig["name"], "price": 9100, "monthly_price": 0, "max_users": 8, "active": True, "modules": []})
        assert r.status_code == 200 and r.json()["gst"] == 1638 and r.json()["total"] == 10738
        pub = requests.get(f"{API}/public/industries").json()["industries"]["retail"]["plans"]
        assert next(p for p in pub if p["key"] == key)["price"] == 9100
    finally:
        DB.plan_settings.delete_many({"key": key})
        sup.put(f"{API}/super/plans/{key}", json={"name": orig["name"], "price": orig["price"], "monthly_price": 0, "max_users": orig["max_users"], "active": True, "modules": []})
        DB.plan_settings.delete_many({"key": key})


def test_create_custom_plan(sup):
    key = f"test_plan_{uuid.uuid4().hex[:6]}"
    CREATED_PLANS.append(key)
    r = sup.post(f"{API}/super/plans", json={"key": key, "name": "TEST College Pro", "industry": "college", "mode": "complete", "price": 20000, "max_users": 20})
    assert r.status_code == 200, r.text
    assert r.json()["gst"] == 3600
    assert any(p["key"] == key for p in sup.get(f"{API}/super/plans").json())
    assert sup.post(f"{API}/super/plans", json={"key": key, "name": "dup", "industry": "college", "price": 1, "max_users": 1}).status_code == 400
    assert sup.post(f"{API}/super/plans", json={"key": "test_bad_mode", "name": "x x", "industry": "college", "mode": "billing", "price": 1, "max_users": 1}).status_code == 400
    bid, s = new_org("college")
    r = sup.post(f"{API}/super/orgs/{bid}/extend", json={"period": "year", "plan": key, "method": "None"})
    assert r.status_code == 200
    assert s.get(f"{API}/billing/status").json()["max_users"] == 20


def test_payments_history(sup):
    rows = sup.get(f"{API}/super/payments").json()
    assert isinstance(rows, list) and rows
    assert {"date", "org", "plan", "amount", "method", "reference", "days", "source", "by"} <= set(rows[0])
