# Probe: invoice finalized AFTER a backup, then restore -> does the next invoice reuse that number? (fresh signup business)
import os
import uuid
from datetime import date

import requests

API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
T = date.today().isoformat()
U = uuid.uuid4().hex[:6]
adm = requests.Session()
adm.headers["Authorization"] = "Bearer " + requests.post(f"{API}/auth/login", json={"email": "admin@easybooks.in", "password": "Admin@123"}).json()["token"]
r = requests.post(f"{API}/auth/signup", json={"industry_type": "wholesale", "business_name": f"TEST_ERPR_{U}", "name": "TEST", "email": f"test_erpr_{U}@example.com", "password": "secret1",
                                             "phone": "", "state": "Maharashtra", "gstin": ""}).json()
s = requests.Session()
s.headers["Authorization"] = "Bearer " + r["token"]
adm.post(f"{API}/erp/platform/{r['user']['business_id']}/grant", json={"days": 30})
c = s.post(f"{API}/erp/parties", json={"kind": "client", "company_name": f"TEST_c_{U}", "state": "Maharashtra"}).json()
p = s.post(f"{API}/erp/projects", json={"name": "TEST_p", "client_id": c["id"], "contract_value": 1}).json()
L = [{"description": "x", "qty": 1, "rate": 100, "gst_rate": 18}]


def fin():
    i = s.post(f"{API}/erp/invoices", json={"date": T, "client_id": c["id"], "project_id": p["id"], "items": L}).json()
    return s.post(f"{API}/erp/invoices/{i['id']}/finalize").json()["number"]


a = fin()
bk = s.get(f"{API}/backup").json()["collections"]
b = fin()
print("before backup:", a, "after backup:", b)
print("restore:", s.post(f"{API}/restore", json={"collections": bk}).status_code)
c2 = fin()
print("after restore next number:", c2, "REUSED" if c2 == b else "not reused")
