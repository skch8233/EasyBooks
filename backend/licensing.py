import base64
import json
import os
from datetime import date
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

PREFIX = "EBOL1"
OFFLINE = os.environ.get("OFFLINE_MODE") == "1"


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def sign_code(payload: dict) -> str:
    key = Ed25519PrivateKey.from_private_bytes(_unb64(os.environ["LICENCE_SIGNING_KEY"]))
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    return f"{PREFIX}.{body}.{_b64(key.sign(body.encode()))}"


def verify_code(code: str) -> dict:
    try:
        prefix, body, sig = code.strip().split(".")
        if prefix != PREFIX:
            raise ValueError
        Ed25519PublicKey.from_public_bytes(_unb64(os.environ["LICENCE_PUBLIC_KEY"])).verify(_unb64(sig), body.encode())
        return json.loads(_unb64(body))
    except Exception:
        raise ValueError("Invalid activation code")


def _state_path() -> Path:
    d = Path(os.environ.get("EB_DATA_DIR", "."))
    d.mkdir(parents=True, exist_ok=True)
    return d / "licence.json"


def read_state() -> dict:
    p = _state_path()
    return json.loads(p.read_text()) if p.exists() else {}


def save_code(code: str) -> dict:
    payload = verify_code(code)
    st = read_state()
    st.update({"code": code.strip(), "last_seen": max(date.today().isoformat(), st.get("last_seen", ""))})
    _state_path().write_text(json.dumps(st))
    return payload


def offline_status() -> dict:
    st = read_state()
    base = {"status": "expired", "ends_at": None, "days_left": 0, "max_users": 8, "plan": "offline", "licence": None}
    if not st.get("code"):
        return base
    try:
        p = verify_code(st["code"])
    except ValueError:
        return base
    today = date.today()
    last = date.fromisoformat(st["last_seen"]) if st.get("last_seen") else today
    if today > last:
        st["last_seen"] = today.isoformat()
        _state_path().write_text(json.dumps(st))
    days = (date.fromisoformat(p["e"]) - max(today, last)).days
    return {**base, "status": "active" if days >= 0 else "expired", "ends_at": f"{p['e']}T23:59:59+00:00",
            "days_left": max(days, 0), "max_users": p.get("d", 8), "plan": p.get("p", "offline"), "licence": p}
