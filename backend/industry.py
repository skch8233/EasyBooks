import calendar
import secrets
import time
from datetime import datetime, timedelta, timezone
from datetime import date
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from pymongo import ReturnDocument

from accounting import Entry, Item, VoucherIn
from auth import ANY, ADMIN_WRITE, WRITE, create_token, hash_password
from business import INDUSTRIES, MODE_LABEL, PLANS, create_business, get_business, industry_of
from db import db, NO_ID, new_id, now_iso, audit, clean
from routes_vouchers import create_voucher

router = APIRouter(prefix="/api")
Ind = Literal["retail", "college", "hospital", "wholesale", "services"]
Mode = Literal["billing", "complete"]


async def _next(bid: str, kind: str, prefix: str) -> str:
    c = await db.counters.find_one_and_update({"_id": f"ind:{bid}:{kind}"}, {"$inc": {"seq": 1}}, upsert=True, return_document=ReturnDocument.AFTER)
    return f"{prefix}/{c['seq']:04d}"


async def sys_ledger(bid: str, key: str, name: str, group: str) -> str:
    led = await db.ledgers.find_one({"business_id": bid, "system_key": key}, NO_ID)
    if led:
        return led["id"]
    doc = {"id": new_id(), "business_id": bid, "name": name, "name_lower": name.lower(), "group": group, "opening_balance": 0, "opening_type": "Dr", "active": True,
           "system_key": key, "gstin": "", "state": "", "phone": "", "email": "", "address": "", "created_at": now_iso()}
    if await db.ledgers.find_one({"business_id": bid, "name_lower": name.lower()}):
        doc["name"] = doc["name_lower"] = f"{name} (auto)"
    await db.ledgers.insert_one(doc)
    return doc["id"]


async def _cash_bank(bid: str, lid: str):
    led = await db.ledgers.find_one({"id": lid, "business_id": bid}, NO_ID)
    if not led or led["group"] not in ("cash", "bank"):
        raise HTTPException(400, "Choose a Cash or Bank ledger for the money received / paid")


async def _get(coll: str, bid: str, oid: str) -> dict:
    d = await db[coll].find_one({"id": oid, "business_id": bid}, NO_ID)
    if not d:
        raise HTTPException(404, "Record not found")
    return d


# ---------- industry profile ----------
class IndustryIn(BaseModel):
    industry_type: Ind
    industry_mode: Mode = "complete"


def _profile(b: dict) -> dict:
    ind, mode = industry_of(b)
    return {"industry_type": ind, "industry_mode": mode, "label": INDUSTRIES[ind]["label"], "mode_label": MODE_LABEL[mode],
            "modes": INDUSTRIES[ind]["modes"], "industries": {k: v["label"] for k, v in INDUSTRIES.items()}}


@router.get("/industry")
async def get_industry(user=Depends(ANY)):
    return _profile(await get_business(user["business_id"]))


@router.put("/industry")
async def set_industry(body: IndustryIn, user=Depends(ADMIN_WRITE)):
    b = await get_business(user["business_id"])
    ind, mode = industry_of(body.model_dump())
    await db.businesses.update_one({"id": b["id"]}, {"$set": {"industry_type": ind, "industry_mode": mode}})
    await audit("business", b["id"], "industry_change", user, before={"industry": industry_of(b)}, after={"industry": [ind, mode]})
    return _profile({**b, "industry_type": ind, "industry_mode": mode})


# ---------- colleges: students, fees, payroll ----------
class Installment(BaseModel):
    label: str = ""
    due_date: str
    amount: float = Field(gt=0)


class StudentIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    roll_no: str = ""
    course: str = ""
    batch: str = ""
    phone: str = ""
    guardian: str = ""
    address: str = ""
    installments: List[Installment] = []
    fine_per_day: float = Field(0, ge=0)


def _student_view(s: dict, paid: float) -> dict:
    total = round(sum(i["amount"] for i in s.get("installments", [])), 2)
    today, left, fine, rows = date.today().isoformat(), paid, 0.0, []
    for i in sorted(s.get("installments", []), key=lambda x: x["due_date"]):
        cover = min(left, i["amount"])
        left -= cover
        due = round(i["amount"] - cover, 2)
        late = (date.today() - date.fromisoformat(i["due_date"])).days if due > 0 and i["due_date"] < today else 0
        fine += late * s.get("fine_per_day", 0)
        rows.append({**i, "paid": round(cover, 2), "due": due, "days_late": late, "status": "paid" if due <= 0 else ("overdue" if late else "pending")})
    return {**clean(s), "total_fee": total, "paid": round(paid, 2), "balance": round(total - paid, 2), "fine_due": round(fine, 2), "schedule": rows}


async def _paid_map(bid: str) -> dict:
    rows = await db.fee_receipts.aggregate([{"$match": {"business_id": bid}}, {"$group": {"_id": "$student_id", "amt": {"$sum": "$amount"}}}]).to_list(None)
    return {r["_id"]: r["amt"] for r in rows}


@router.get("/college/students")
async def list_students(user=Depends(ANY)):
    paid = await _paid_map(user["business_id"])
    ss = await db.students.find({"business_id": user["business_id"]}, NO_ID).sort("name", 1).to_list(5000)
    return [_student_view(s, paid.get(s["id"], 0)) for s in ss]


@router.post("/college/students")
async def add_student(body: StudentIn, user=Depends(WRITE)):
    doc = {**body.model_dump(), "id": new_id(), "business_id": user["business_id"], "created_at": now_iso()}
    await db.students.insert_one(doc)
    return _student_view(doc, 0)


@router.put("/college/students/{sid}")
async def edit_student(sid: str, body: StudentIn, user=Depends(WRITE)):
    await _get("students", user["business_id"], sid)
    await db.students.update_one({"id": sid}, {"$set": body.model_dump()})
    s = await _get("students", user["business_id"], sid)
    return _student_view(s, (await _paid_map(user["business_id"])).get(sid, 0))


class FeeIn(BaseModel):
    student_id: str
    date: str
    amount: float = Field(gt=0)
    fine: float = Field(0, ge=0)
    ledger_id: str
    note: str = ""


@router.post("/college/fees")
async def collect_fee(body: FeeIn, user=Depends(WRITE)):
    bid = user["business_id"]
    s = await _get("students", bid, body.student_id)
    v0 = _student_view(s, (await _paid_map(bid)).get(s["id"], 0))
    if body.amount > v0["balance"] + 0.005:
        raise HTTPException(400, f"Amount is more than the balance fee of {v0['balance']:.2f}")
    await _cash_bank(bid, body.ledger_id)
    entries = [Entry(ledger_id=body.ledger_id, debit=round(body.amount + body.fine, 2)),
               Entry(ledger_id=await sys_ledger(bid, "fee_income", "Fee Income", "direct_income"), credit=body.amount)]
    if body.fine:
        entries.append(Entry(ledger_id=await sys_ledger(bid, "late_fine_income", "Late Fine Income", "indirect_income"), credit=body.fine))
    no = await _next(bid, "fee", "FR")
    v = await create_voucher(VoucherIn(voucher_type="receipt", date=body.date, reference_no=no, entries=entries,
                                       narration=f"Fee received from {s['name']} ({s.get('roll_no') or '-'}) {body.note}".strip()), user=user)
    doc = {"id": new_id(), "business_id": bid, "receipt_no": no, "student_id": s["id"], "student": s["name"], "roll_no": s.get("roll_no", ""),
           "course": s.get("course", ""), "batch": s.get("batch", ""), "date": body.date, "amount": body.amount, "fine": body.fine,
           "total": round(body.amount + body.fine, 2), "note": body.note, "voucher_id": v["id"], "voucher_no": v["voucher_no"],
           "balance_after": round(v0["balance"] - body.amount, 2), "created_at": now_iso()}
    await db.fee_receipts.insert_one(doc)
    return clean(doc)


@router.get("/college/fees")
async def list_fees(student_id: Optional[str] = None, user=Depends(ANY)):
    q = {"business_id": user["business_id"], **({"student_id": student_id} if student_id else {})}
    return clean(await db.fee_receipts.find(q, NO_ID).sort("created_at", -1).to_list(2000))


class StaffIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    designation: str = ""
    phone: str = ""
    basic: float = Field(0, ge=0)
    allowances: float = Field(0, ge=0)
    deductions: float = Field(0, ge=0)
    active: bool = True


@router.get("/payroll/staff")
async def list_staff(user=Depends(ANY)):
    return clean(await db.staff.find({"business_id": user["business_id"]}, NO_ID).sort("name", 1).to_list(2000))


@router.post("/payroll/staff")
async def add_staff(body: StaffIn, user=Depends(WRITE)):
    doc = {**body.model_dump(), "id": new_id(), "business_id": user["business_id"], "created_at": now_iso()}
    await db.staff.insert_one(doc)
    return clean(doc)


@router.put("/payroll/staff/{sid}")
async def edit_staff(sid: str, body: StaffIn, user=Depends(WRITE)):
    await _get("staff", user["business_id"], sid)
    await db.staff.update_one({"id": sid}, {"$set": body.model_dump()})
    return clean(await _get("staff", user["business_id"], sid))


class PayrollIn(BaseModel):
    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    date: str
    ledger_id: str


@router.post("/payroll/runs")
async def run_payroll(body: PayrollIn, user=Depends(WRITE)):
    bid = user["business_id"]
    if await db.payroll_runs.find_one({"business_id": bid, "month": body.month}):
        raise HTTPException(400, f"Salary for {body.month} is already posted")
    await _cash_bank(bid, body.ledger_id)
    staff = await db.staff.find({"business_id": bid, "active": True}, NO_ID).to_list(2000)
    slips = [{"staff_id": s["id"], "name": s["name"], "designation": s.get("designation", ""), "basic": s["basic"], "allowances": s["allowances"],
              "gross": round(s["basic"] + s["allowances"], 2), "deductions": s["deductions"], "net": round(s["basic"] + s["allowances"] - s["deductions"], 2)} for s in staff]
    slips = [p for p in slips if p["gross"] > 0]
    if not slips:
        raise HTTPException(400, "Add active staff with a salary first")
    gross, ded = round(sum(p["gross"] for p in slips), 2), round(sum(p["deductions"] for p in slips), 2)
    if gross - ded <= 0:
        raise HTTPException(400, "Net salary must be more than zero")
    entries = [Entry(ledger_id=await sys_ledger(bid, "salary_expense", "Staff Salary", "indirect_expense"), debit=gross),
               Entry(ledger_id=body.ledger_id, credit=round(gross - ded, 2))]
    if ded:
        entries.append(Entry(ledger_id=await sys_ledger(bid, "salary_deductions", "Salary Deductions Payable (PF/ESI/TDS)", "current_liabilities"), credit=ded))
    v = await create_voucher(VoucherIn(voucher_type="payment", date=body.date, reference_no=f"PAY-{body.month}", entries=entries,
                                       narration=f"Staff salary for {body.month} ({len(slips)} staff)"), user=user)
    doc = {"id": new_id(), "business_id": bid, "month": body.month, "date": body.date, "slips": slips, "gross": gross, "deductions": ded,
           "net": round(gross - ded, 2), "voucher_id": v["id"], "voucher_no": v["voucher_no"], "created_at": now_iso()}
    await db.payroll_runs.insert_one(doc)
    return clean(doc)


@router.get("/payroll/runs")
async def list_runs(user=Depends(ANY)):
    return clean(await db.payroll_runs.find({"business_id": user["business_id"]}, NO_ID).sort("month", -1).to_list(500))


# ---------- hospitals: patients, pharmacy, bills ----------
class PatientIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    age: str = ""
    gender: str = ""
    phone: str = ""
    address: str = ""
    blood_group: str = ""
    guardian: str = ""


@router.get("/hospital/patients")
async def list_patients(user=Depends(ANY)):
    return clean(await db.patients.find({"business_id": user["business_id"]}, NO_ID).sort("created_at", -1).to_list(5000))


@router.post("/hospital/patients")
async def add_patient(body: PatientIn, user=Depends(WRITE)):
    doc = {**body.model_dump(), "id": new_id(), "business_id": user["business_id"], "reg_no": await _next(user["business_id"], "patient", "UHID"), "created_at": now_iso()}
    await db.patients.insert_one(doc)
    return clean(doc)


@router.put("/hospital/patients/{pid}")
async def edit_patient(pid: str, body: PatientIn, user=Depends(WRITE)):
    await _get("patients", user["business_id"], pid)
    await db.patients.update_one({"id": pid}, {"$set": body.model_dump()})
    return clean(await _get("patients", user["business_id"], pid))


class MedicineIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    batch: str = Field(min_length=1, max_length=40)
    expiry: str
    qty: float = Field(0, ge=0)
    mrp: float = Field(0, ge=0)
    gst_rate: float = Field(12, ge=0, le=28)


def _med_view(m: dict) -> dict:
    days = (date.fromisoformat(m["expiry"]) - date.today()).days
    return {**clean(m), "days_to_expiry": days, "expired": days < 0, "expiring": 0 <= days <= 90}


@router.get("/hospital/medicines")
async def list_meds(user=Depends(ANY)):
    ms = await db.medicines.find({"business_id": user["business_id"]}, NO_ID).sort([("name", 1), ("expiry", 1)]).to_list(5000)
    return [_med_view(m) for m in ms]


@router.post("/hospital/medicines")
async def add_med(body: MedicineIn, user=Depends(WRITE)):
    doc = {**body.model_dump(), "id": new_id(), "business_id": user["business_id"], "created_at": now_iso()}
    await db.medicines.insert_one(doc)
    return _med_view(doc)


@router.put("/hospital/medicines/{mid}")
async def edit_med(mid: str, body: MedicineIn, user=Depends(WRITE)):
    await _get("medicines", user["business_id"], mid)
    await db.medicines.update_one({"id": mid}, {"$set": body.model_dump()})
    return _med_view(await _get("medicines", user["business_id"], mid))


class BillLine(BaseModel):
    description: str = ""
    amount: float = Field(0, ge=0)
    medicine_id: Optional[str] = None
    qty: float = Field(0, ge=0)


class HospitalBillIn(BaseModel):
    patient_id: str
    kind: Literal["opd", "ipd", "lab", "pharmacy"]
    date: str
    doctor: str = ""
    admission_date: str = ""
    discharge_date: str = ""
    ledger_id: str
    lines: List[BillLine] = Field(min_length=1)


KIND = {"opd": ("opd_income", "OPD Consultation Income", "OPD"), "ipd": ("ipd_income", "IPD Income", "IPD"),
        "lab": ("lab_income", "Laboratory Income", "LAB"), "pharmacy": ("pharmacy_income", "Pharmacy Sales", "PH")}


@router.post("/hospital/bills")
async def hospital_bill(body: HospitalBillIn, user=Depends(WRITE)):
    bid = user["business_id"]
    p = await _get("patients", bid, body.patient_id)
    await _cash_bank(bid, body.ledger_id)
    if body.kind != "ipd":
        body.admission_date = body.discharge_date = ""
    lines, stock, need = [], [], {}
    for ln in body.lines:
        if ln.medicine_id:
            need[ln.medicine_id] = need.get(ln.medicine_id, 0) + ln.qty
    for ln in body.lines:
        if ln.medicine_id:
            m = await _get("medicines", bid, ln.medicine_id)
            if ln.qty <= 0 or need[m["id"]] > m["qty"]:
                raise HTTPException(400, f"{m['name']} batch {m['batch']}: only {m['qty']:g} in stock")
            if m["expiry"] < date.today().isoformat():
                raise HTTPException(400, f"{m['name']} batch {m['batch']} has expired and cannot be sold")
            amt = round(ln.qty * m["mrp"], 2)
            lines.append({"description": f"{m['name']} (Batch {m['batch']}, Exp {m['expiry'][:7]})", "qty": ln.qty, "rate": m["mrp"], "amount": amt, "medicine_id": m["id"],
                          "gst_rate": m.get("gst_rate", 0), "gst": round(amt - amt / (1 + m.get("gst_rate", 0) / 100), 2)})
            stock.append((m["id"], ln.qty))
        elif ln.amount > 0 and ln.description.strip():
            lines.append({"description": ln.description.strip(), "qty": 1, "rate": ln.amount, "amount": round(ln.amount, 2)})
    total = round(sum(x["amount"] for x in lines), 2)
    if total <= 0:
        raise HTTPException(400, "Add at least one bill line with an amount")
    key, name, pre = KIND[body.kind]
    done = []
    for mid, q in need.items():
        r = await db.medicines.update_one({"id": mid, "business_id": bid, "qty": {"$gte": q}}, {"$inc": {"qty": -q}})
        if not r.modified_count:
            for d, dq in done:
                await db.medicines.update_one({"id": d}, {"$inc": {"qty": dq}})
            raise HTTPException(409, "Stock changed while billing - please check the quantities and try again")
        done.append((mid, q))
    gst = round(sum(x.get("gst", 0) for x in lines), 2)
    entries = [Entry(ledger_id=body.ledger_id, debit=total), Entry(ledger_id=await sys_ledger(bid, key, name, "direct_income"), credit=round(total - gst, 2))]
    if gst:
        half = round(gst / 2, 2)
        entries += [Entry(ledger_id=await sys_ledger(bid, "cgst", "Output CGST", "duties_taxes"), credit=half),
                    Entry(ledger_id=await sys_ledger(bid, "sgst", "Output SGST", "duties_taxes"), credit=round(gst - half, 2))]
    no = await _next(bid, f"hb_{body.kind}", pre)
    try:
        v = await create_voucher(VoucherIn(voucher_type="receipt", date=body.date, reference_no=no, narration=f"{name} - {p['name']} ({p['reg_no']})", entries=entries), user=user)
    except Exception:
        for d, dq in done:
            await db.medicines.update_one({"id": d}, {"$inc": {"qty": dq}})
        raise
    doc = {"id": new_id(), "business_id": bid, "bill_no": no, "kind": body.kind, "date": body.date, "patient_id": p["id"], "patient": p["name"],
           "reg_no": p["reg_no"], "age": p.get("age", ""), "gender": p.get("gender", ""), "doctor": body.doctor, "admission_date": body.admission_date,
           "discharge_date": body.discharge_date, "lines": lines, "total": total, "gst": gst, "voucher_id": v["id"], "voucher_no": v["voucher_no"], "created_at": now_iso()}
    await db.hospital_bills.insert_one(doc)
    return clean(doc)


@router.get("/hospital/bills")
async def list_bills(patient_id: Optional[str] = None, user=Depends(ANY)):
    q = {"business_id": user["business_id"], **({"patient_id": patient_id} if patient_id else {})}
    return clean(await db.hospital_bills.find(q, NO_ID).sort("created_at", -1).to_list(2000))


# ---------- services: recurring bills, TDS ----------
class RecurringIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    party_ledger_id: str
    account_ledger_id: str
    gst_type: Literal["intra", "inter", "none"] = "intra"
    items: List[Item] = Field(min_length=1)
    every_months: int = Field(1, ge=1, le=12)
    next_date: str
    active: bool = True


@router.get("/recurring")
async def list_recurring(user=Depends(ANY)):
    return clean(await db.recurring_bills.find({"business_id": user["business_id"]}, NO_ID).sort("next_date", 1).to_list(1000))


@router.post("/recurring")
async def add_recurring(body: RecurringIn, user=Depends(WRITE)):
    doc = {**body.model_dump(), "id": new_id(), "business_id": user["business_id"], "generated": [], "created_at": now_iso()}
    await db.recurring_bills.insert_one(doc)
    return clean(doc)


@router.put("/recurring/{rid}")
async def edit_recurring(rid: str, body: RecurringIn, user=Depends(WRITE)):
    await _get("recurring_bills", user["business_id"], rid)
    await db.recurring_bills.update_one({"id": rid}, {"$set": body.model_dump()})
    return clean(await _get("recurring_bills", user["business_id"], rid))


def _add_months(d: str, n: int) -> str:
    x = date.fromisoformat(d)
    m = x.month - 1 + n
    y, m = x.year + m // 12, m % 12 + 1
    return date(y, m, min(x.day, calendar.monthrange(y, m)[1])).isoformat()


@router.post("/recurring/run")
async def run_recurring(user=Depends(WRITE)):
    bid, today, made = user["business_id"], date.today().isoformat(), []
    for r in await db.recurring_bills.find({"business_id": bid, "active": True, "next_date": {"$lte": today}}, NO_ID).to_list(1000):
        d = r["next_date"]
        while d <= today and len(made) < 200:
            nd = _add_months(d, r["every_months"])
            # claim this period atomically so parallel runs cannot bill it twice
            if not (await db.recurring_bills.update_one({"id": r["id"], "next_date": d, "active": True}, {"$set": {"next_date": nd}})).modified_count:
                break
            try:
                v = await create_voucher(VoucherIn(voucher_type="sales", date=d, party_ledger_id=r["party_ledger_id"], account_ledger_id=r["account_ledger_id"],
                                                   gst_type=r["gst_type"], items=[Item(**i) for i in r["items"]], invoice_format="service",
                                                   reference_no=r["name"][:40], narration=f"Recurring bill: {r['name']}"), user=user)
            except Exception:
                await db.recurring_bills.update_one({"id": r["id"], "next_date": nd}, {"$set": {"next_date": d}})
                raise
            made.append({"recurring": r["name"], "date": d, "voucher_no": v["voucher_no"], "amount": v["amount"]})
            await db.recurring_bills.update_one({"id": r["id"]}, {"$push": {"generated": {"date": d, "voucher_id": v["id"], "voucher_no": v["voucher_no"]}}})
            d = nd
    return {"created": made}


class TdsIn(BaseModel):
    party_ledger_id: str
    ledger_id: str
    date: str
    gross: float = Field(gt=0)
    tds: float = Field(ge=0)
    section: str = "194J"
    reference: str = ""
    tds_base: float = Field(0, ge=0)


@router.post("/tds/receipts")
async def tds_receipt(body: TdsIn, user=Depends(WRITE)):
    bid = user["business_id"]
    if body.tds >= body.gross:
        raise HTTPException(400, "TDS must be less than the bill amount")
    if body.tds_base and (body.tds_base > body.gross or body.tds > body.tds_base):
        raise HTTPException(400, "TDS base cannot be more than the bill amount, and TDS cannot be more than its base")
    party = await _get("ledgers", bid, body.party_ledger_id)
    await _cash_bank(bid, body.ledger_id)
    entries = [Entry(ledger_id=body.ledger_id, debit=round(body.gross - body.tds, 2)), Entry(ledger_id=party["id"], credit=body.gross)]
    if body.tds:
        entries.append(Entry(ledger_id=await sys_ledger(bid, "tds_receivable", "TDS Receivable", "current_assets"), debit=body.tds))
    v = await create_voucher(VoucherIn(voucher_type="receipt", date=body.date, reference_no=body.reference, entries=entries,
                                       narration=f"Received from {party['name']}, TDS {body.tds:.2f} u/s {body.section}"), user=user)
    doc = {"id": new_id(), "business_id": bid, "party_ledger_id": party["id"], "party": party["name"], "date": body.date, "gross": body.gross,
           "tds": body.tds, "tds_base": body.tds_base or body.gross, "net": round(body.gross - body.tds, 2), "section": body.section, "reference": body.reference,
           "voucher_id": v["id"], "voucher_no": v["voucher_no"], "created_at": now_iso()}
    await db.tds_entries.insert_one(doc)
    return clean(doc)


@router.get("/tds/receipts")
async def tds_list(user=Depends(ANY)):
    return clean(await db.tds_entries.find({"business_id": user["business_id"]}, NO_ID).sort("date", -1).to_list(5000))


# ---------- live demo ----------
class DemoIn(BaseModel):
    industry_type: Ind
    industry_mode: Mode = "complete"


async def seed_sample(bid: str, ind: str):
    t = date.today().isoformat()
    if ind == "college":
        await db.students.insert_many([{"id": new_id(), "business_id": bid, "name": n, "roll_no": r, "course": "B.Com", "batch": "2026-29", "phone": "", "guardian": "",
                                        "address": "", "fine_per_day": 10, "installments": [{"label": "Term 1", "due_date": t, "amount": 15000}, {"label": "Term 2", "due_date": _add_months(t, 6), "amount": 15000}],
                                        "created_at": now_iso()} for n, r in (("Aarav Sharma", "BC-001"), ("Diya Patel", "BC-002"))])
        await db.staff.insert_one({"id": new_id(), "business_id": bid, "name": "Prof. R. Iyer", "designation": "Lecturer", "phone": "", "basic": 40000, "allowances": 8000, "deductions": 2400, "active": True})
    elif ind == "hospital":
        await db.patients.insert_one({"id": new_id(), "business_id": bid, "reg_no": await _next(bid, "patient", "UHID"), "name": "Ramesh Kumar", "age": "52", "gender": "M",
                                      "phone": "", "address": "", "blood_group": "B+", "guardian": "", "created_at": now_iso()})
        await db.medicines.insert_many([{"id": new_id(), "business_id": bid, "name": n, "batch": b_, "expiry": e, "qty": q, "mrp": m, "gst_rate": 12, "created_at": now_iso()}
                                        for n, b_, e, q, m in (("Paracetamol 500mg", "PCM24A", _add_months(t, 14), 200, 2), ("Amoxicillin 250mg", "AMX11", _add_months(t, 2), 60, 9))])
    elif ind == "retail":
        await db.stock_items.insert_many([{"id": new_id(), "business_id": bid, "name": n, "name_lower": n.lower(), "hsn": "", "unit": "Nos", "gst_rate": g, "sale_rate": s, "purchase_rate": round(s * 0.8, 2),
                                           "opening_qty": q, "opening_rate": round(s * 0.8, 2), "reorder_level": 5, "barcode": bc, "mrp": s, "active": True, "created_at": now_iso()}
                                          for n, s, g, q, bc in (("Tata Salt 1kg", 28, 5, 40, "8901058000017"), ("Parle-G 250g", 25, 18, 4, "8901719110016"), ("Amul Butter 100g", 58, 12, 20, "8901262010016"))])


DEMO_COLLECTIONS = ("settings", "financial_years", "ledgers", "vouchers", "stock_items", "students", "fee_receipts", "staff", "payroll_runs", "patients",
                    "medicines", "hospital_bills", "recurring_bills", "tds_entries", "audit_logs")


async def _cleanup_demos():
    cut = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    old = [b["id"] for b in await db.businesses.find({"demo": True, "created_at": {"$lt": cut}}, {"_id": 0, "id": 1}).to_list(500)]
    if old:
        for c in DEMO_COLLECTIONS:
            await db[c].delete_many({"business_id": {"$in": old}})
        await db.users.delete_many({"business_id": {"$in": old}})
        await db.businesses.delete_many({"id": {"$in": old}})


@router.post("/public/demo")
async def demo(body: DemoIn, request: Request):
    # real client: Cloudflare's header, else the hop left of the two trusted proxies (Cloudflare edge, load balancer)
    xff = [x.strip() for x in (request.headers.get("x-forwarded-for") or "").split(",") if x.strip()]
    ip = request.headers.get("cf-connecting-ip") or (xff[-3] if len(xff) >= 3 else (xff[0] if xff else (request.client.host if request.client else "")))
    now = time.time()
    if await db.demo_hits.count_documents({"ip": ip, "ts": {"$gt": now - 3600}}) >= 10:
        raise HTTPException(429, "Too many demo sandboxes from your network. Please try again in an hour, or start a free trial.")
    await db.demo_hits.insert_one({"ip": ip, "ts": now})
    await db.demo_hits.delete_many({"ts": {"$lt": now - 7200}})
    await _cleanup_demos()
    ind, mode = industry_of(body.model_dump())
    email = f"demo-{secrets.token_hex(5)}@demo.easybooks.in"
    biz = await create_business(f"Demo {INDUSTRIES[ind]['label']}", email, state="27-Maharashtra", industry_type=ind, industry_mode=mode, demo=True)
    user = {"id": new_id(), "business_id": biz["id"], "name": "Demo User", "email": email, "role": "admin", "active": True, "demo": True,
            "password_hash": hash_password(secrets.token_urlsafe(16)), "created_at": now_iso()}
    await db.users.insert_one(user)
    await seed_sample(biz["id"], ind)
    return {"token": create_token(user), "user": clean({k: v for k, v in user.items() if k != "password_hash"})}


@router.post("/industry/sample-data")
async def sample_data(user=Depends(ADMIN_WRITE)):
    b = await get_business(user["business_id"])
    ind, _ = industry_of(b)
    if ind not in ("retail", "college", "hospital"):
        raise HTTPException(400, "There is no sample data for this industry")
    claim = await db.businesses.update_one({"id": b["id"], f"sample_loaded.{ind}": {"$exists": False}}, {"$set": {f"sample_loaded.{ind}": now_iso()}})
    if not claim.modified_count:
        raise HTTPException(409, "Sample data for this industry is already loaded")
    await seed_sample(b["id"], ind)
    return {"ok": True, "industry": ind}


@router.get("/public/industries")
async def industries():
    return {"industries": {k: {**v, "plans": [p for p in PLANS.values() if p.get("industry") == k]} for k, v in INDUSTRIES.items()}, "modes": MODE_LABEL}
