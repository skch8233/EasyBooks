from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

import logging
import os
from fastapi import FastAPI
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
import business

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Easy Books Accounting")
for r in (auth.router, auth.users_router, routes_ledgers.router, routes_vouchers.router, routes_reports.router, routes_admin.router, billing.router, gst.router, public.router):
    app.include_router(r)


@app.get("/api/")
async def root():
    return {"message": "Easy Books API"}


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
        await db.vouchers.create_index([("business_id", ASCENDING), ("status", ASCENDING), ("date", ASCENDING)])
        await db.licences.create_index("key", unique=True)
        await db.vouchers.create_index("share_token", sparse=True)
        await db.payments.create_index("order_id")
    except Exception as exc:
        logger.error("index creation: %s", exc)
    await business.migrate_legacy()
    await auth.seed_admin()
    try:
        routes_admin.init_storage()
    except Exception as exc:
        logger.error("storage init failed: %s", exc)


@app.on_event("shutdown")
async def shutdown():
    client.close()
