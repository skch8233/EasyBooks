import os
import re
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from auth import ANY, SUPER
from business import ERP_PLAN, PLANS, get_business, status_of
from db import db, NO_ID, new_id, now_iso, audit, clean
from routes_admin import APP_NAME, _storage

router = APIRouter(prefix="/api/erp")
ROLES = ["admin", "accountant", "project_manager", "data_entry", "viewer"]
ACTIONS = ["view", "create", "edit", "approve", "finalize", "cancel", "edit_finalized", "delete", "settings"]
DEFAULT_PERMS = {
    "view": ROLES, "create": ROLES[:4], "edit": ROLES[:4], "approve": ["admin", "project_manager"],
    "finalize": ["admin", "accountant"], "cancel": ["admin", "accountant"], "edit_finalized": ["admin"],
    "delete": ROLES[:4], "settings": ["admin"],
}
INDUSTRIES = ["Construction & Civil", "Interior & Fit-out", "Electrical & MEP", "Solar & Renewable", "IT & Software Services",
              "Engineering & Consulting", "Manufacturing (job work)", "Events & Media", "Real Estate", "Other"]
STATUSES = ["Planning", "Running", "On Hold", "Completed", "Cancelled"]


def erp_active(b: dict) -> bool:
    if os.environ.get("OFFLINE_MODE") == "1":
        return True
    if "erp" in (b.get("modules") or {}):
        return bool(b["modules"]["erp"])
    st = status_of(b)
    if st["status"] == "trial" or (st["status"] == "active" and b.get("plan", "") in PLANS and PLANS[b["plan"]].get("industry")
                                    and not b["plan"].startswith("wholesale_billing")):
        return True
    return bool(b.get("erp_ends")) and b["erp_ends"] > now_iso()


async def erp_settings(bid: str) -> dict:
    s = await db.erp_settings.find_one({"business_id": bid}, NO_ID) or {}
    return {"industry": "", "quotation_prefix": "QT", "invoice_prefix": "INV", "default_quote_template": "classic",
            "default_invoice_template": "gst_goods", "authorized_signatory": "", "quote_terms": "", "expense_categories": [], "permissions": DEFAULT_PERMS, **clean(s)}


def can(user: dict, perms: dict, action: str) -> bool:
    return bool(user.get("is_superadmin")) or user["role"] in perms.get(action, DEFAULT_PERMS[action])


def erp(action: str = "view"):
    async def dep(user=Depends(ANY)):
        b = await get_business(user["business_id"])
        if not erp_active(b):
            raise HTTPException(402, "The Projects / ERP module needs the ERP plan (₹15,000 + GST per year).")
        if action != "view" and status_of(b)["status"] == "expired":
            raise HTTPException(402, "Your Easy Books plan has expired. Books are read-only until you renew from Subscription.")
        s = await erp_settings(user["business_id"])
        if not can(user, s["permissions"], action):
            raise HTTPException(403, f"Your role ({user['role'].replace('_', ' ')}) is not allowed to {action.replace('_', ' ')} ERP documents")
        return user
    return dep


# ---------- plan & settings ----------
@router.get("/status")
async def status(user=Depends(ANY)):
    b = await get_business(user["business_id"])
    s = await erp_settings(user["business_id"])
    return {"active": erp_active(b), "ends_at": b.get("erp_ends"), "plan": ERP_PLAN, "industry": s["industry"],
            "my_permissions": {a: can(user, s["permissions"], a) for a in ACTIONS}}


class GrantIn(BaseModel):
    days: int = Field(365, ge=1, le=3650)


@router.post("/platform/{bid}/grant")
async def grant(bid: str, body: GrantIn, user=Depends(SUPER)):
    b = await get_business(bid)
    start = max(datetime.now(timezone.utc), datetime.fromisoformat(b["erp_ends"]) if b.get("erp_ends") else datetime.now(timezone.utc))
    ends = (start + timedelta(days=body.days)).isoformat()
    await db.businesses.update_one({"id": bid}, {"$set": {"erp_ends": ends}})
    await audit("erp_plan", bid, "grant", {**user, "business_id": bid}, note=f"+{body.days} days")
    return {"erp_ends": ends}


class ErpSettingsIn(BaseModel):
    industry: str = ""
    quotation_prefix: str = Field("QT", min_length=1, max_length=10)
    invoice_prefix: str = Field("INV", min_length=1, max_length=10)
    default_quote_template: Literal["classic", "modern", "detailed"] = "classic"
    default_invoice_template: Literal["classic", "modern", "detailed", "gst_goods", "gst_service"] = "gst_goods"
    authorized_signatory: str = ""
    quote_terms: str = ""
    expense_categories: list = []
    permissions: dict = DEFAULT_PERMS


@router.get("/settings")
async def get_settings(user=Depends(erp())):
    return {**(await erp_settings(user["business_id"])), "industries": INDUSTRIES, "roles": ROLES, "actions": ACTIONS}


@router.put("/settings")
async def put_settings(body: ErpSettingsIn, user=Depends(erp("settings"))):
    perms = {a: [r for r in body.permissions.get(a, DEFAULT_PERMS[a]) if r in ROLES] for a in ACTIONS}
    perms["settings"] = sorted(set(perms["settings"]) | {"admin"})
    data = {**body.model_dump(), "permissions": perms}
    await db.erp_settings.update_one({"business_id": user["business_id"]}, {"$set": {**data, "business_id": user["business_id"]}}, upsert=True)
    await audit("erp_settings", user["business_id"], "update", user)
    return await erp_settings(user["business_id"])


@router.post("/settings/signature")
async def upload_signature(file: UploadFile = File(...), user=Depends(erp("settings"))):
    if file.content_type not in ("image/png", "image/jpeg", "image/webp"):
        raise HTTPException(400, "Signature must be a PNG, JPG or WEBP image")
    data = await file.read()
    if len(data) > 1024 * 1024:
        raise HTTPException(400, "Signature image must be under 1 MB")
    bid = user["business_id"]
    path = f"{APP_NAME}/signatures/{bid}/{new_id()}.{file.content_type.split('/')[1]}"
    res = _storage("PUT", path, data=data, headers={"Content-Type": file.content_type})
    await db.erp_settings.update_one({"business_id": bid}, {"$set": {"signature_path": res.json()["path"], "signature_type": file.content_type, "business_id": bid}}, upsert=True)
    await audit("erp_settings", bid, "signature", user)
    return {"ok": True}


@router.delete("/settings/signature")
async def remove_signature(user=Depends(erp("settings"))):
    await db.erp_settings.update_one({"business_id": user["business_id"]}, {"$set": {"signature_path": None}})
    return {"ok": True}


@router.get("/settings/signature")
async def get_signature(user=Depends(erp())):
    s = await erp_settings(user["business_id"])
    if not s.get("signature_path"):
        raise HTTPException(404, "No signature uploaded")
    try:
        r = _storage("GET", s["signature_path"])
    except Exception:
        raise HTTPException(404, "Signature not available")
    return Response(content=r.content, media_type=s.get("signature_type", "image/png"))


# ---------- clients & vendors ----------
class PartyIn(BaseModel):
    kind: Literal["client", "vendor"]
    company_name: str = Field(min_length=1, max_length=150)
    gstin: str = ""
    pan: str = ""
    address: str = ""
    state: str = ""
    contact_person: str = ""
    mobile: str = ""
    email: str = ""
    opening_balance: float = Field(0, ge=0)
    opening_type: Literal["Dr", "Cr"] = "Dr"
    payment_terms_days: int = Field(30, ge=0, le=365)


def _check_party(p: PartyIn):
    if p.gstin.strip() and not re.match(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$", p.gstin.strip().upper()):
        raise HTTPException(400, "Invalid GSTIN format")
    if p.pan.strip() and not re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]$", p.pan.strip().upper()):
        raise HTTPException(400, "Invalid PAN format (e.g. ABCDE1234F)")


def _ledger_fields(p: PartyIn) -> dict:
    return {"group": "sundry_debtors" if p.kind == "client" else "sundry_creditors", "opening_balance": p.opening_balance,
            "opening_type": p.opening_type, "gstin": p.gstin.strip().upper(), "state": p.state, "phone": p.mobile, "email": p.email,
            "address": p.address, "credit_days": p.payment_terms_days}


@router.get("/parties")
async def list_parties(kind: Optional[str] = None, q: Optional[str] = None, user=Depends(erp())):
    query = {"business_id": user["business_id"], "active": True, **({"kind": kind} if kind else {})}
    if q:
        query["company_name"] = {"$regex": re.escape(q), "$options": "i"}
    return clean(await db.erp_parties.find(query, NO_ID).sort("company_name", 1).to_list(5000))


@router.post("/parties")
async def create_party(p: PartyIn, user=Depends(erp("create"))):
    _check_party(p)
    bid, name = user["business_id"], p.company_name.strip()
    if await db.erp_parties.find_one({"business_id": bid, "kind": p.kind, "name_lower": name.lower(), "active": True}):
        raise HTTPException(400, f"A {p.kind} with this name already exists")
    led = await db.ledgers.find_one({"business_id": bid, "name_lower": name.lower(), "active": True}, NO_ID)
    if led and led["group"] != _ledger_fields(p)["group"]:
        raise HTTPException(400, f"A ledger named '{name}' already exists in another group. Use a slightly different name.")
    if not led:
        led = {"id": new_id(), "business_id": bid, "name": name, "name_lower": name.lower(), "system_key": None, "active": True,
               "created_at": now_iso(), **_ledger_fields(p)}
        await db.ledgers.insert_one({**led})
    doc = {**p.model_dump(), "id": new_id(), "business_id": bid, "company_name": name, "name_lower": name.lower(),
           "gstin": p.gstin.strip().upper(), "pan": p.pan.strip().upper(), "ledger_id": led["id"], "active": True, "created_at": now_iso()}
    await db.erp_parties.insert_one({**doc})
    await audit("erp_party", doc["id"], "create", user, after=clean(doc))
    return clean(doc)


async def get_party(pid: str, bid: str) -> dict:
    p = await db.erp_parties.find_one({"id": pid, "business_id": bid}, NO_ID)
    if not p:
        raise HTTPException(404, "Client / vendor not found")
    return p


@router.put("/parties/{pid}")
async def update_party(pid: str, p: PartyIn, user=Depends(erp("edit"))):
    _check_party(p)
    before = await get_party(pid, user["business_id"])
    if p.kind != before["kind"]:
        raise HTTPException(400, "Type cannot be changed")
    upd = {**p.model_dump(), "gstin": p.gstin.strip().upper(), "pan": p.pan.strip().upper(), "updated_at": now_iso()}
    upd.pop("company_name")
    await db.erp_parties.update_one({"id": pid}, {"$set": upd})
    await db.ledgers.update_one({"id": before["ledger_id"]}, {"$set": {k: v for k, v in _ledger_fields(p).items() if k != "group"}})
    await audit("erp_party", pid, "update", user, before=clean(before), after=upd)
    return clean(await get_party(pid, user["business_id"]))


@router.get("/parties/{pid}")
async def party_detail(pid: str, user=Depends(erp())):
    p = await get_party(pid, user["business_id"])
    bid = user["business_id"]
    f = {"business_id": bid, "client_id": pid}
    projects = await db.erp_projects.find({"business_id": bid, "client_id": pid}, NO_ID).sort("created_at", -1).to_list(500)
    quotes = await db.erp_quotations.find(f, {**NO_ID, "items": 0}).sort("date", -1).to_list(500)
    invoices = await db.erp_invoices.find(f, {**NO_ID, "items": 0, "versions": 0}).sort("date", -1).to_list(500)
    docs = await db.erp_documents.find({"business_id": bid, "party_id": pid, "is_deleted": False}, NO_ID).to_list(500)
    return {**clean(p), "projects": clean(projects), "quotations": clean(quotes), "invoices": clean(invoices), "documents": clean(docs)}


@router.delete("/parties/{pid}")
async def delete_party(pid: str, user=Depends(erp("delete"))):
    p = await get_party(pid, user["business_id"])
    used = await db.erp_projects.count_documents({"business_id": p["business_id"], "client_id": pid}) \
        + await db.erp_invoices.count_documents({"business_id": p["business_id"], "client_id": pid}) \
        + await db.erp_quotations.count_documents({"business_id": p["business_id"], "client_id": pid})
    if used:
        raise HTTPException(400, "This client / vendor has projects or documents and cannot be deleted")
    await db.erp_parties.update_one({"id": pid}, {"$set": {"active": False}})
    await audit("erp_party", pid, "delete", user, before=clean(p))
    return {"ok": True}


# ---------- projects ----------
class ProjectIn(BaseModel):
    code: str = ""
    name: str = Field(min_length=1, max_length=150)
    client_id: str
    manager: str = ""
    location: str = ""
    description: str = ""
    start_date: str = ""
    end_date: str = ""
    contract_value: float = Field(0, ge=0)
    status: Literal["Planning", "Running", "On Hold", "Completed", "Cancelled"] = "Planning"
    progress: int = Field(0, ge=0, le=100)


async def next_seq(bid: str, kind: str) -> int:
    from pymongo import ReturnDocument
    c = await db.counters.find_one_and_update({"_id": f"erp:{bid}:{kind}"}, {"$inc": {"seq": 1}}, upsert=True, return_document=ReturnDocument.AFTER)
    return c["seq"]


@router.get("/projects")
async def list_projects(status: Optional[str] = None, client_id: Optional[str] = None, q: Optional[str] = None, user=Depends(erp())):
    query = {"business_id": user["business_id"], **({"status": status} if status else {}), **({"client_id": client_id} if client_id else {})}
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        query["$or"] = [{"name": rx}, {"code": rx}, {"client_name": rx}, {"location": rx}]
    return clean(await db.erp_projects.find(query, NO_ID).sort("created_at", -1).to_list(5000))


@router.post("/projects")
async def create_project(p: ProjectIn, user=Depends(erp("create"))):
    bid = user["business_id"]
    client = await get_party(p.client_id, bid)
    code = p.code.strip().upper()
    if not code:
        while True:
            code = f"PRJ-{await next_seq(bid, 'project'):04d}"
            if not await db.erp_projects.find_one({"business_id": bid, "code": code}):
                break
    elif await db.erp_projects.find_one({"business_id": bid, "code": code}):
        raise HTTPException(400, f"Project code {code} is already used")
    doc = {**p.model_dump(), "id": new_id(), "business_id": bid, "code": code, "client_name": client["company_name"],
           "created_by": user["name"], "created_at": now_iso()}
    await db.erp_projects.insert_one({**doc})
    await audit("erp_project", doc["id"], "create", user, after=clean(doc))
    return clean(doc)


async def get_project(pid: str, bid: str) -> dict:
    p = await db.erp_projects.find_one({"id": pid, "business_id": bid}, NO_ID)
    if not p:
        raise HTTPException(404, "Project not found")
    return p


@router.put("/projects/{pid}")
async def update_project(pid: str, p: ProjectIn, user=Depends(erp("edit"))):
    bid = user["business_id"]
    before = await get_project(pid, bid)
    client = await get_party(p.client_id, bid)
    code = p.code.strip().upper() or before["code"]
    if code != before["code"] and await db.erp_projects.find_one({"business_id": bid, "code": code}):
        raise HTTPException(400, f"Project code {code} is already used")
    upd = {**p.model_dump(), "code": code, "client_name": client["company_name"], "updated_at": now_iso()}
    await db.erp_projects.update_one({"id": pid}, {"$set": upd})
    await db.erp_invoices.update_many({"project_id": pid}, {"$set": {"project_name": p.name, "project_code": code}})
    await db.erp_quotations.update_many({"project_id": pid}, {"$set": {"project_name": p.name, "project_code": code}})
    await audit("erp_project", pid, "update", user, before=clean(before), after=upd)
    return clean(await get_project(pid, bid))


async def project_numbers(pid: str, bid: str) -> dict:
    inv = await db.erp_invoices.find({"business_id": bid, "project_id": pid, "status": {"$in": ["finalized"]}}, NO_ID).to_list(5000)
    notes = await db.erp_notes.find({"business_id": bid, "project_id": pid, "status": "active"}, NO_ID).to_list(5000)
    quotes = await db.erp_quotations.find({"business_id": bid, "project_id": pid, "status": {"$ne": "cancelled"}}, NO_ID).to_list(5000)
    billed = sum(i["totals"]["total"] for i in inv)
    taxable = sum(i["totals"]["taxable"] for i in inv)
    cn = sum(n["totals"]["total"] for n in notes if n["kind"] == "credit")
    dn = sum(n["totals"]["total"] for n in notes if n["kind"] == "debit")
    cn_tax = sum(n["totals"]["taxable"] for n in notes if n["kind"] == "credit")
    dn_tax = sum(n["totals"]["taxable"] for n in notes if n["kind"] == "debit")
    received = sum(i.get("paid", 0) for i in inv)
    from erp_purchase import purchase_numbers
    pn = await purchase_numbers(pid, bid)
    return {"quotations": len(quotes), "quoted_value": round(sum(q["totals"]["total"] for q in quotes), 2),
            "accepted_quotes": sum(1 for q in quotes if q["status"] in ("accepted", "converted")), "invoices": len(inv),
            "billed": round(billed, 2), "billed_taxable": round(taxable, 2), "credit_notes": round(cn, 2), "debit_notes": round(dn, 2),
            "received": round(received, 2), "outstanding": round(sum(i.get("balance", 0) for i in inv), 2),
            **pn, "profit": round(taxable - cn_tax + dn_tax - pn["purchases"] - pn["expenses"], 2)}


@router.get("/projects/{pid}")
async def project_dashboard(pid: str, user=Depends(erp())):
    bid = user["business_id"]
    p = await get_project(pid, bid)
    quotes = await db.erp_quotations.find({"business_id": bid, "project_id": pid}, {**NO_ID, "items": 0}).sort("date", -1).to_list(500)
    invoices = await db.erp_invoices.find({"business_id": bid, "project_id": pid}, {**NO_ID, "items": 0, "versions": 0}).sort("date", -1).to_list(500)
    docs = await db.erp_documents.find({"business_id": bid, "project_id": pid, "is_deleted": False, "expense_id": None}, NO_ID).sort("created_at", -1).to_list(500)
    activity = await db.audit_logs.find({"business_id": bid, "entity_id": {"$in": [pid] + [q["id"] for q in quotes] + [i["id"] for i in invoices]}},
                                        {**NO_ID, "before": 0, "after": 0}).sort("timestamp", -1).to_list(30)
    nums = await project_numbers(pid, bid)
    return {**clean(p), "numbers": {**nums, "contract_value": p["contract_value"], "balance_to_bill": round(p["contract_value"] - nums["billed_taxable"], 2)},
            "quotations": clean(quotes), "invoices": clean(invoices), "documents": clean(docs), "activity": clean(activity)}


@router.delete("/projects/{pid}")
async def delete_project(pid: str, user=Depends(erp("delete"))):
    p = await get_project(pid, user["business_id"])
    if await db.erp_invoices.count_documents({"business_id": p["business_id"], "project_id": pid}) or await db.erp_quotations.count_documents({"business_id": p["business_id"], "project_id": pid}):
        raise HTTPException(400, "Project has quotations or invoices. Set its status to Cancelled instead.")
    await db.erp_projects.delete_one({"id": pid})
    await audit("erp_project", pid, "delete", user, before=clean(p))
    return {"ok": True}


# ---------- documents ----------
@router.post("/documents")
async def upload_doc(project_id: str = "", party_id: str = "", expense_id: str = "", file: UploadFile = File(...), user=Depends(erp("create"))):
    bid = user["business_id"]
    if not project_id and not party_id:
        raise HTTPException(400, "Link the document to a project or client / vendor")
    if project_id:
        await get_project(project_id, bid)
    if expense_id and not await db.erp_expenses.find_one({"id": expense_id, "business_id": bid}):
        raise HTTPException(404, "Expense not found")
    if party_id:
        await get_party(party_id, bid)
    data = await file.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(400, "File is larger than 15 MB")
    ext = (file.filename or "file").rsplit(".", 1)[-1][:8].lower() if "." in (file.filename or "") else "bin"
    path = f"{APP_NAME}/erp/{bid}/{new_id()}.{ext}"
    res = _storage("PUT", path, data=data, headers={"Content-Type": file.content_type or "application/octet-stream"})
    doc = {"id": new_id(), "business_id": bid, "project_id": project_id or None, "party_id": party_id or None, "expense_id": expense_id or None, "name": file.filename,
           "storage_path": res.json()["path"], "content_type": file.content_type, "size": len(data), "is_deleted": False,
           "uploaded_by": user["name"], "created_at": now_iso()}
    await db.erp_documents.insert_one({**doc})
    await audit("erp_document", project_id or party_id, "upload", user, note=file.filename)
    return clean(doc)


@router.get("/documents/{did}")
async def download_doc(did: str, user=Depends(erp())):
    d = await db.erp_documents.find_one({"id": did, "business_id": user["business_id"], "is_deleted": False}, NO_ID)
    if not d:
        raise HTTPException(404, "Document not found")
    r = _storage("GET", d["storage_path"])
    return Response(content=r.content, media_type=d.get("content_type") or "application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{d["name"]}"'})


@router.delete("/documents/{did}")
async def delete_doc(did: str, user=Depends(erp("delete"))):
    d = await db.erp_documents.find_one({"id": did, "business_id": user["business_id"]}, NO_ID)
    if not d:
        raise HTTPException(404, "Document not found")
    await db.erp_documents.update_one({"id": did}, {"$set": {"is_deleted": True}})
    await audit("erp_document", d.get("project_id") or d.get("party_id"), "delete_document", user, note=d["name"])
    return {"ok": True}


# ---------- dashboard ----------
@router.get("/dashboard")
async def dashboard(user=Depends(erp())):
    bid = user["business_id"]
    projects = await db.erp_projects.find({"business_id": bid}, NO_ID).to_list(5000)
    inv = await db.erp_invoices.find({"business_id": bid, "status": "finalized"}, {**NO_ID, "versions": 0}).to_list(10000)
    today = datetime.now(timezone.utc).date().isoformat()
    from erp_reports import F, _project_money
    per = [{**r, "name": r["project"], "client_name": r["client"]} for r in await _project_money(bid, F())]
    activity = await db.audit_logs.find({"business_id": bid, "entity": {"$regex": "^erp_"}}, {**NO_ID, "before": 0, "after": 0}).sort("timestamp", -1).to_list(15)
    return {
        "projects": len(projects), "active_projects": sum(1 for p in projects if p["status"] in ("Planning", "Running", "On Hold")),
        "completed_projects": sum(1 for p in projects if p["status"] == "Completed"),
        "clients": await db.erp_parties.count_documents({"business_id": bid, "kind": "client", "active": True}),
        "vendors": await db.erp_parties.count_documents({"business_id": bid, "kind": "vendor", "active": True}),
        "quotations": await db.erp_quotations.count_documents({"business_id": bid, "status": {"$ne": "cancelled"}}),
        "invoices": len(inv), "invoiced": round(sum(i["totals"]["total"] for i in inv), 2),
        "received": round(sum(i.get("paid", 0) for i in inv), 2), "outstanding": round(sum(i.get("balance", 0) for i in inv), 2),
        "overdue": sum(1 for i in inv if i.get("balance", 0) > 0 and i.get("due_date") and i["due_date"] < today),
        "purchases": round(sum(x["purchases"] for x in per), 2), "expenses": round(sum(x["expenses"] for x in per), 2),
        "purchase_orders": await db.erp_pos.count_documents({"business_id": bid, "status": {"$in": ["approved", "closed"]}}),
        "pending_bills": sum(1 for b in await db.erp_bills.find({"business_id": bid, "status": "posted"}, {"totals": 1, "paid": 1}).to_list(10000) if b["totals"]["total"] - b.get("paid", 0) > 0.005),
        "pending_prs": await db.erp_prs.count_documents({"business_id": bid, "status": "submitted"}), "contract_value": round(sum(p["contract_value"] for p in projects), 2),
        "profit": round(sum(x["profit"] for x in per), 2), "by_project": sorted(per, key=lambda x: -x["billed"])[:10], "activity": clean(activity),
    }
