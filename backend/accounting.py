from decimal import Decimal, ROUND_HALF_UP
from typing import Literal, Optional, List

from fastapi import HTTPException
from pydantic import BaseModel, Field

GROUPS = [
    {"key": "sundry_debtors", "name": "Sundry Debtors (Customers)", "nature": "asset"},
    {"key": "sundry_creditors", "name": "Sundry Creditors (Suppliers)", "nature": "liability"},
    {"key": "cash", "name": "Cash-in-Hand", "nature": "asset"},
    {"key": "bank", "name": "Bank Accounts", "nature": "asset"},
    {"key": "sales", "name": "Sales Accounts", "nature": "income", "section": "direct"},
    {"key": "purchase", "name": "Purchase Accounts", "nature": "expense", "section": "direct"},
    {"key": "direct_income", "name": "Direct Incomes", "nature": "income", "section": "direct"},
    {"key": "indirect_income", "name": "Indirect Incomes", "nature": "income", "section": "indirect"},
    {"key": "direct_expense", "name": "Direct Expenses", "nature": "expense", "section": "direct"},
    {"key": "indirect_expense", "name": "Indirect Expenses", "nature": "expense", "section": "indirect"},
    {"key": "duties_taxes", "name": "Duties & Taxes (GST)", "nature": "liability"},
    {"key": "capital", "name": "Capital Account", "nature": "liability"},
    {"key": "loans", "name": "Loans (Liability)", "nature": "liability"},
    {"key": "current_liabilities", "name": "Current Liabilities", "nature": "liability"},
    {"key": "fixed_assets", "name": "Fixed Assets", "nature": "asset"},
    {"key": "current_assets", "name": "Current Assets", "nature": "asset"},
]
GROUP_MAP = {g["key"]: g for g in GROUPS}
CASH_BANK = {"cash", "bank"}

VOUCHER_TYPES = {
    "payment": "PMT", "receipt": "RCT", "sales": "SAL", "purchase": "PUR",
    "contra": "CON", "journal": "JRN", "debit_note": "DN", "credit_note": "CN",
}
ITEM_TYPES = {"sales", "purchase", "credit_note", "debit_note"}
VoucherType = Literal["payment", "receipt", "sales", "purchase", "contra", "journal", "debit_note", "credit_note"]

CENT = Decimal("0.01")


def D(x) -> Decimal:
    return Decimal(str(x or 0)).quantize(CENT, ROUND_HALF_UP)


class Entry(BaseModel):
    ledger_id: str
    debit: float = 0
    credit: float = 0


class Item(BaseModel):
    item_id: Optional[str] = None
    unit: str = ""
    description: str = ""
    hsn: str = ""
    qty: float = Field(1, gt=0)
    rate: float = Field(0, ge=0)
    gst_rate: float = Field(0, ge=0, le=100)


class VoucherIn(BaseModel):
    voucher_type: VoucherType
    date: str
    narration: str = ""
    reference_no: str = ""
    entries: List[Entry] = []
    party_ledger_id: Optional[str] = None
    account_ledger_id: Optional[str] = None
    gst_type: Literal["intra", "inter", "none"] = "intra"
    items: List[Item] = []


def bad(msg: str):
    raise HTTPException(400, msg)


def compute_items(v: VoucherIn):
    items, taxable, cgst, sgst, igst = [], D(0), D(0), D(0), D(0)
    for it in v.items:
        amt = D(Decimal(str(it.qty)) * Decimal(str(it.rate)))
        rate = Decimal(str(it.gst_rate)) if v.gst_type != "none" else Decimal(0)
        tax = D(amt * rate / 100)
        c = s = i = D(0)
        if v.gst_type == "intra":
            c = D(tax / 2)
            s = tax - c
        elif v.gst_type == "inter":
            i = tax
        taxable += amt
        cgst += c
        sgst += s
        igst += i
        items.append({**it.model_dump(), "gst_rate": float(rate), "amount": float(amt), "cgst": float(c),
                      "sgst": float(s), "igst": float(i), "total": float(amt + c + s + i)})
    return items, {"taxable": taxable, "cgst": cgst, "sgst": sgst, "igst": igst, "total": taxable + cgst + sgst + igst}


def build_item_entries(v: VoucherIn, ledgers: dict, gst_ledgers: dict):
    if not v.items:
        bad("Add at least one item line")
    party, acct = ledgers.get(v.party_ledger_id), ledgers.get(v.account_ledger_id)
    if not party:
        bad("Select a valid party ledger")
    if not acct:
        bad("Select a valid sales/purchase ledger")
    want = "sales" if v.voucher_type in ("sales", "credit_note") else "purchase"
    if acct["group"] != want:
        bad(f"Account ledger must belong to {GROUP_MAP[want]['name']}")
    items, t = compute_items(v)
    if t["total"] <= 0:
        bad("Voucher total must be greater than zero")
    # side of party: Dr for sales & debit note, Cr for purchase & credit note
    party_dr = v.voucher_type in ("sales", "debit_note")
    lines = [(party["id"], t["total"], party_dr), (acct["id"], t["taxable"], not party_dr)]
    for k in ("cgst", "sgst", "igst"):
        if t[k] > 0:
            if k not in gst_ledgers:
                bad(f"{k.upper()} ledger missing; create it under Duties & Taxes")
            lines.append((gst_ledgers[k], t[k], not party_dr))
    entries = [Entry(ledger_id=lid, debit=float(a) if dr else 0, credit=0 if dr else float(a)) for lid, a, dr in lines if a > 0]
    return entries, items, {k: float(x) for k, x in t.items()}


def validate_entries(vtype: str, entries: List[Entry], ledgers: dict):
    if len(entries) < 2:
        bad("A voucher needs at least one debit and one credit line")
    dr = cr = D(0)
    for e in entries:
        led = ledgers.get(e.ledger_id)
        if not led:
            bad("One of the selected ledgers does not exist")
        d, c = D(e.debit), D(e.credit)
        if d < 0 or c < 0:
            bad("Amounts cannot be negative")
        if (d > 0) == (c > 0):
            bad(f"Line for '{led['name']}' must have either a debit or a credit amount")
        dr += d
        cr += c
    if dr != cr:
        bad(f"Voucher is not balanced: Debit {dr} vs Credit {cr}")
    if not any(e.debit > 0 for e in entries) or not any(e.credit > 0 for e in entries):
        bad("A voucher needs at least one debit and one credit line")
    groups = [(ledgers[e.ledger_id]["group"], e) for e in entries]
    if vtype == "contra" and any(g not in CASH_BANK for g, _ in groups):
        bad("Contra vouchers can only use Cash and Bank ledgers")
    if vtype == "payment" and not any(g in CASH_BANK and e.credit > 0 for g, e in groups):
        bad("Payment must be credited from a Cash or Bank ledger")
    if vtype == "receipt" and not any(g in CASH_BANK and e.debit > 0 for g, e in groups):
        bad("Receipt must be debited to a Cash or Bank ledger")
    return float(dr)
