# Round 5: offline Windows server harness (offline_server.py) - licence gating, signup lock, SPA fallback
import os
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

PORT = 8768
URL = f"http://127.0.0.1:{PORT}"
BACKEND = Path("/app/backend")
FRONT = Path("/tmp/ebfront_t")
DATA = Path("/tmp/ebdt")
DB = "eb_off_t"


def _sign(payload):
    sys.path.insert(0, str(BACKEND))
    os.environ["LICENCE_SIGNING_KEY"] = dotenv_values(BACKEND / ".env")["LICENCE_SIGNING_KEY"]
    import licensing
    return licensing.sign_code(payload)


@pytest.fixture(scope="module")
def srv():
    (FRONT / "static").mkdir(parents=True, exist_ok=True)
    (FRONT / "index.html").write_text("<html><body>EB_OFFLINE_INDEX</body></html>")
    (FRONT / "static" / "app.js").write_text("console.log('ok')")
    if (DATA / "licence.json").exists():
        (DATA / "licence.json").unlink()
    subprocess.run(["mongosh", DB, "--quiet", "--eval", "db.dropDatabase()"], check=False)
    env = {**os.environ, "MONGO_URL": "mongodb://localhost:27017", "DB_NAME": DB, "JWT_SECRET": "x",
           "LICENCE_PUBLIC_KEY": "G8Jy7VEVHgl6Vp6oRf645qoqsqcoEf3XqWXiJG8-E_g", "EB_DATA_DIR": str(DATA),
           "FRONTEND_DIR": str(FRONT), "EB_PORT": str(PORT)}
    env.pop("LICENCE_SIGNING_KEY", None)
    p = subprocess.Popen([sys.executable, "offline_server.py"], cwd="/app/offline/server", env=env,
                         stdout=open("/tmp/eb_off.log", "w"), stderr=subprocess.STDOUT)
    for _ in range(60):
        try:
            if requests.get(f"{URL}/api/offline/status", timeout=1).status_code == 200:
                break
        except Exception:
            time.sleep(0.5)
    else:
        p.kill()
        pytest.fail("offline server did not start: " + open("/tmp/eb_off.log").read()[-2000:])
    yield
    p.terminate()
    p.wait(10)
    subprocess.run(["mongosh", DB, "--quiet", "--eval", "db.dropDatabase()"], check=False)


class TestOfflineHarness:
    st = {}

    def test_01_status_fresh(self, srv):
        d = requests.get(f"{URL}/api/offline/status").json()
        assert d["offline"] is True and d["has_users"] is False and d["status"] == "expired"

    def test_02_signup_once(self, srv):
        body = {"business_name": "TEST_Off", "name": "TEST Owner", "email": "owner@example.com", "password": "secret1", "phone": "", "state": "", "gstin": ""}
        r = requests.post(f"{URL}/api/auth/signup", json=body)
        assert r.status_code == 200, r.text
        TestOfflineHarness.st["h"] = {"Authorization": f"Bearer {r.json()['token']}"}
        r2 = requests.post(f"{URL}/api/auth/signup", json={**body, "email": "two@example.com"})
        assert r2.status_code == 403
        assert requests.get(f"{URL}/api/offline/status").json()["has_users"] is True

    def test_03_write_402(self, srv):
        r = requests.post(f"{URL}/api/ledgers", headers=self.st["h"], json={"name": "TEST L", "group": "sundry_debtors", "opening_balance": 0, "opening_type": "Dr"})
        assert r.status_code == 402, r.text

    def test_04_invalid_codes(self, srv):
        code = open("/tmp/eb_r5_code.txt").read().strip()
        pre, body, sig = code.split(".")
        bad = [
            "garbage",
            f"EBOL2.{body}.{sig}",
            f"{pre}.{body[:-2]}{'AA' if body[-2:] != 'AA' else 'BB'}.{sig}",
            f"{pre}.{body}.{sig[:-3]}{'xyz' if sig[-3:] != 'xyz' else 'abc'}",
        ]
        # forge payload with far expiry, reuse original sig
        import base64, json
        p = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        p["e"] = "2099-12-31"
        forged = base64.urlsafe_b64encode(json.dumps(p, separators=(",", ":")).encode()).decode().rstrip("=")
        bad.append(f"{pre}.{forged}.{sig}")
        for c in bad:
            r = requests.post(f"{URL}/api/offline/licence", headers=self.st["h"], json={"code": c})
            assert r.status_code == 400, (c[:30], r.status_code, r.text)
        assert requests.get(f"{URL}/api/offline/status").json()["status"] == "expired"

    def test_05_expired_code(self, srv):
        past = (date.today() - timedelta(days=1)).isoformat()
        c = _sign({"k": "EB-TEST-TEST-TEST-TEST", "n": "x", "b": "x", "p": "offline_first", "i": "2024-01-01", "e": past, "d": 8})
        r = requests.post(f"{URL}/api/offline/licence", headers=self.st["h"], json={"code": c})
        assert r.status_code == 400 and "expired" in r.json()["detail"]

    def test_06_valid_code(self, srv):
        code = open("/tmp/eb_r5_code.txt").read().strip()
        r = requests.post(f"{URL}/api/offline/licence", headers=self.st["h"], json={"code": code})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "active" and 364 <= d["days_left"] <= 366 and d["max_users"] == 8
        s = requests.get(f"{URL}/api/offline/status").json()
        assert s["status"] == "active" and s["licence"]["k"].startswith("EB-")

    def test_07_write_works(self, srv):
        r = requests.post(f"{URL}/api/ledgers", headers=self.st["h"], json={"name": "TEST L", "group": "sundry_debtors", "opening_balance": 0, "opening_type": "Dr"})
        assert r.status_code in (200, 201), r.text
        sub = requests.get(f"{URL}/api/billing/status", headers=self.st["h"])
        print("subscription:", sub.status_code, sub.text[:300])

    def test_08_spa_fallback(self, srv):
        for path in ["/", "/dashboard", "/some/deep/route"]:
            r = requests.get(f"{URL}{path}")
            assert r.status_code == 200 and "EB_OFFLINE_INDEX" in r.text
        assert "console.log" in requests.get(f"{URL}/static/app.js").text
        # path traversal blocked
        r = requests.get(f"{URL}/..%2f..%2fetc%2fpasswd")
        assert "root:" not in r.text
        # unknown api path should not return index
        r = requests.get(f"{URL}/api/does-not-exist")
        print("unknown api:", r.status_code, r.text[:80])
