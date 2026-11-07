import base64
import hashlib
import json
import uuid
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


def _raw_machine() -> str:
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
        return winreg.QueryValueEx(k, "MachineGuid")[0]
    except Exception:
        pass
    for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        if Path(p).exists():
            return Path(p).read_text().strip()
    return str(uuid.getnode())


def machine_id() -> str:
    h = hashlib.sha256(f"easybooks:{os.environ.get('EB_MACHINE_ID') or _raw_machine()}".encode()).hexdigest().upper()[:16]
    return "-".join(h[i:i + 4] for i in range(0, 16, 4))


def check_pc(payload: dict) -> None:
    if not payload.get("m"):
        raise ValueError("This code is not locked to a computer. Use Activate online with your licence key to get a code for this PC.")
    if payload["m"] != machine_id():
        raise ValueError("This activation code belongs to another computer. Each licence works on one PC only.")


def _state_path() -> Path:
    d = Path(os.environ.get("EB_DATA_DIR", "."))
    d.mkdir(parents=True, exist_ok=True)
    return d / "licence.json"


def read_state() -> dict:
    p = _state_path()
    return json.loads(p.read_text()) if p.exists() else {}


def save_code(code: str) -> dict:
    payload = verify_code(code)
    check_pc(payload)
    st = read_state()
    st.update({"code": code.strip(), "last_seen": max(date.today().isoformat(), st.get("last_seen", ""))})
    _state_path().write_text(json.dumps(st))
    return payload


def offline_status() -> dict:
    st = read_state()
    base = {"status": "expired", "ends_at": None, "days_left": 0, "max_users": 8, "plan": "offline", "licence": None, "machine_id": machine_id()}
    if not st.get("code"):
        return base
    try:
        p = verify_code(st["code"])
        check_pc(p)
    except ValueError as exc:
        return {**base, "reason": str(exc)}
    today = date.today()
    last = date.fromisoformat(st["last_seen"]) if st.get("last_seen") else today
    if today > last:
        st["last_seen"] = today.isoformat()
        _state_path().write_text(json.dumps(st))
    days = (date.fromisoformat(p["e"]) - max(today, last)).days
    return {**base, "status": "active" if days >= 0 else "expired", "ends_at": f"{p['e']}T23:59:59+00:00",
            "days_left": max(days, 0), "max_users": p.get("d", 8), "plan": p.get("p", "offline"), "licence": p}
