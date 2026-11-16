import os, sys, json, time, requests
B = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
ts = str(int(time.time()))
r = requests.post(f"{B}/auth/signup", json={"business_name": f"TEST_R13 Biz {ts}", "name": "Tester", "email": f"test_r13_{ts}@ex.in", "password": "secret12", "state": "27-Maharashtra"})
r.raise_for_status()
tok = r.json()["token"]
H = {"Authorization": f"Bearer {tok}"}
fy = requests.get(f"{B}/auth/me", headers=H).json()
lg = requests.get(f"{B}/ledgers", headers=H).json()
names = {l["name"]: l["id"] for l in lg}
def mk(name, group):
    if name in names: return names[name]
    x = requests.post(f"{B}/ledgers", headers=H, json={"name": name, "group": group}); x.raise_for_status(); return x.json()["id"]
cap = mk("TEST_Capital", "capital")
bank = mk("TEST_Bank", "bank")
inc = mk("TEST_Consulting Income", "indirect_income")
print(json.dumps({"token": tok, "email": f"test_r13_{ts}@ex.in", "cap": cap, "bank": bank, "inc": inc, "ledgers": list(names.keys())[:40]}))
