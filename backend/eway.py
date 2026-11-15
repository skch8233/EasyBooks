import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import ANY, WRITE
from db import db, NO_ID, new_id, now_iso, audit, clean

router = APIRouter(prefix="/api/eway-bills")


class EwayIn(BaseModel):
    source: str = "manual"
    source_id: Optional[str] = None
    data: dict = Field(default_factory=dict)
    ewb_json: dict = Field(default_factory=dict)


class EwbNo(BaseModel):
    ewb_no: str = Field(max_length=40)
    ewb_date: str = ""


@router.get("")
async def list_eway(user=Depends(ANY)):
    rows = await db.eway_bills.find({"business_id": user["business_id"]}, NO_ID).sort("created_at", -1).to_list(500)
    return clean(rows)


@router.post("")
async def save_eway(b: EwayIn, user=Depends(WRITE)):
    doc = {"id": new_id(), "business_id": user["business_id"], **b.model_dump(), "doc_no": str(b.data.get("docNo", "")), "status": "json_ready",
           "ewb_no": "", "created_by": user["name"], "created_at": now_iso()}
    await db.eway_bills.insert_one({**doc})
    await audit("eway_bill", doc["id"], "create", user, note=doc["doc_no"])
    return clean(doc)


@router.put("/{eid}/number")
async def set_number(eid: str, b: EwbNo, user=Depends(WRITE)):
    if not re.match(r"^\d{12}$", b.ewb_no.strip()):
        raise HTTPException(400, "E-way bill number must be 12 digits")
    e = await db.eway_bills.find_one({"id": eid, "business_id": user["business_id"]}, NO_ID)
    if not e:
        raise HTTPException(404, "E-way bill not found")
    await db.eway_bills.update_one({"id": eid}, {"$set": {"ewb_no": b.ewb_no.strip(), "ewb_date": b.ewb_date, "status": "generated"}})
    coll = {"voucher": "vouchers", "erp_invoice": "erp_invoices"}.get(e.get("source"))
    if coll and e.get("source_id"):
        await db[coll].update_one({"id": e["source_id"], "business_id": user["business_id"]}, {"$set": {"gst_meta.eway_bill_no": b.ewb_no.strip()}})
    await audit("eway_bill", eid, "number", user, note=b.ewb_no)
    return {"ok": True}


@router.delete("/{eid}")
async def delete_eway(eid: str, user=Depends(WRITE)):
    await db.eway_bills.delete_one({"id": eid, "business_id": user["business_id"]})
    return {"ok": True}
