# Setup a TEST_ business for Round 10 UI tests (ERP granted, company settings, customer ledger, project)
import os, uuid, requests
API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
U = uuid.uuid4().hex[:5]
a = requests.post(f"{API}/auth/login", json={"email": "admin@easybooks.in", "password": "Admin@123"}).json()["token"]
r = requests.post(f"{API}/auth/signup", json={"business_name": f"TEST_R10UI_{U}", "name": "TEST UI", "email": f"test_r10ui_{U}@example.com", "password": "secret1", "phone": "", "state": "Maharashtra", "gstin": ""}).json()
h = {"Authorization": f"Bearer {r['token']}"}
bid = r["user"]["business_id"]
requests.post(f"{API}/erp/platform/{bid}/grant", json={"days": 365}, headers={"Authorization": f"Bearer {a}"})
requests.put(f"{API}/settings", headers=h, json={"company_name": f"TEST_R10UI_{U}", "address": "1 Test Rd, Pune", "state": "27-Maharashtra", "gstin": "27AABCA4829K1Z4", "pan": "AABCA4829K", "bank_name": "HDFC", "bank_account": "5020", "bank_ifsc": "HDFC0001289"})
print(requests.post(f"{API}/ledgers", headers=h, json={"name": f"TEST_Cust_{U}", "group": "sundry_debtors", "state": "29-Karnataka", "gstin": "29AAACH7194M1Z8", "address": "Blr"}).status_code)
c = requests.post(f"{API}/erp/parties", headers=h, json={"kind": "client", "company_name": f"TEST_cl_{U}", "state": "Maharashtra", "gstin": "27AAACH7194M1Z8"}).json()
p = requests.post(f"{API}/erp/projects", headers=h, json={"name": f"TEST_P1_{U}", "client_id": c["id"], "contract_value": 100000}).json()
print("EMAIL", f"test_r10ui_{U}@example.com", "PROJECT", p.get("code"), p.get("id"), "CLIENT", c["id"])
