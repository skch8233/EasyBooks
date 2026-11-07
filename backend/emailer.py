import ipaddress
import logging
import os
import re
from datetime import date
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

from db import db, new_id, now_iso

logger = logging.getLogger(__name__)
EMAIL_BASE_URL = "https://integrations.emergentagent.com"
GST_RATE = 18

_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = ("reply with your password", "reply with the code", "send your password", "cvv",
             "send us your password", "enter your password below", "confirm your card number",
             "your full card number", "seed phrase", "recovery phrase", "verify your card",
             "social security number", "confirm your bank details")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)


def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)


def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []


def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan()
    scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body:
            raise ValueError(f"Email asks the recipient for credentials: {p!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} ≠ real link host {real!r} (G3)")


async def send_email(*, to: str, subject: str, html: str) -> str | None:
    key, from_name = os.environ.get("EMERGENT_EMAIL_KEY"), os.environ.get("EMAIL_FROM_NAME")
    if not key or not from_name:
        raise HTTPException(503, "Email is not configured")
    _assert_safe_email(subject, html)
    payload = {"to": [to], "subject": subject, "html": html, "from_name": from_name}
    if os.environ.get("EMAIL_REPLY_TO"):
        payload["contact_email"] = os.environ["EMAIL_REPLY_TO"]
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{EMAIL_BASE_URL}/api/v1/email/send", headers={"X-Email-Key": key}, json=payload)
        resp.raise_for_status()
        return resp.json().get("id")
    except httpx.HTTPStatusError as e:
        try:
            code = e.response.json().get("code", "")
        except ValueError:
            code = ""
        if code in ("insufficient_credits", "integration_disabled", "daily_limit_reached"):
            logger.warning(f"Email paused: {code} ({e.response.status_code}): {e.response.text}")
            raise HTTPException(503, "Email is temporarily unavailable")
        logger.error(f"Email send failed: {e.response.status_code} {e.response.text}")
        raise HTTPException(502, "Failed to send email")
    except Exception as e:
        logger.error(f"Email send error: {e}")
        raise HTTPException(500, "Failed to send email")


def _fy(d: date) -> str:
    y = d.year if d.month >= 4 else d.year - 1
    return f"{y}-{str(y + 1)[2:]}"


async def _next_invoice_no() -> str:
    fy = _fy(date.today())
    c = await db.counters.find_one_and_update({"id": f"hs_invoice_{fy}"}, {"$inc": {"seq": 1}}, upsert=True, return_document=True)
    return f"HS/{fy}/{c['seq']:05d}"


def _taxes(base: float, buyer_gstin: str) -> list:
    seller = os.environ.get("SELLER_GSTIN", "").strip().upper()
    gst = round(base * GST_RATE / 100, 2)
    if buyer_gstin and seller and buyer_gstin[:2] != seller[:2]:
        return [("IGST @18%", gst)]
    half = round(gst / 2, 2)
    return [("CGST @9%", half), ("SGST @9%", round(gst - half, 2))]


async def create_invoice(*, buyer: dict, item: str, base: float, licence_key: str, payment_id: str, source: str) -> dict:
    gstin = (buyer.get("gstin") or "").strip().upper()
    taxes = _taxes(base, gstin)
    inv = {"id": new_id(), "number": await _next_invoice_no(), "date": date.today().isoformat(), "buyer": {**buyer, "gstin": gstin},
           "item": item, "sac": "997331", "base": base, "taxes": taxes, "total": round(base + sum(t for _, t in taxes), 2),
           "licence_key": licence_key, "payment_id": payment_id, "source": source, "created_at": now_iso()}
    await db.hs_invoices.insert_one({**inv})
    return inv


def _money(v: float) -> str:
    return f"₹{v:,.2f}"


def _invoice_html(inv: dict) -> str:
    seller, sg, sa = (escape(os.environ.get(k, "")) for k in ("SELLER_NAME", "SELLER_GSTIN", "SELLER_ADDRESS"))
    b = inv["buyer"]
    td = 'style="padding:8px;border:1px solid #e2e8f0;font-size:13px"'
    tdr = 'style="padding:8px;border:1px solid #e2e8f0;font-size:13px;text-align:right"'
    tax_rows = "".join(f'<tr><td {td} colspan="2">{escape(n)}</td><td {tdr}>{_money(v)}</td></tr>' for n, v in inv["taxes"])
    return (f'<table role="presentation" width="100%" style="border-collapse:collapse;margin-top:8px">'
            f'<tr><td style="padding:8px 0;font-size:16px;font-weight:bold" colspan="3">Tax Invoice {escape(inv["number"])}</td></tr>'
            f'<tr><td style="font-size:13px;vertical-align:top;padding-bottom:12px"><b>{seller}</b><br>{sa}{"<br>GSTIN: " + sg if sg else ""}</td>'
            f'<td></td><td style="font-size:13px;vertical-align:top;text-align:right;padding-bottom:12px">Date: {escape(inv["date"])}<br>'
            f'Billed to: <b>{escape(b.get("business_name") or b.get("name", ""))}</b><br>{escape(b.get("name", ""))}'
            f'{"<br>GSTIN: " + escape(b["gstin"]) if b.get("gstin") else ""}</td></tr>'
            f'<tr><td {td}><b>Description</b></td><td {td}><b>SAC</b></td><td {tdr}><b>Amount</b></td></tr>'
            f'<tr><td {td}>{escape(inv["item"])} (1 year)<br><span style="color:#64748b">Licence {escape(inv["licence_key"])}</span></td>'
            f'<td {td}>{inv["sac"]}</td><td {tdr}>{_money(inv["base"])}</td></tr>{tax_rows}'
            f'<tr><td {td} colspan="2"><b>Total paid</b></td><td {tdr}><b>{_money(inv["total"])}</b></td></tr>'
            f'<tr><td colspan="3" style="font-size:12px;color:#64748b;padding-top:6px">Payment reference: {escape(inv["payment_id"] or inv["source"])}</td></tr></table>')


async def email_purchase(*, to: str, name: str, inv: dict, expires: str, code: str | None = None, offline: bool = False) -> dict:
    site = os.environ.get("PUBLIC_APP_URL", "").rstrip("/")
    brand = escape(os.environ.get("EMAIL_FROM_NAME", ""))
    p = 'style="font-size:14px;line-height:1.5;margin:0 0 12px"'
    if offline and code:
        steps = (f'<p {p}>Your activation code for this computer (open Easy Books, go to Licence and paste it):</p>'
                 f'<p style="font-family:Consolas,monospace;font-size:11px;word-break:break-all;background:#f1f5f9;padding:10px;border-radius:6px">{escape(code)}</p>')
    elif offline:
        steps = (f'<p {p}><b>How to activate:</b> install the software, open <b>Licence</b>, enter this licence key and click <b>Activate online</b>. '
                 f'The key locks to that one computer.</p>'
                 + (f'<p {p}>No internet on that PC? <a href="{site}/activate">Get an activation code here</a> using the Machine ID shown on the Licence screen.</p>' if site.startswith("https://") else ""))
    else:
        steps = f'<p {p}>Your subscription is active. Sign in to Easy Books to keep working.</p>'
    html = (f'<table role="presentation" width="100%"><tr><td style="padding:24px;font-family:Arial,sans-serif;color:#0f172a">'
            f'<p {p}>Hi {escape(name)}, thank you for your payment.</p>'
            f'<p {p}>Licence key: <b style="font-family:Consolas,monospace;font-size:16px">{escape(inv["licence_key"])}</b><br>Valid till: <b>{escape(expires[:10])}</b></p>'
            f'{steps}<p {p}>Keep this key safe. You need it for next year\'s renewal.</p>{_invoice_html(inv)}'
            f'<p style="font-size:12px;color:#64748b;margin-top:20px">Sent by {brand}. All rights reserved to Hannusoft Private Limited. '
            f'We never ask for your password or payment details by email.</p></td></tr></table>')
    subject = f"Your Easy Books licence key and GST invoice {inv['number']}"
    try:
        eid = await send_email(to=to, subject=subject, html=html)
        st = {"status": "sent", "email_id": eid, "to": to, "at": now_iso()}
    except Exception as exc:
        logger.error(f"Purchase email failed for {inv['number']}: {exc}")
        st = {"status": "failed", "to": to, "at": now_iso()}
    await db.hs_invoices.update_one({"id": inv["id"]}, {"$set": {"email": st}})
    return st
