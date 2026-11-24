from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import logging
import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import jwt
from pymongo import ASCENDING, DESCENDING
from starlette.middleware.cors import CORSMiddleware

from db import db, client
import auth
import routes_ledgers
import routes_vouchers
import routes_reports
import routes_admin
import billing
import gst
import public
import stock
import reminders
import shop
import business
import erp_core
import erp_sales
import erp_purchase
import erp_reports
import final_accounts
import eway
import fa_tax
import gstin
import ca
import industry
import superadmin

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Easy Books Accounting")
for r in (auth.router, auth.users_router, routes_ledgers.router, routes_vouchers.router, routes_reports.router, routes_admin.router,
          billing.router, gst.router, public.router, stock.router, reminders.router, shop.router, erp_core.router, erp_sales.router,
          erp_purchase.router, erp_reports.router, final_accounts.router, eway.router, fa_tax.router, gstin.router, ca.router,
          industry.router, superadmin.router):
    app.include_router(r)


@app.get("/api/")
async def root():
    return {"message": "Easy Books API"}


BILLING_BLOCK = ("/api/reports/", "/api/depreciation", "/api/tax-provision", "/api/audit-logs", "/api/ca/")


@app.middleware("http")
async def billing_only_guard(request, call_next):
    p = request.url.path
    if p.startswith(BILLING_BLOCK) and not (p == "/api/reports/register" and request.query_params.get("voucher_type", "sales") == "sales"):
        h = request.headers.get("authorization", "")
        if h.startswith("Bearer "):
            try:
                pl = jwt.decode(h[7:], os.environ["JWT_SECRET"], algorithms=["HS256"])
                bid = pl.get("bid") or (await db.users.find_one({"id": pl["sub"]}, {"_id": 0, "business_id": 1}) or {}).get("business_id")
                b = await db.businesses.find_one({"id": bid}, {"_id": 0, "industry_type": 1, "industry_mode": 1}) if bid else None
                if b and b.get("industry_type") in ("wholesale", "services") and b.get("industry_mode") == "billing":
                    msg = "This report is part of the Complete Accounting & Billing set. Switch the plan in Settings > Industry."
                    return JSONResponse({"detail": msg}, status_code=403)
            except jwt.PyJWTError:
                pass
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_credentials=False,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    try:
        await db.users.create_index("email", unique=True)
        await db.users.create_index("id", unique=True)
        await db.login_attempts.create_index("identifier")
        await db.ledgers.create_index("id", unique=True)
        await db.ledgers.create_index("name_lower")
        await db.vouchers.create_index("id", unique=True)
        await db.vouchers.create_index([("date", DESCENDING), ("created_at", DESCENDING)])
        await db.vouchers.create_index([("status", ASCENDING), ("date", ASCENDING)])
        await db.vouchers.create_index("entries.ledger_id")
        await db.vouchers.create_index([("voucher_type", ASCENDING), ("date", ASCENDING)])
        await db.audit_logs.create_index([("entity_id", ASCENDING), ("timestamp", ASCENDING)])
        await db.audit_logs.create_index([("timestamp", DESCENDING)])
        await db.financial_years.create_index("id", unique=True)
        await db.businesses.create_index("id", unique=True)
        await db.users.create_index("business_id")
        for c in ("ledgers", "vouchers", "financial_years", "audit_logs", "settings", "payments", "licences"):
            await db[c].create_index("business_id")
        await superadmin.load_plan_overrides()
        await db.payroll_runs.create_index([("business_id", ASCENDING), ("month", ASCENDING)], unique=True)
        await db.vouchers.create_index([("business_id", ASCENDING), ("status", ASCENDING), ("date", ASCENDING)])
        await db.licences.create_index("key", unique=True)
        await db.vouchers.create_index("share_token", sparse=True)
        await db.stock_items.create_index([("business_id", ASCENDING), ("name_lower", ASCENDING)])
        await db.vouchers.create_index([("business_id", ASCENDING), ("items.item_id", ASCENDING)])
        await db.reminders.create_index("token")
        await db.reminders.create_index([("business_id", ASCENDING), ("ledger_id", ASCENDING)])
        await db.payments.create_index("order_id")
        await db.offline_licences.create_index("key", unique=True)
        await db.shop_orders.create_index("order_id")
        await db.erp_projects.create_index([("business_id", ASCENDING), ("code", ASCENDING)], unique=True)
        await db.erp_invoices.create_index([("business_id", ASCENDING), ("number", ASCENDING)], unique=True,
                                          partialFilterExpression={"number": {"$type": "string"}})
        await db.erp_used_numbers.create_index([("business_id", ASCENDING), ("number", ASCENDING)], unique=True)
        await db.erp_quotations.create_index([("business_id", ASCENDING), ("number", ASCENDING)], unique=True)
        await db.erp_parties.create_index([("business_id", ASCENDING), ("kind", ASCENDING)])
        for c in ("erp_prs", "erp_rfqs", "erp_pos", "erp_grns", "erp_bills", "erp_expenses"):
            await db[c].create_index([("business_id", ASCENDING), ("number", ASCENDING)], unique=True)
        await db.memberships.create_index([("user_id", ASCENDING), ("business_id", ASCENDING)], unique=True)
        await db.memberships.create_index("business_id")
        for c in ("students", "fee_receipts", "staff", "payroll_runs", "patients", "medicines", "hospital_bills", "recurring_bills", "tds_entries"):
            await db[c].create_index("business_id")
        await db.payroll_runs.create_index([("business_id", ASCENDING), ("month", ASCENDING)], unique=True)
        await db.erp_vendor_quotes.create_index([("rfq_id", ASCENDING), ("vendor_id", ASCENDING)], unique=True)
    except Exception as exc:
        logger.error("index creation: %s", exc)
    await business.migrate_legacy()
    if os.environ.get("OFFLINE_MODE") == "1":
        return
    await auth.seed_admin()
    try:
        routes_admin.init_storage()
    except Exception as exc:
        logger.error("storage init failed: %s", exc)


@app.on_event("shutdown")
async def shutdown():
    client.close()
