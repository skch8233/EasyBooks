# Round 18: sample-data idempotency (409 on 2nd call, no duplicates) for retail/college/hospital, concurrency race, auth.
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests

API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"


def signup(ind, mode="complete"):
    e = f"test_r18_{uuid.uuid4().hex[:8]}@ex.in"
    r = requests.post(f"{API}/auth/signup", json={"business_name": f"TEST_R18 {ind}", "name": "T", "email": e,
                                                  "password": "secret12", "industry_type": ind, "industry_mode": mode})
    assert r.status_code == 200, r.text
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return s


def count(s, path):
    d = s.get(f"{API}{path}").json()
    return len(d["items"] if isinstance(d, dict) else d)


@pytest.mark.parametrize("ind,paths", [("retail", {"/stock-items": 3}),
                                       ("college", {"/college/students": 2}),
                                       ("hospital", {"/hospital/patients": 1, "/hospital/medicines": 2})])
def test_second_call_409_no_dupes(ind, paths):
    s = signup(ind)
    r1 = s.post(f"{API}/industry/sample-data")
    assert r1.status_code == 200 and r1.json()["industry"] == ind, r1.text
    r2 = s.post(f"{API}/industry/sample-data")
    assert r2.status_code == 409, r2.text
    assert "already" in r2.json()["detail"].lower()
    for p, n in paths.items():
        assert count(s, p) == n, f"{p} count after 2 calls"


def test_concurrent_calls_race():
    s = signup("retail")
    with ThreadPoolExecutor(5) as ex:
        codes = list(ex.map(lambda _: s.post(f"{API}/industry/sample-data").status_code, range(5)))
    n = count(s, "/stock-items")
    print("concurrent codes", codes, "items", n)
    assert codes.count(200) == 1, f"race: {codes}"
    assert n == 3, f"race duplicates: {n} items"


def test_requires_auth():
    assert requests.post(f"{API}/industry/sample-data").status_code in (401, 403)
