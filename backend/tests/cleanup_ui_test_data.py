# One-off cleanup of records created by UI testing (cancels TEST_UI vouchers by id, deactivates TEST ledgers/users by id)
import os
import requests

API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
s = requests.Session()
s.headers["Authorization"] = "Bearer " + requests.post(f"{API}/auth/login", json={"email": "admin@easybooks.in", "password": "Admin@123"}).json()["token"]
for v in s.get(f"{API}/vouchers", params={"q": "TEST_UI", "status": "active"}).json():
    print("cancel", v["voucher_no"], s.post(f"{API}/vouchers/{v['id']}/cancel", json={"reason": "TEST cleanup"}).status_code)
for l in s.get(f"{API}/ledgers").json():
    if l["name"].startswith("TEST_UI"):
        print("deactivate ledger", l["name"], s.delete(f"{API}/ledgers/{l['id']}").status_code)
for u in s.get(f"{API}/users").json():
    if u["email"].startswith("test_") and u["active"]:
        print("deactivate user", u["email"], s.put(f"{API}/users/{u['id']}", json={"active": False}).status_code)
print("FYs", [(f["name"], f["locked"], f["is_active"]) for f in s.get(f"{API}/financial-years").json()])
print("TB", {k: v for k, v in s.get(f"{API}/reports/trial-balance").json().items() if k != "rows"})
