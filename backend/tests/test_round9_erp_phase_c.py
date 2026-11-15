# Round 9 ERP Phase C: ERP reports (16) + filters + reconciliation with source data, PAN, signature, backup/restore of ERP, offline flags
# Uses a FRESH signup business (ERP granted by superadmin) so admin data is untouched.
import os
import re
import subprocess
import uuid
from datetime import date, timedelta

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
TODAY = date.today().isoformat()
YDAY = (date.today() - timedelta(days=1)).isoformat()
U = uuid.uuid4().hex[:6]
KEYS = ["project_income_expense", "project_profitability", "clients", "vendors", "quotations", "invoices", "cancelled_invoices", "outstanding_invoices",
        "prs", "vendor_comparison", "pos", "pending_delivery", "grns", "bills", "reconciliation", "expenses"]
PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")


def ok(r):
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    return r.json()


def line(desc="TEST_work", qty=1, rate=10000, gst=18):
    return {"description": desc, "hsn": "9954", "unit": "nos", "qty": qty, "rate": rate, "discount": 0, "gst_rate": gst}


@pytest.fixture(scope="module")
def admin():
    r = requests.post(f"{API}/auth/login", json={"email": "admin@easybooks.in", "password": "Admin@123"})
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {ok(r)['token']}"})
    return s


@pytest.fixture(scope="module")
def W(admin):
    """Fresh business with full ERP data set."""
    r = ok(requests.post(f"{API}/auth/signup", json={"business_name": f"TEST_ERPC_{U}", "name": "TEST Owner", "email": f"test_erpc_{U}_{uuid.uuid4().hex[:4]}@example.com",
                                                    "password": "secret1", "phone": "", "state": "Maharashtra", "gstin": ""}))
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {r['token']}"})
    bid = r["user"]["business_id"]
    ok(admin.post(f"{API}/erp/platform/{bid}/grant", json={"days": 365}))
    mk = lambda kind, **kw: ok(s.post(f"{API}/erp/parties", json={"kind": kind, "company_name": f"TEST_{kind}_{uuid.uuid4().hex[:5]}", "state": "Maharashtra", **kw}))
    c1, c2, v1, v2 = mk("client"), mk("client"), mk("vendor"), mk("vendor")
    p1 = ok(s.post(f"{API}/erp/projects", json={"name": f"TEST_P1_{U}", "client_id": c1["id"], "contract_value": 500000}))
    p2 = ok(s.post(f"{API}/erp/projects", json={"name": f"TEST_P2_{U}", "client_id": c2["id"], "contract_value": 100000}))
    cash = next(l["id"] for l in ok(s.get(f"{API}/ledgers")) if l["group"] == "cash")
    # sales: quotation -> accepted -> invoice -> finalize -> payment -> credit note
    q = ok(s.post(f"{API}/erp/quotations", json={"date": TODAY, "valid_until": (date.today() + timedelta(days=15)).isoformat(), "client_id": c1["id"],
                                                 "project_id": p1["id"], "items": [line(qty=2, rate=10000)], "subject": "TEST_q"}))
    ok(s.post(f"{API}/erp/quotations/{q['id']}/status", json={"status": "sent"}))
    ok(s.post(f"{API}/erp/quotations/{q['id']}/status", json={"status": "accepted"}))
    inv1 = ok(s.post(f"{API}/erp/quotations/{q['id']}/convert", json={"to": "invoice"}))["invoice_id"]
    inv1 = ok(s.post(f"{API}/erp/invoices/{inv1}/finalize"))
    ok(s.post(f"{API}/erp/invoices/{inv1['id']}/payments", json={"date": TODAY, "amount": 10000, "ledger_id": cash}))
    cn = ok(s.post(f"{API}/erp/invoices/{inv1['id']}/notes", json={"kind": "credit", "date": TODAY, "reason": "TEST short", "items": [line(rate=2000)]}))
    inv_c = ok(s.post(f"{API}/erp/invoices", json={"date": TODAY, "client_id": c1["id"], "project_id": p1["id"], "items": [line(rate=5000)]}))
    ok(s.post(f"{API}/erp/invoices/{inv_c['id']}/finalize"))
    ok(s.post(f"{API}/erp/invoices/{inv_c['id']}/cancel", json={"reason": "TEST_wrong client"}))
    inv2 = ok(s.post(f"{API}/erp/invoices", json={"date": TODAY, "client_id": c2["id"], "project_id": p2["id"], "items": [line(rate=3000)]}))
    inv2 = ok(s.post(f"{API}/erp/invoices/{inv2['id']}/finalize"))
    # purchase: PR -> RFQ -> quotes -> select -> PO -> approve -> GRN -> bill -> post -> pay
    items = [{"description": "TEST_Cement", "unit": "bag", "qty": 100}, {"description": "TEST_Steel", "unit": "kg", "qty": 50}]
    pr = ok(s.post(f"{API}/erp/prs", json={"project_id": p1["id"], "date": TODAY, "items": items}))
    ok(s.post(f"{API}/erp/prs/{pr['id']}/action", json={"action": "submit"}))
    ok(s.post(f"{API}/erp/prs/{pr['id']}/action", json={"action": "approve"}))
    rfq = ok(s.post(f"{API}/erp/rfqs", json={"project_id": p1["id"], "date": TODAY, "vendor_ids": [v1["id"], v2["id"]], "items": items, "pr_id": pr["id"]}))
    ok(s.post(f"{API}/erp/rfqs/{rfq['id']}/quotes", json={"vendor_id": v1["id"], "date": TODAY, "lines": [{"rate": 300}, {"rate": 80}]}))
    vq = ok(s.post(f"{API}/erp/rfqs/{rfq['id']}/quotes", json={"vendor_id": v2["id"], "date": TODAY, "lines": [{"rate": 320, "discount": 10}, {"rate": 40}]}))
    ok(s.post(f"{API}/erp/rfqs/{rfq['id']}/select", json={"quote_id": vq["comparison"]["lowest_quote_id"]}))
    po1 = ok(s.post(f"{API}/erp/rfqs/{rfq['id']}/create-po"))
    po1 = ok(s.post(f"{API}/erp/pos/{po1['id']}/approve"))
    ok(s.post(f"{API}/erp/grns", json={"po_id": po1["id"], "date": TODAY, "challan_no": "TEST_CH", "lines": [{"line": 0, "received": 60, "accepted": 58, "rejected": 2},
                                                                                                           {"line": 1, "received": 50, "accepted": 50}]}))
    bill = ok(s.post(f"{API}/erp/bills", json={"vendor_id": v2["id"], "project_id": p1["id"], "po_id": po1["id"], "vendor_invoice_no": f"TEST_VI_{U}",
                                              "vendor_invoice_date": TODAY, "items": [{"description": "TEST_Steel", "qty": 50, "rate": 40, "gst_rate": 18, "po_line": 1}]}))
    ok(s.post(f"{API}/erp/bills/{bill['id']}/post"))
    bill = ok(s.post(f"{API}/erp/bills/{bill['id']}/payments", json={"date": TODAY, "amount": 1000, "ledger_id": cash}))
    po2 = ok(s.post(f"{API}/erp/pos", json={"date": TODAY, "project_id": p2["id"], "vendor_id": v1["id"], "items": [{"description": "TEST_item", "unit": "nos", "qty": 10, "rate": 100, "gst_rate": 18}]}))
    po2 = ok(s.post(f"{API}/erp/pos/{po2['id']}/approve"))
    ok(s.post(f"{API}/erp/grns", json={"po_id": po2["id"], "date": TODAY, "lines": [{"line": 0, "received": 10, "accepted": 10}]}))
    exp = ok(s.post(f"{API}/erp/expenses", json={"project_id": p1["id"], "date": TODAY, "category": "Transport", "paid_to": "TEST_driver", "amount": 1000,
                                                "gst_rate": 5, "payment_ledger_id": cash}))
    ok(s.post(f"{API}/erp/expenses/{exp['id']}/post"))
    return dict(s=s, bid=bid, c1=c1, c2=c2, v1=v1, v2=v2, p1=p1, p2=p2, inv1=inv1, inv2=inv2, inv_c=inv_c, cn=cn, po1=po1, po2=po2, rfq=rfq, bill=bill, pr=pr, cash=cash)


def rep(s, key, **f):
    return ok(s.get(f"{API}/erp/reports/{key}", params=f))


def tb_ok(s):
    tb = ok(s.get(f"{API}/reports/trial-balance"))
    assert round(tb["total_debit"], 2) == round(tb["total_credit"], 2), tb


class TestReports:
    def test_list_and_all_run(self, W):
        s = W["s"]
        lst = ok(s.get(f"{API}/erp/reports"))
        assert [x["key"] for x in lst] == KEYS
        for k in KEYS:
            d = rep(s, k)
            assert d["key"] == k and d["count"] == len(d["rows"]) and isinstance(d["footer"], dict) and d["columns"], k
        assert s.get(f"{API}/erp/reports/nope").status_code == 404

    def test_profitability_reconciles(self, W):
        s = W["s"]
        rows = {r["code"]: r for r in rep(s, "project_profitability")["rows"]}
        r1 = rows[W["p1"]["code"]]
        assert r1["income"] == 18000 and r1["cost"] == 3000 and r1["profit"] == 15000 and r1["margin_pct"] == 83.33, r1
        assert r1["billed"] == 23600 and r1["received"] == 10000
        inv1 = ok(s.get(f"{API}/erp/invoices/{W['inv1']['id']}"))
        assert r1["outstanding"] == round(inv1["balance"], 2)
        ie = {r["code"]: r for r in rep(s, "project_income_expense")["rows"]}[W["p1"]["code"]]
        assert ie["purchases"] == 2000 and ie["expenses"] == 1000 and ie["profit"] == 15000
        # project dashboard + ERP dashboard match
        pd = ok(s.get(f"{API}/erp/projects/{W['p1']['id']}"))["numbers"]
        assert pd["profit"] == r1["profit"] and pd["purchases"] == 2000 and pd["expenses"] == 1000 and pd["billed"] == r1["billed"]
        dash = ok(s.get(f"{API}/erp/dashboard"))
        allp = rep(s, "project_profitability")
        assert dash["profit"] == allp["footer"]["profit"] and dash["purchases"] == allp["footer"]["cost"] - dash["expenses"]
        assert dash["invoiced"] == allp["footer"]["billed"] and dash["received"] == allp["footer"]["received"] and dash["outstanding"] == allp["footer"]["outstanding"]
        tb_ok(s)

    def test_sales_reports(self, W):
        s = W["s"]
        inv = rep(s, "invoices")
        assert inv["count"] == 3 and {r["status"] for r in inv["rows"]} == {"finalized", "cancelled"}
        can = rep(s, "cancelled_invoices")
        assert can["count"] == 1 and can["rows"][0]["reason"] == "TEST_wrong client" and can["rows"][0]["cancelled_at"] == TODAY
        out = rep(s, "outstanding_invoices")
        assert out["count"] == 2 and all(r["bucket"] for r in out["rows"]) and out["footer"]["balance"] == round(sum(r["balance"] for r in out["rows"]), 2)
        qt = rep(s, "quotations")
        assert qt["count"] == 1 and qt["rows"][0]["status"] == "converted"
        cl = {r["party"]: r for r in rep(s, "clients")["rows"]}[W["c1"]["company_name"]]
        assert cl["invoiced"] == 23600 and cl["credit_notes"] == 2360 and cl["received"] == 10000 and cl["projects"] == 1

    def test_purchase_reports(self, W):
        s = W["s"]
        vc = rep(s, "vendor_comparison")
        assert vc["count"] == 2
        low = next(r for r in vc["rows"] if r["lowest"] == "Yes")
        assert low["vendor"] == W["v2"]["company_name"] and low["selected"] == "Selected" and low["diff"] == 0
        hi = next(r for r in vc["rows"] if r["lowest"] != "Yes")
        assert hi["diff"] == 3776.0 and hi["selected"] == ""
        pdl = rep(s, "pending_delivery")
        assert pdl["count"] == 1 and pdl["rows"][0]["item"] == "TEST_Cement" and pdl["rows"][0]["pending"] == 42 and pdl["rows"][0]["pending_value"] == 12096
        rc = {(r["po"], r["item"]): r["status"] for r in rep(s, "reconciliation")["rows"]}
        assert rc[(W["po1"]["number"], "TEST_Cement")] == "to receive"
        assert rc[(W["po1"]["number"], "TEST_Steel")] == "matched"
        assert rc[(W["po2"]["number"], "TEST_item")] == "to bill"
        bl = rep(s, "bills")
        assert bl["count"] == 1 and bl["rows"][0]["taxable"] == 2000 and bl["rows"][0]["balance"] == 1360
        g = rep(s, "grns")
        assert g["count"] == 3 and "rejected" not in g["footer"] and sum(r["rejected"] for r in g["rows"]) == 2
        pos = rep(s, "pos")
        assert pos["count"] == 2
        ex = rep(s, "expenses")
        assert ex["count"] == 1 and ex["rows"][0]["amount"] == 1000 and ex["rows"][0]["total"] == 1050
        prs = rep(s, "prs")
        assert prs["count"] == 1 and prs["rows"][0]["status"] == "rfq"
        vd = {r["party"]: r for r in rep(s, "vendors")["rows"]}[W["v2"]["company_name"]]
        assert vd["billed"] == 2360 and vd["paid"] == 1000 and vd["balance"] == 1360 and vd["pos"] == 1

    def test_filters(self, W):
        s = W["s"]
        assert rep(s, "invoices", project_id=W["p2"]["id"])["count"] == 1
        assert rep(s, "invoices", client_id=W["c1"]["id"])["count"] == 2
        assert rep(s, "invoices", status="cancelled")["count"] == 1
        assert rep(s, "invoices", to_date=YDAY)["count"] == 0
        assert rep(s, "invoices", from_date=TODAY, to_date=TODAY)["count"] == 3
        assert rep(s, "pos", vendor_id=W["v1"]["id"])["rows"][0]["number"] == W["po2"]["number"]
        assert rep(s, "reconciliation", status="to bill")["count"] == 1
        assert rep(s, "pending_delivery", status="late")["count"] == 0
        assert rep(s, "project_profitability", project_id=W["p2"]["id"])["count"] == 1
        assert rep(s, "project_profitability", client_id=W["c1"]["id"])["count"] == 1
        assert rep(s, "project_profitability", to_date=YDAY)["footer"]["income"] == 0
        assert rep(s, "expenses", project_id=W["p2"]["id"])["count"] == 0
        assert rep(s, "vendor_comparison", vendor_id=W["v1"]["id"])["count"] == 1
        assert rep(s, "clients", client_id=W["c2"]["id"])["count"] == 1
        assert rep(s, "bills", vendor_id=W["v1"]["id"])["count"] == 0


class TestCompanySettings:
    def test_pan_validation(self, W):
        s = W["s"]
        cur = ok(s.get(f"{API}/settings"))
        body = {k: v for k, v in cur.items() if k not in ("id", "business_id", "logo_path")}
        bad = s.put(f"{API}/settings", json={**body, "pan": "ABC12"})
        assert bad.status_code == 400 and "Invalid PAN format" in bad.json()["detail"]
        good = s.put(f"{API}/settings", json={**body, "pan": "abcde1234f"})
        assert good.status_code == 200, good.text
        assert ok(s.get(f"{API}/settings"))["pan"] == "ABCDE1234F"

    def test_signature(self, W):
        s = W["s"]
        assert s.post(f"{API}/erp/settings/signature", files={"file": ("x.txt", b"hello", "text/plain")}).status_code == 400
        ok(s.post(f"{API}/erp/settings/signature", files={"file": ("sig.png", PNG, "image/png")}))
        g = s.get(f"{API}/erp/settings/signature")
        assert g.status_code == 200 and g.headers["content-type"].startswith("image/png") and g.content[:4] == PNG[:4]
        ok(s.delete(f"{API}/erp/settings/signature"))
        assert s.get(f"{API}/erp/settings/signature").status_code == 404
        ok(s.post(f"{API}/erp/settings/signature", files={"file": ("sig.png", PNG, "image/png")}))  # leave one for UI


class TestBackupRestore:
    def test_backup_contains_erp_and_restore(self, W):
        s, bid = W["s"], W["bid"]
        b = ok(s.get(f"{API}/backup"))
        cols = b["collections"]
        for c in ("erp_settings", "erp_parties", "erp_projects", "erp_quotations", "erp_invoices", "erp_notes", "erp_used_numbers",
                  "erp_prs", "erp_rfqs", "erp_vendor_quotes", "erp_pos", "erp_grns", "erp_bills", "erp_expenses"):
            assert c in cols, c
        assert len(cols["erp_invoices"]) == 3 and len(cols["erp_pos"]) == 2 and len(cols["erp_grns"]) == 2 and len(cols["erp_bills"]) == 1
        erp_ctr = [c["_id"] for c in cols["counters"] if str(c["_id"]).startswith(f"erp:{bid}:")]
        assert erp_ctr, cols["counters"]
        assert all(not str(c["_id"]).startswith("erp:") or str(c["_id"]).startswith(f"erp:{bid}:") for c in cols["counters"])
        # change data after backup, then restore
        extra = ok(s.post(f"{API}/erp/prs", json={"project_id": W["p1"]["id"], "date": TODAY, "items": [{"description": "TEST_x", "qty": 1}]}))
        ok(s.post(f"{API}/restore", json={"collections": cols}))
        assert s.get(f"{API}/erp/prs/{extra['id']}").status_code == 404
        b2 = ok(s.get(f"{API}/backup"))["collections"]
        for c in ("erp_invoices", "erp_pos", "erp_grns", "erp_bills", "erp_expenses", "erp_prs", "erp_rfqs", "erp_vendor_quotes", "erp_notes"):
            assert len(b2[c]) == len(cols[c]), c
        # reports still identical after restore
        assert {r["code"]: r["profit"] for r in rep(s, "project_profitability")["rows"]}[W["p1"]["code"]] == 15000
        # numbering continues, no reuse of restored numbers
        used_inv = {i["number"] for i in cols["erp_invoices"] if i.get("number")}
        used_po = {p["number"] for p in cols["erp_pos"]}
        n = ok(s.post(f"{API}/erp/invoices", json={"date": TODAY, "client_id": W["c2"]["id"], "project_id": W["p2"]["id"], "items": [line(rate=100)]}))
        n = ok(s.post(f"{API}/erp/invoices/{n['id']}/finalize"))
        assert n["number"] not in used_inv
        seqs = sorted(int(x.rsplit("/", 1)[1]) for x in used_inv)
        assert int(n["number"].rsplit("/", 1)[1]) == seqs[-1] + 1, (n["number"], used_inv)
        po = ok(s.post(f"{API}/erp/pos", json={"date": TODAY, "project_id": W["p2"]["id"], "vendor_id": W["v1"]["id"], "items": [{"description": "TEST_n", "qty": 1, "rate": 1, "gst_rate": 0}]}))
        assert po["number"] not in used_po
        prn = ok(s.post(f"{API}/erp/prs", json={"project_id": W["p1"]["id"], "date": TODAY, "items": [{"description": "TEST_y", "qty": 1}]}))
        assert prn["number"] != W["pr"]["number"]
        tb_ok(s)

    def test_restore_foreign_business_rejected(self, W, admin):
        b = ok(W["s"].get(f"{API}/backup"))
        r = admin.post(f"{API}/restore", json={"collections": b["collections"]})
        assert r.status_code == 400 and "different business" in r.json()["detail"]


class TestOffline:
    def test_build_files(self):
        wf = open("/app/.github/workflows/build-windows.yml").read()
        bat = open("/app/offline/server/build_server.bat").read()
        for m in ("erp_core", "erp_sales", "erp_purchase", "erp_reports"):
            assert f'"{m}"' in wf and f"--hidden-import {m}" in bat, m
        r = subprocess.run(["git", "check-ignore", "backend/erp_core.py", "backend/erp_sales.py", "backend/erp_purchase.py", "backend/erp_reports.py",
                            "frontend/src/pages/erp/ErpReports.jsx"], cwd="/app", capture_output=True, text=True)
        assert r.returncode == 1 and not r.stdout.strip(), r.stdout

    def test_erp_active_offline(self):
        code = "from dotenv import load_dotenv;load_dotenv('.env');from erp_core import erp_active;print(erp_active({}))"
        r = subprocess.run(["python", "-c", code], cwd="/app/backend", capture_output=True, text=True, env={**os.environ, "OFFLINE_MODE": "1"})
        assert r.stdout.strip().endswith("True"), r.stderr[-500:]
        code2 = "from dotenv import load_dotenv;load_dotenv('.env');from erp_core import erp_active;print(erp_active({}))"
        env = {k: v for k, v in os.environ.items() if k != "OFFLINE_MODE"}
        r2 = subprocess.run(["python", "-c", code2], cwd="/app/backend", capture_output=True, text=True, env=env)
        assert r2.stdout.strip().endswith("False"), r2.stderr[-500:]
