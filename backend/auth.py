import os
from datetime import datetime, timezone, timedelta
from typing import Literal, Optional

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr

from db import db, NO_ID, new_id, now_iso, audit, clean

ALG = "HS256"
Role = Literal["admin", "accountant", "viewer"]
router = APIRouter(prefix="/api/auth")
users_router = APIRouter(prefix="/api/users")


def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()


def verify_password(p: str, h: str) -> bool:
    return bcrypt.checkpw(p.encode(), h.encode())


def create_token(user: dict) -> str:
    payload = {"sub": user["id"], "email": user["email"], "type": "access",
               "exp": datetime.now(timezone.utc) + timedelta(hours=12)}
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm=ALG)


async def get_current_user(request: Request) -> dict:
    header = request.headers.get("Authorization", "")
    token = header[7:] if header.startswith("Bearer ") else request.cookies.get("access_token")
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=[ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Session expired, please login again")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    user = await db.users.find_one({"id": payload["sub"]}, {**NO_ID, "password_hash": 0})
    if not user or not user.get("active", True):
        raise HTTPException(401, "User not found or disabled")
    return user


def require_roles(*roles):
    async def dep(user=Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(403, "You do not have permission for this action")
        return user
    return dep


ANY = get_current_user
WRITE = require_roles("admin", "accountant")
ADMIN = require_roles("admin")


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserIn(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: Role = "accountant"


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[Role] = None
    active: Optional[bool] = None
    password: Optional[str] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


@router.post("/login")
async def login(body: LoginIn, request: Request):
    email = body.email.lower()
    ident = email
    att = await db.login_attempts.find_one({"identifier": ident})
    if att and att.get("count", 0) >= 5 and att.get("locked_until", "") > now_iso():
        raise HTTPException(429, "Too many failed attempts. Try again in 15 minutes.")
    user = await db.users.find_one({"email": email}, NO_ID)
    if not user or not verify_password(body.password, user["password_hash"]) or not user.get("active", True):
        count = (att.get("count", 0) if att else 0) + 1
        locked = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
        await db.login_attempts.update_one({"identifier": ident}, {"$set": {"count": count, "locked_until": locked}}, upsert=True)
        raise HTTPException(401, "Invalid email or password")
    await db.login_attempts.delete_many({"identifier": ident})
    return {"token": create_token(user), "user": clean(user)}


@router.get("/me")
async def me(user=Depends(ANY)):
    return clean(user)


@router.post("/logout")
async def logout(user=Depends(ANY)):
    return {"ok": True}


@router.post("/change-password")
async def change_password(body: PasswordChange, user=Depends(ANY)):
    doc = await db.users.find_one({"id": user["id"]})
    if not verify_password(body.current_password, doc["password_hash"]):
        raise HTTPException(400, "Current password is incorrect")
    if len(body.new_password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    await db.users.update_one({"id": user["id"]}, {"$set": {"password_hash": hash_password(body.new_password)}})
    return {"ok": True}


@users_router.get("")
async def list_users(user=Depends(ADMIN)):
    users = await db.users.find({}, {**NO_ID, "password_hash": 0}).sort("created_at", 1).to_list(500)
    return clean(users)


@users_router.post("")
async def create_user(body: UserIn, user=Depends(ADMIN)):
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "A user with this email already exists")
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    doc = {"id": new_id(), "name": body.name, "email": email, "role": body.role, "active": True,
           "password_hash": hash_password(body.password), "created_at": now_iso()}
    await db.users.insert_one(doc)
    await audit("user", doc["id"], "create", user, after={"email": email, "role": body.role})
    return clean(doc)


@users_router.put("/{uid}")
async def update_user(uid: str, body: UserUpdate, user=Depends(ADMIN)):
    target = await db.users.find_one({"id": uid}, {**NO_ID, "password_hash": 0})
    if not target:
        raise HTTPException(404, "User not found")
    if uid == user["id"] and (body.role not in (None, "admin") or body.active is False):
        raise HTTPException(400, "You cannot demote or disable your own account")
    upd = {k: v for k, v in body.model_dump().items() if v is not None and k != "password"}
    if body.password:
        if len(body.password) < 6:
            raise HTTPException(400, "Password must be at least 6 characters")
        upd["password_hash"] = hash_password(body.password)
    await db.users.update_one({"id": uid}, {"$set": upd})
    await audit("user", uid, "update", user, before=target, after={k: v for k, v in upd.items() if k != "password_hash"})
    updated = await db.users.find_one({"id": uid}, {**NO_ID, "password_hash": 0})
    return clean(updated)


async def seed_admin():
    email = os.environ["ADMIN_EMAIL"].lower()
    if not await db.users.find_one({"email": email}):
        await db.users.insert_one({"id": new_id(), "name": "Admin", "email": email, "role": "admin", "active": True,
                                   "password_hash": hash_password(os.environ["ADMIN_PASSWORD"]), "created_at": now_iso()})
