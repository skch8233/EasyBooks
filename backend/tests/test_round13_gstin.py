import os
import uuid

import requests

API = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/") + "/api"


def biz():
    u = uuid.uuid4().hex[:8]
    r = requests.post(f"{API}/auth/signup", json={"industry_type": "wholesale", "business_name": f"TEST_g_{u}", "name": "T", "email": f"g_{u}@example.com", "password": "secret1", "phone": "", "state": "Maharashtra", "gstin": ""})
    s = requests.Session()
    s.headers["Authorization"] = "Bearer " + r.json()["token"]
    return s


def test_parse_state_pan_and_checksum():
    s = biz()
    d = s.get(f"{API}/gstin/27AAPFU0939F1ZV").json()
    assert d["valid"] and d["state_code"] == "27" and d["pan"] == "AAPFU0939F" and d["saved"] is None
    assert s.get(f"{API}/gstin/27AAPFU0939F1ZX").json()["valid"] is False
    assert s.get(f"{API}/gstin/99AAPFU0939F1ZV").json()["valid"] is False
    assert s.get(f"{API}/gstin/ABC").json()["valid"] is False


def test_saved_details_returned_from_ledger_and_party():
    s = biz()
    s.post(f"{API}/ledgers", json={"name": "Acme Traders", "group": "sundry_debtors", "gstin": "27AAPFU0939F1ZV", "state": "27-Maharashtra", "phone": "9876543210", "address": "Pune"})
    d = s.get(f"{API}/gstin/27aapfu0939f1zv").json()
    assert d["saved"]["name"] == "Acme Traders" and d["saved"]["address"] == "Pune" and d["saved"]["phone"] == "9876543210"
    s.post(f"{API}/erp/parties", json={"kind": "client", "company_name": "Acme Traders Pvt", "gstin": "27AAPFU0939F1ZV", "email": "a@acme.in", "state": "27-Maharashtra"})
    d = s.get(f"{API}/gstin/27AAPFU0939F1ZV").json()
    assert d["saved"]["email"] in ("a@acme.in", "") and d["saved"]["name"]
