# Round 17: demo rate limit - spoofed X-Forwarded-For must not bypass the 429 (run LAST, it uses up the hourly demo quota).
import os
import requests

API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"


def test_demo_limit_and_spoof():
    codes = []
    for _ in range(12):
        r = requests.post(f"{API}/public/demo", json={"industry_type": "retail"})
        codes.append(r.status_code)
        if r.status_code == 429:
            break
    print("codes:", codes)
    assert 429 in codes, "never rate limited"
    for ip in ("10.9.8.7", "1.2.3.4, 5.6.7.8"):
        r = requests.post(f"{API}/public/demo", json={"industry_type": "retail"}, headers={"X-Forwarded-For": ip})
        assert r.status_code == 429, f"spoof {ip} bypassed: {r.status_code}"
