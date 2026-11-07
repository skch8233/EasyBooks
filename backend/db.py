import os
import uuid
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]

NO_ID = {"_id": 0}


def clean(doc):
    if isinstance(doc, list):
        return [clean(d) for d in doc]
    if isinstance(doc, dict):
        return {k: v for k, v in doc.items() if k not in ("_id", "password_hash")}
    return doc


def new_id() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def audit(entity: str, entity_id: str, action: str, user: dict, before=None, after=None, note: str = ""):
    await db.audit_logs.insert_one({
        "id": new_id(), "business_id": user.get("business_id"), "entity": entity, "entity_id": entity_id, "action": action,
        "user_id": user.get("id"), "user_name": user.get("name"), "user_email": user.get("email"),
        "before": before, "after": after, "note": note, "timestamp": now_iso(),
    })
