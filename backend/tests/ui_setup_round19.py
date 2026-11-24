# Creates TEST_ orgs for Round 19 super admin UI testing; `cleanup` arg deletes them by stored ids
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import requests
from pymongo import MongoClient

API = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
env = dict(l.strip().split("=", 1) for l in open("/app/backend/.env") if "=" in l)
DB = MongoClient(env["MONGO_URL"].strip('"'))[env["DB_NAME"].strip('"')]
F = "/tmp/r19_ui.json"

if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
    for o in json.load(open(F)):
        bid = o["bid"]
        for c in ("users", "settings", "financial_years", "ledgers", "vouchers", "audit_logs", "subscription_ledger", "support_access_log"):
            DB[c].delete_many({"business_id": bid})
        DB.businesses.delete_one({"id": bid})
    print("cleaned")
    sys.exit()

out = []
for tag, ind in (("A", "hospital"), ("B", "wholesale"), ("SUSP", "retail"), ("LOCK", "services"), ("GRACE", "services")):
    e = f"test_r19{tag.lower()}_{uuid.uuid4().hex[:6]}@ex.in"
    r = requests.post(f"{API}/auth/signup", json={"industry_type": ind, "industry_mode": "complete", "business_name": f"TEST_R19 {tag}",
                                                  "name": f"TEST {tag}", "email": e, "password": "secret12"})
    bid = r.json()["user"]["business_id"]
    out.append({"tag": tag, "bid": bid, "email": e})
now = datetime.now(timezone.utc)
DB.businesses.update_one({"id": out[3]["bid"]}, {"$set": {"trial_ends": (now - timedelta(days=9)).isoformat()}})
DB.businesses.update_one({"id": out[4]["bid"]}, {"$set": {"trial_ends": (now - timedelta(days=2)).isoformat()}})
DB.businesses.update_one({"id": out[1]["bid"]}, {"$set": {"max_users_override": 6, "modules": {"erp": True}}})
json.dump(out, open(F, "w"))
print(json.dumps(out))
