# Probe: concurrency on bill post / payments / GRN (Phase B)
import os, uuid, concurrent.futures as cf
from datetime import date
import requests

API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
T = date.today().isoformat()
tok = requests.post(f"{API}/auth/login", json={"email": "admin@easybooks.in", "password": "Admin@123"}).json()["token"]
H = {"Authorization": f"Bearer {tok}"}
s = requests.Session(); s.headers.update(H)
v = s.post(f"{API}/erp/parties", json={"kind": "vendor", "company_name": f"TEST_vendor_race_{uuid.uuid4().hex[:5]}"}).json()
c = s.post(f"{API}/erp/parties", json={"kind": "client", "company_name": f"TEST_client_race_{uuid.uuid4().hex[:5]}"}).json()
p = s.post(f"{API}/erp/projects", json={"name": f"TEST_race_{uuid.uuid4().hex[:5]}", "client_id": c["id"]}).json()
po = s.post(f"{API}/erp/pos", json={"date": T, "project_id": p["id"], "vendor_id": v["id"], "items": [{"description": "TEST_r", "qty": 10, "rate": 100, "gst_rate": 18}]}).json()
s.post(f"{API}/erp/pos/{po['id']}/approve")

def post(url, body=None):
    return requests.post(url, json=body, headers=H).status_code

with cf.ThreadPoolExecutor(5) as ex:
    codes = list(ex.map(lambda _: post(f"{API}/erp/grns", {"po_id": po["id"], "date": T, "lines": [{"line": 0, "received": 8, "accepted": 8}]}), range(4)))
pv = s.get(f"{API}/erp/pos/{po['id']}").json()
print("GRN race codes", codes, "accepted", pv["items"][0]["accepted"], "pending", pv["items"][0]["pending"])

b = s.post(f"{API}/erp/bills", json={"vendor_id": v["id"], "project_id": p["id"], "po_id": po["id"], "vendor_invoice_no": f"TEST_R_{uuid.uuid4().hex[:4]}",
                                    "vendor_invoice_date": T, "items": [{"description": "TEST_r", "qty": 8, "rate": 100, "gst_rate": 18, "po_line": 0}]}).json()
print("bill", b.get("id"), b.get("detail"))
with cf.ThreadPoolExecutor(4) as ex:
    codes = list(ex.map(lambda _: post(f"{API}/erp/bills/{b['id']}/post"), range(4)))
bb = s.get(f"{API}/erp/bills/{b['id']}").json()
vs = [x for x in s.get(f"{API}/vouchers", params={"voucher_type": "purchase"}).json() if isinstance(x, dict) and bb["number"] in (x.get("narration") or "")] if True else []
print("post race codes", codes, "voucher_no", bb.get("voucher_no"), "purchase vouchers w/ narration", len(vs))
cash = next(l["id"] for l in s.get(f"{API}/ledgers").json() if l["group"] == "cash")
with cf.ThreadPoolExecutor(4) as ex:
    codes = list(ex.map(lambda _: post(f"{API}/erp/bills/{b['id']}/payments", {"date": T, "amount": bb["totals"]["total"], "ledger_id": cash}), range(4)))
bb = s.get(f"{API}/erp/bills/{b['id']}").json()
print("pay race codes", codes, "paid", bb.get("paid"), "total", bb["totals"]["total"], "balance", bb.get("balance"))
tb = s.get(f"{API}/reports/trial-balance").json()
print("TB", tb["total_debit"], tb["total_credit"])
print("IDS", po["id"], b["id"], p["id"])
