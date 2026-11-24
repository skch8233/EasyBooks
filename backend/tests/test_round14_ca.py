import os
import uuid

import requests

API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"


def signup(name):
    e = f"test_ca_{uuid.uuid4().hex[:8]}@ex.in"
    r = requests.post(f"{API}/auth/signup", json={"industry_type": "wholesale", "business_name": name, "name": name, "email": e, "password": "secret12", "state": "27-Maharashtra"})
    assert r.status_code == 200, r.text
    return r.json()["token"], e


H = lambda t: {"Authorization": f"Bearer {t}"}


def test_ca_flow():
    ca, ca_email = signup("TEST_CA Firm")
    owner, _ = signup("TEST_Owner Biz")
    # CA creates a client business
    r = requests.post(f"{API}/ca/clients", headers=H(ca), json={"industry_type": "wholesale", "business_name": "TEST_Client One", "business_type": "company", "state": "29-Karnataka"})
    assert r.status_code == 200, r.text
    c1 = r.json()["id"]
    # owner grants CA access to their business
    assert requests.post(f"{API}/ca/access", headers=H(owner), json={"email": "nobody_xx@ex.in"}).status_code == 404
    r = requests.post(f"{API}/ca/access", headers=H(owner), json={"email": ca_email, "role": "accountant"})
    assert r.status_code == 200, r.text
    lst = requests.get(f"{API}/ca/businesses", headers=H(ca)).json()
    assert len(lst) == 3 and lst[0]["home"] and lst[0]["current"]
    owner_bid = [b for b in lst if b["name"] == "TEST_Owner Biz"][0]["id"]
    # switch to client one: settings and role change, data isolated
    r = requests.post(f"{API}/ca/switch", headers=H(ca), json={"business_id": c1})
    t1 = r.json()["token"]
    assert r.json()["user"]["business_id"] == c1 and r.json()["user"]["role"] == "admin"
    s = requests.get(f"{API}/settings", headers=H(t1)).json()
    assert s["company_name"] == "TEST_Client One" and s["business_type"] == "company"
    fa = requests.get(f"{API}/reports/final-accounts", headers=H(t1), params={"to_date": "2027-03-31"})
    assert fa.status_code == 200, fa.text
    # switch to owner biz as accountant
    t2 = requests.post(f"{API}/ca/switch", headers=H(t1), json={"business_id": owner_bid}).json()["token"]
    me = requests.get(f"{API}/auth/me", headers=H(t2)).json()
    assert me["business_id"] == owner_bid and me["role"] == "accountant"
    assert requests.get(f"{API}/ca/access", headers=H(t2)).status_code == 403
    # not a member
    assert requests.post(f"{API}/ca/switch", headers=H(owner), json={"business_id": c1}).status_code == 403
    # revoke: CA token for owner biz stops working
    ca_id = requests.get(f"{API}/auth/me", headers=H(ca)).json()["id"]
    assert requests.delete(f"{API}/ca/access/{ca_id}", headers=H(owner)).status_code == 200
    assert requests.get(f"{API}/auth/me", headers=H(t2)).status_code == 401
    # back home
    th = requests.post(f"{API}/ca/switch", headers=H(t1), json={"business_id": lst[0]["id"]}).json()["token"]
    assert requests.get(f"{API}/settings", headers=H(th)).json()["company_name"] == "TEST_CA Firm"
