# Round 16: /api/public/demo rate limit (10/hour/IP), demo businesses hidden from platform list. RUN LAST (blocks demos from this IP for 1h).
import os
import uuid

import requests

API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"


def admin():
    r = requests.post(f"{API}/auth/login", json={"email": "admin@easybooks.in", "password": "Admin@123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_demo_hidden_then_rate_limited_and_spoof():
    r = requests.post(f"{API}/public/demo", json={"industry_type": "retail"})
    if r.status_code == 200:
        bid = r.json()["user"]["business_id"]
        rows = requests.get(f"{API}/platform/businesses", headers=admin()).json()
        rows = rows.get("businesses", rows) if isinstance(rows, dict) else rows
        assert bid not in [b["id"] for b in rows], "demo listed in platform businesses"
    codes = [r.status_code]
    for _ in range(12):
        c = requests.post(f"{API}/public/demo", json={"industry_type": "retail"}).status_code
        codes.append(c)
        if c == 429:
            break
    print("codes", codes)
    assert 429 in codes, codes
    assert codes.count(200) <= 10
    body = requests.post(f"{API}/public/demo", json={"industry_type": "retail"}).json()
    assert "Too many" in body["detail"]
    # spoofed X-Forwarded-For should not bypass the limit
    sp = requests.post(f"{API}/public/demo", json={"industry_type": "retail"}, headers={"X-Forwarded-For": f"10.9.{uuid.uuid4().int % 250}.7"})
    print("spoof status", sp.status_code)
    assert sp.status_code == 429, "X-Forwarded-For spoof bypasses demo rate limit"
