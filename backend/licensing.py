import base64
import hashlib
import hmac
import json
import uuid
import os
from datetime import date, timedelta
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
        raise ValueError("This activation code belongs to another computer. Activate this PC with your licence key (Activate online or the /activate page).")


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


TRIAL_DAYS = 30
CLOCK_SLACK_DAYS = 2


def _trial_mac(body: str) -> str:
    secret = hashlib.sha256(f"EB-TRIAL-v1|{machine_id()}|{os.environ['LICENCE_PUBLIC_KEY']}".encode()).digest()
    return hmac.new(secret, body.encode(), hashlib.sha256).hexdigest()


def _pack(t: dict) -> str:
    body = _b64(json.dumps(t, separators=(",", ":")).encode())
    return f"{body}.{_trial_mac(body)}"


def _unpack(tok: str | None) -> dict | None:
    try:
        body, mac = tok.split(".")
        if not hmac.compare_digest(mac, _trial_mac(body)):
            return None
        t = json.loads(_unb64(body))
        return t if t.get("m") == machine_id() else None
    except Exception:
        return None


def _shadow_read() -> str | None:
    if os.environ.get("EB_SHADOW_FILE"):
        p = Path(os.environ["EB_SHADOW_FILE"])
        return p.read_text().strip() if p.exists() else None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Hannusoft\EasyBooks") as k:
            return winreg.QueryValueEx(k, "cfg")[0]
    except Exception:
        p = Path.home() / ".hsebk"
        return p.read_text().strip() if p.exists() else None


def _shadow_write(tok: str) -> None:
    if os.environ.get("EB_SHADOW_FILE"):
        Path(os.environ["EB_SHADOW_FILE"]).write_text(tok)
        return
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Hannusoft\EasyBooks") as k:
            winreg.SetValueEx(k, "cfg", 0, winreg.REG_SZ, tok)
    except Exception:
        (Path.home() / ".hsebk").write_text(tok)


def trial_state(has_data: bool = False) -> dict:
    """Trial anchored in two signed tokens (data folder + registry); clock can only move forward."""
    st, today = read_state(), date.today()
    a, b = _unpack(st.get("trial")), _unpack(_shadow_read())
    if not a and not b:
        if has_data or st.get("trial") or st.get("last_seen") or _shadow_read():
            st["trial"] = "tampered"
            _state_path().write_text(json.dumps(st))
            return {"active": False, "days_left": 0, "tampered": True}
        a = {"i": today.isoformat(), "s": today.isoformat(), "m": machine_id()}
    cands = [t for t in (a, b) if t]
    t = {"i": min(x["i"] for x in cands), "s": max(x["s"] for x in cands), "m": machine_id()}
    last = date.fromisoformat(t["s"])
    rolled_back = today < last - timedelta(days=CLOCK_SLACK_DAYS)
    eff = max(today, last)
    t["s"] = eff.isoformat()
    tok = _pack(t)
    if st.get("trial") != tok:
        st["trial"] = tok
        _state_path().write_text(json.dumps(st))
    if _shadow_read() != tok:
        _shadow_write(tok)
    ends = date.fromisoformat(t["i"]) + timedelta(days=TRIAL_DAYS)
    return {"active": eff < ends and not rolled_back, "days_left": max((ends - eff).days, 0), "ends": ends.isoformat(),
            "installed": t["i"], "rolled_back": rolled_back, "effective_today": eff.isoformat()}


def offline_status() -> dict:
    st = read_state()
    tr = trial_state()
    base = {"status": "expired", "ends_at": None, "days_left": 0, "max_users": 8, "plan": "offline", "licence": None,
            "machine_id": machine_id(), "trial": tr, "alert": True}
    reason = None
    if st.get("code"):
        try:
            p = verify_code(st["code"])
            check_pc(p)
            eff = date.fromisoformat(tr.get("effective_today") or date.today().isoformat())
            days = (date.fromisoformat(p["e"]) - eff).days
            if days >= 0:
                return {**base, "status": "active", "ends_at": f"{p['e']}T23:59:59+00:00", "days_left": days, "alert": days <= 30,
                        "max_users": p.get("d", 8), "plan": p.get("p", "offline"), "licence": p}
            reason = f"Your licence expired on {p['e']}. Enter a renewal key to continue."
        except ValueError as exc:
            reason = str(exc)
    if not reason and tr["active"]:
        return {**base, "status": "trial", "plan": "trial", "ends_at": f"{tr['ends']}T23:59:59+00:00", "days_left": tr["days_left"], "alert": True}
    if not reason:
        reason = ("The trial record was removed or changed on this computer. Enter a subscription key to continue." if tr.get("tampered")
                  else "The system date was set back. Correct the date or enter a subscription key." if tr.get("rolled_back")
                  else "Your 30-day free trial has ended. Enter a subscription key to continue.")
    return {**base, "reason": reason}
