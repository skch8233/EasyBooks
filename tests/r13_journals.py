import os, json, requests
B = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
d = json.load(open("/tmp/r13.json"))
H = {"Authorization": f"Bearer {d['token']}"}
L = {l["name"]: l["id"] for l in requests.get(f"{B}/ledgers", headers=H).json()}
def jv(date, dr, cr, a, n):
    r = requests.post(f"{B}/vouchers", headers=H, json={"voucher_type": "journal", "date": date, "narration": n, "entries": [{"ledger_id": dr, "debit": a}, {"ledger_id": cr, "credit": a}]})
    print(n, r.status_code, r.text[:150])
jv("2026-04-01", L["TEST_Bank"], L["TEST_Capital"], 1000000, "TEST_capital intro")
jv("2026-04-10", L["TEST_Plant Machinery"], L["TEST_Bank"], 500000, "TEST_plant purchase")
jv("2026-10-20", L["TEST_Computers"], L["TEST_Bank"], 100000, "TEST_computer purchase")
jv("2026-06-01", L["TEST_Bank"], L["TEST_Consulting Income"], 800000, "TEST_income")
