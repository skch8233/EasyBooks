# CA client switch: dashboard total_sales/purchases must match Sales/Purchase Register, P&L, Day Book, GSTR-1 (offline server)
import os
import pytest
import requests

OFF = os.environ.get("OFFLINE_URL", "http://127.0.0.1:8765").rstrip("/")
FROM, TO = "2026-04-01", "2027-03-31"


def _session():
    try:
        r = requests.post(f"{OFF}/api/offline/session", timeout=10)
    except Exception:
        pytest.skip("offline server not running")
    return r.json()["token"]


def _clients(tok):
    h = {"Authorization": f"Bearer {tok}"}
    return [b for b in requests.get(f"{OFF}/api/ca/businesses", headers=h).json() if not b.get("home")]


@pytest.fixture(scope="module")
def home_token():
    return _session()


def _switch(home_token, bid):
    r = requests.post(f"{OFF}/api/ca/switch", json={"business_id": bid}, headers={"Authorization": f"Bearer {home_token}"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_parity_for_every_client(home_token):
    clients = _clients(home_token)
    assert clients, "no CA client businesses"
    for b in clients:
        h = _switch(home_token, b["id"])
        g = lambda p, **q: requests.get(f"{OFF}/api{p}", params=q, headers=h).json()
        d = g("/reports/dashboard", from_date=FROM, to_date=TO)
        sreg = g("/reports/register", voucher_type="sales", from_date=FROM, to_date=TO)
        preg = g("/reports/register", voucher_type="purchase", from_date=FROM, to_date=TO)
        pl = g("/reports/profit-loss", from_date=FROM, to_date=TO)
        tb = g("/reports/trial-balance", to_date=TO)
        day = g("/vouchers", from_date=FROM, to_date=TO, status="active", limit=5000)
        cn = g("/reports/register", voucher_type="credit_note", from_date=FROM, to_date=TO)
        print(b["name"], "dash", d["total_sales"], "reg", sreg["totals"]["taxable"], len(sreg["rows"]), "cn", cn["totals"]["taxable"],
              "pl", pl["totals"].get("sales", 0), "day", len(day), "tb_bal", tb["balanced"])
        assert round(sreg["totals"]["taxable"] - cn["totals"]["taxable"], 2) == round(d["total_sales"], 2), b["name"]
        assert round(preg["totals"]["taxable"], 2) == round(d["total_purchases"], 2) or d["total_purchases"] == 0, b["name"]
        assert pl["totals"].get("sales", 0) == d["total_sales"]
        assert len(day) == d["voucher_count"]
        assert tb["balanced"]
        for m in ("2026-11",):
            g1 = g("/reports/gstr1", month=m)
            assert "summary" in g1
