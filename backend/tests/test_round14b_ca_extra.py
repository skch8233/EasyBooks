# Round 14 CA multi-client access: extra regression tests (businesses list, clients, switch, access, isolation)
import os
import uuid

import pytest
import requests

API = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/") + "/api"
H = lambda t: {"Authorization": f"Bearer {t}"}
P = {"from_date": "2026-04-01", "to_date": "2027-03-31"}


def signup(name):
    e = f"test_cax_{uuid.uuid4().hex[:8]}@ex.in"
    r = requests.post(f"{API}/auth/signup", json={"business_name": name, "name": name, "email": e, "password": "secret12", "state": "27-Maharashtra"})
    assert r.status_code == 200, r.text
    return r.json()["token"], e, r.json()["user"]


def jv(t, d, dr, cr, amt):
    return requests.post(f"{API}/vouchers", headers=H(t), json={"voucher_type": "journal", "date": d, "entries": [{"ledger_id": dr, "debit": amt}, {"ledger_id": cr, "credit": amt}]})


def leds(t):
    ls = requests.get(f"{API}/ledgers", headers=H(t)).json()
    return {l["group"]: l["id"] for l in ls}, ls


@pytest.fixture(scope="module")
def W():
    ca, ca_email, ca_user = signup("TEST_CAX Firm")
    owner, owner_email, owner_user = signup("TEST_CAX Owner")
    other, other_email, _ = signup("TEST_CAX Other")
    return dict(ca=ca, ca_email=ca_email, ca_user=ca_user, owner=owner, owner_email=owner_email, owner_user=owner_user, other=other, other_email=other_email)


# businesses list (home only)
def test_businesses_home_only(W):
    r = requests.get(f"{API}/ca/businesses", headers=H(W["ca"]))
    assert r.status_code == 200
    d = r.json()
    assert len(d) == 1 and d[0]["home"] is True and d[0]["current"] is True and d[0]["role"] == "admin"
    for k in ["name", "role", "business_type", "fy", "vouchers", "last_entry", "depreciation_posted", "tax_posted", "plan_status"]:
        assert k in d[0], k
    assert d[0]["name"] == "TEST_CAX Firm"


# client creation validation
def test_client_validation(W):
    assert requests.post(f"{API}/ca/clients", headers=H(W["ca"]), json={"business_name": "  "}).status_code == 400
    r = requests.post(f"{API}/ca/clients", headers=H(W["ca"]), json={"business_name": "TEST_bad", "gstin": "12345"})
    assert r.status_code == 400 and "GSTIN" in r.json()["detail"]
    assert requests.post(f"{API}/ca/clients", headers=H(W["ca"]), json={"business_name": "TEST_x", "business_type": "trust"}).status_code == 422


def test_client_create_and_switch(W):
    r = requests.post(f"{API}/ca/clients", headers=H(W["ca"]), json={"business_name": "TEST_CAX Client LLP", "business_type": "llp", "state": "29-Karnataka", "gstin": "29ABCDE1234F1Z5"})
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["role"] == "admin" and c["business_type"] == "llp" and c["current"] is False and c["gstin"] == "29ABCDE1234F1Z5"
    W["c1"] = c["id"]
    lst = requests.get(f"{API}/ca/businesses", headers=H(W["ca"])).json()
    assert [b["id"] for b in lst] == [lst[0]["id"], c["id"]]
    W["home"] = lst[0]["id"]
    s = requests.post(f"{API}/ca/switch", headers=H(W["ca"]), json={"business_id": c["id"]})
    assert s.status_code == 200
    W["t1"] = s.json()["token"]
    me = requests.get(f"{API}/auth/me", headers=H(W["t1"])).json()
    assert me["business_id"] == c["id"] and me["role"] == "admin"
    st = requests.get(f"{API}/settings", headers=H(W["t1"])).json()
    assert st["company_name"] == "TEST_CAX Client LLP" and st["business_type"] == "llp"
    lst2 = requests.get(f"{API}/ca/businesses", headers=H(W["t1"])).json()
    assert [b["current"] for b in lst2] == [False, True]


# data isolation: vouchers + fa-tax endpoints
def test_isolation(W):
    g, _ = leds(W["t1"])
    r = jv(W["t1"], "2026-05-10", g["bank"], g["capital"], 77777)
    assert r.status_code == 200, r.text
    vid = r.json()["id"]
    cv = requests.get(f"{API}/vouchers", headers=H(W["t1"])).json()
    assert any(v["id"] == vid for v in cv)
    hv = requests.get(f"{API}/vouchers", headers=H(W["ca"])).json()
    assert not any(v["id"] == vid for v in hv)
    assert requests.get(f"{API}/vouchers/{vid}", headers=H(W["ca"])).status_code in (403, 404)
    fa = requests.get(f"{API}/reports/final-accounts", headers=H(W["t1"]), params={"to_date": "2027-03-31"})
    assert fa.status_code == 200
    assert requests.get(f"{API}/depreciation", headers=H(W["t1"]), params=P).status_code == 200
    assert requests.get(f"{API}/tax-provision", headers=H(W["t1"]), params=P).status_code == 200
    lst = requests.get(f"{API}/ca/businesses", headers=H(W["ca"])).json()
    c = [b for b in lst if b["id"] == W["c1"]][0]
    assert c["vouchers"] == 1 and c["last_entry"] == "2026-05-10"
    assert lst[0]["vouchers"] == 0


def test_switch_non_member_and_back_home(W):
    assert requests.post(f"{API}/ca/switch", headers=H(W["other"]), json={"business_id": W["c1"]}).status_code == 403
    assert requests.post(f"{API}/ca/switch", headers=H(W["ca"]), json={"business_id": "nonexistent"}).status_code == 403
    r = requests.post(f"{API}/ca/switch", headers=H(W["t1"]), json={"business_id": W["home"]})
    assert r.status_code == 200
    assert r.json()["user"]["business_id"] == W["home"] and r.json()["user"]["role"] == "admin"
    me = requests.get(f"{API}/auth/me", headers=H(r.json()["token"])).json()
    assert me["business_id"] == W["home"] and me["role"] == "admin" and "home_business_id" not in me


# access management
def test_access_grant_rules(W):
    o = W["owner"]
    r = requests.post(f"{API}/ca/access", headers=H(o), json={"email": "nobody_zz9@ex.in"})
    assert r.status_code == 404 and "sign up" in r.json()["detail"]
    assert requests.post(f"{API}/ca/access", headers=H(o), json={"email": W["owner_email"]}).status_code == 400
    assert requests.post(f"{API}/ca/access", headers=H(o), json={"email": "not-an-email"}).status_code == 422
    assert requests.post(f"{API}/ca/access", headers=H(o), json={"email": W["ca_email"], "role": "superuser"}).status_code == 422
    r = requests.post(f"{API}/ca/access", headers=H(o), json={"email": W["ca_email"].upper(), "role": "viewer"})
    assert r.status_code == 200 and r.json()["role"] == "viewer"
    lst = requests.get(f"{API}/ca/access", headers=H(o)).json()
    assert len(lst) == 1 and lst[0]["email"] == W["ca_email"] and lst[0]["role"] == "viewer"
    W["owner_bid"] = W["owner_user"]["business_id"]


def test_viewer_member_cannot_write(W):
    t = requests.post(f"{API}/ca/switch", headers=H(W["ca"]), json={"business_id": W["owner_bid"]}).json()["token"]
    me = requests.get(f"{API}/auth/me", headers=H(t)).json()
    assert me["role"] == "viewer"
    g, _ = leds(t)
    assert jv(t, "2026-05-10", g["bank"], g["capital"], 100).status_code == 403
    assert requests.get(f"{API}/vouchers", headers=H(t)).status_code == 200
    # viewer of member biz but admin at home: can still add client (home role)
    r = requests.post(f"{API}/ca/clients", headers=H(t), json={"business_name": "TEST_CAX Client2"})
    assert r.status_code == 200
    W["c2"] = r.json()["id"]


def test_upgrade_to_accountant_and_revoke(W):
    o = W["owner"]
    assert requests.post(f"{API}/ca/access", headers=H(o), json={"email": W["ca_email"], "role": "accountant"}).status_code == 200
    lst = requests.get(f"{API}/ca/access", headers=H(o)).json()
    assert len(lst) == 1 and lst[0]["role"] == "accountant"
    t = requests.post(f"{API}/ca/switch", headers=H(W["ca"]), json={"business_id": W["owner_bid"]}).json()["token"]
    g, _ = leds(t)
    assert jv(t, "2026-06-01", g["bank"], g["capital"], 500).status_code == 200
    assert requests.get(f"{API}/ca/access", headers=H(t)).status_code == 403
    assert requests.post(f"{API}/ca/access", headers=H(t), json={"email": W["other_email"]}).status_code == 403
    assert requests.delete(f"{API}/ca/access/{W['ca_user']['id']}", headers=H(t)).status_code == 403
    # revoke
    assert requests.delete(f"{API}/ca/access/{W['ca_user']['id']}", headers=H(o)).status_code == 200
    assert requests.get(f"{API}/auth/me", headers=H(t)).status_code == 401
    assert requests.get(f"{API}/vouchers", headers=H(t)).status_code == 401
    assert requests.delete(f"{API}/ca/access/{W['ca_user']['id']}", headers=H(o)).status_code == 404
    lst = requests.get(f"{API}/ca/businesses", headers=H(W["ca"])).json()
    assert W["owner_bid"] not in [b["id"] for b in lst]


def test_viewer_home_cannot_add_client(W):
    # owner adds a viewer user in their own business
    e = f"test_caxv_{uuid.uuid4().hex[:6]}@ex.in"
    r = requests.post(f"{API}/users", headers=H(W["owner"]), json={"name": "TEST_viewer", "email": e, "password": "secret12", "role": "viewer"})
    if r.status_code != 200:
        pytest.skip(f"cannot create viewer: {r.status_code} {r.text}")
    t = requests.post(f"{API}/auth/login", json={"email": e, "password": "secret12"}).json()["token"]
    r = requests.post(f"{API}/ca/clients", headers=H(t), json={"business_name": "TEST_viewer client"})
    assert r.status_code == 403
    assert requests.get(f"{API}/ca/access", headers=H(t)).status_code == 403


def test_self_grant_via_client_does_not_downgrade(W):
    # CA switched into own client (admin) grants own email -> should be refused (would downgrade own role)
    t = requests.post(f"{API}/ca/switch", headers=H(W["ca"]), json={"business_id": W["c1"]}).json()["token"]
    r = requests.post(f"{API}/ca/access", headers=H(t), json={"email": W["ca_email"], "role": "viewer"})
    me_role = requests.get(f"{API}/auth/me", headers=H(t)).json().get("role")
    if r.status_code == 200:
        # restore
        pass
    assert r.status_code == 400, f"self-grant accepted; role now {me_role}"
