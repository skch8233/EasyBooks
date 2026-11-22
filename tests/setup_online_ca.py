# Iteration 23: create fresh TEST_ CA signup + client online for two-tab business isolation test
import os, json, time, requests
BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
ts = int(time.time())
email = f"test_ca23_{ts}@example.com"
r = requests.post(f"{BASE}/auth/signup", json={"business_name": "TEST_CA23 Firm", "name": "TEST CA", "email": email, "password": "Test@1234", "state": "27-Maharashtra"})
r.raise_for_status()
tok = r.json()["token"]; home = r.json()["user"]["business_id"]
h = {"Authorization": f"Bearer {tok}"}
c = requests.post(f"{BASE}/ca/clients", json={"business_name": "TEST_CA23 Client", "state": "27-Maharashtra"}, headers=h)
print(c.status_code, c.text[:200])
biz = requests.get(f"{BASE}/ca/businesses", headers=h).json()
print(json.dumps({"email": email, "password": "Test@1234", "home": home, "businesses": [(b["id"], b["name"]) for b in biz]}))
