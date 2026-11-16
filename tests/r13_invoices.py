import os, json, requests
B = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
H = {"Authorization": "Bearer " + open("/tmp/admintok").read().strip()}
parties = requests.get(f"{B}/erp/parties", headers=H, params={"kind": "client"}).json()
c = next(p for p in parties if p["company_name"] == "TEST_Karna Corp")
pr = requests.post(f"{B}/erp/projects", headers=H, json={"name": "TEST_R13 Project", "client_id": c["id"], "status": "Running"}); print("proj", pr.status_code, pr.text[:120])
pid = pr.json()["id"]
out = {"project": pid, "client": c["id"]}
for tag, rate in [("fin", 11111), ("draft", 22222)]:
    r = requests.post(f"{B}/erp/invoices", headers=H, json={"date": "2026-11-16", "client_id": c["id"], "project_id": pid, "items": [{"description": f"TEST_R13 {tag} work", "qty": 1, "rate": rate, "gst_rate": 18}]})
    print(tag, r.status_code, r.text[:150]); out[tag] = r.json()["id"]
json.dump(out, open("/tmp/r13inv.json", "w")); print(out)
