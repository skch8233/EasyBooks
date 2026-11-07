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

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Easy Books Accounting")
for r in (auth.router, auth.users_router, routes_ledgers.router, routes_vouchers.router, routes_reports.router, routes_admin.router):
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
    except Exception as exc:
        logger.error("index creation: %s", exc)
    await auth.seed_admin()
    await routes_admin.seed_data()


@app.on_event("shutdown")
async def shutdown():
    client.close()
