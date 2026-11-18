# Round 14c: CA access guards retest (self-grant 400, last-admin revoke guard, non-admin revoke still works)
import asyncio
import os
import sys
import uuid

import pytest
import requests

API = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/") + "/api"
H = lambda t: {"Authorization": f"Bearer {t}"}


def signup(name):
    e = f"test_cag_{uuid.uuid4().hex[:8]}@ex.in"
    r = requests.post(f"{API}/auth/signup", json={"business_name": name, "name": name, "email": e, "password": "secret12", "state": "27-Maharashtra"})
    assert r.status_code == 200, r.text
    return r.json()["token"], e, r.json()["user"]


def switch(t, bid):
    r = requests.post(f"{API}/ca/switch", headers=H(t), json={"business_id": bid})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def W():
    ca, ca_e, ca_u = signup("TEST_CAG Firm")
    b, b_e, b_u = signup("TEST_CAG Second")
    v, v_e, v_u = signup("TEST_CAG Viewer")
    c = requests.post(f"{API}/ca/clients", headers=H(ca), json={"business_name": "TEST_CAG Client"}).json()
    return dict(ca=ca, ca_e=ca_e, ca_u=ca_u, b=b, b_e=b_e, b_u=b_u, v=v, v_e=v_e, v_u=v_u, c=c["id"], tc=switch(ca, c["id"]))


# self-grant guard inside client business
def test_self_grant_400_role_unchanged(W):
    for role in ["viewer", "accountant", "admin"]:
        r = requests.post(f"{API}/ca/access", headers=H(W["tc"]), json={"email": W["ca_e"].upper(), "role": role})
        assert r.status_code == 400, r.text
        assert r.json()["detail"] == "You cannot change your own access"
    me = requests.get(f"{API}/auth/me", headers=H(W["tc"])).json()
    assert me["role"] == "admin" and me["business_id"] == W["c"]
    acc = requests.get(f"{API}/ca/access", headers=H(W["tc"])).json()
    assert [a["role"] for a in acc if a["email"] == W["ca_e"]] == ["admin"]


# self-grant at home also refused
def test_self_grant_home_400(W):
    r = requests.post(f"{API}/ca/access", headers=H(W["ca"]), json={"email": W["ca_e"], "role": "viewer"})
    assert r.status_code == 400


# self revoke refused
def test_self_revoke_400(W):
    r = requests.delete(f"{API}/ca/access/{W['ca_u']['id']}", headers=H(W["tc"]))
    assert r.status_code == 400 and "own" in r.json()["detail"]


# revoke non-admin member works; switched token invalid after
def test_revoke_non_admin_member(W):
    r = requests.post(f"{API}/ca/access", headers=H(W["tc"]), json={"email": W["v_e"], "role": "viewer"})
    assert r.status_code == 200
    tv = switch(W["v"], W["c"])
    r = requests.delete(f"{API}/ca/access/{W['v_u']['id']}", headers=H(W["tc"]))
    assert r.status_code == 200, r.text
    assert requests.get(f"{API}/auth/me", headers=H(tv)).status_code == 401
    assert requests.delete(f"{API}/ca/access/{W['v_u']['id']}", headers=H(W["tc"])).status_code == 404


# second admin revokes CA (allowed since caller is admin); CA can no longer switch
def test_second_admin_revokes_ca(W):
    r = requests.post(f"{API}/ca/access", headers=H(W["tc"]), json={"email": W["b_e"], "role": "admin"})
    assert r.status_code == 200
    tb = switch(W["b"], W["c"])
    r = requests.delete(f"{API}/ca/access/{W['ca_u']['id']}", headers=H(tb))
    assert r.status_code == 200, r.text
    assert requests.post(f"{API}/ca/switch", headers=H(W["ca"]), json={"business_id": W["c"]}).status_code == 403
    # B is now the only admin; B cannot revoke self
    assert requests.delete(f"{API}/ca/access/{W['b_u']['id']}", headers=H(tb)).status_code == 400
    W["tb"] = tb


# last-admin guard branch exercised directly (unreachable via API since caller is always an admin)
def test_last_admin_guard_direct(W):
    sys.path.insert(0, "/app/backend")
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    from fastapi import HTTPException
    import ca as camod
    import db as dbmod
    from motor.motor_asyncio import AsyncIOMotorClient

    async def run():
        cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
        dbmod.db = camod.db = cli[os.environ["DB_NAME"]]
        fake = {"id": "TEST_fake_caller", "business_id": W["c"], "role": "admin", "email": "x@x.in", "name": "x"}
        try:
            await camod.revoke_access(W["b_u"]["id"], user=fake)
            return None
        except HTTPException as e:
            return e
        finally:
            cli.close()
    e = asyncio.run(run())
    assert e is not None and e.status_code == 400 and "only admin" in e.detail
    # B still member
    assert requests.get(f"{API}/auth/me", headers=H(W["tb"])).json()["role"] == "admin"
