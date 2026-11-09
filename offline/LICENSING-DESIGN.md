# Easy Books Offline: licensing and authentication design

This is for the standalone Windows app. It runs fully offline, with no login, a 30-day trial, and Single-PC or Multi-PC subscription keys.

## 1. Architecture

```
          WEBSITE (online, Hannusoft)                       CUSTOMER PC (offline)
 ┌───────────────────────────────────────┐        ┌──────────────────────────────────────┐
 │ /buy → Razorpay → /api/shop/verify    │        │ Electron window (Easy Books.exe)     │
 │   └ issue licence key EB-XXXX-...     │        │  └ local API 127.0.0.1:8765          │
 │   └ email key + GST invoice           │        │      ├ trial_state()  (2 signed      │
 │                                       │        │      │   tokens + forward-only clock)│
 │ /api/shop/activate {key, machine_id}  │◄──1x──►│      ├ offline_status()              │
 │   └ checks PC slots (1 or 8)          │internet│      ├ verify_code() Ed25519 PUBLIC  │
 │   └ signs activation code with        │  or    │      │   key only (cannot sign)      │
 │     Ed25519 PRIVATE key (server only) │ /activate     └ check_pc()  code.m == HWID   │
 │ MongoDB: offline_licences             │  page  │  └ local MongoDB (books)             │
 └───────────────────────────────────────┘        └──────────────────────────────────────┘
```

- **Hardware ID (HWID):** `machine_id() = first 16 hex of SHA-256("easybooks:" + Windows MachineGuid)`, shown as `XXXX-XXXX-XXXX-XXXX`. If no MachineGuid is found, it falls back to `/etc/machine-id`, then the MAC address.
- **Activation code:** `EBOL1.<base64 JSON payload>.<Ed25519 signature>`, with this payload:
  `{k: key, n: name, b: business, p: plan, i: issued, e: expiry, d: max users, t: "single"|"multi", c: max PCs, m: HWID}`
- **Why it can't be forged:** only the website holds the private key. The app ships only the public key, so editing the code breaks the signature. Because the code contains `m`, it only works on that PC.
- **Multi-PC:** this uses a multi-activation key. One licence key has `c` slots (8). Each PC activates once and gets its own code locked to its own HWID. The website counts the used slots. No local network server is needed, so each PC stays fully independent and offline.

## 2. Database schema

### Website (MongoDB `offline_licences`)
```
{ key: "EB-ABCD-...", tier: "single"|"multi", max_pcs: 1|8, plan, expires: "YYYY-MM-DD",
  name, email, phone, gstin, business_name,
  machines: [ { id: "1A2B-...", at: ISO time } ],        // ≤ max_pcs
  history: [ { plan, issued, expires, source, payment_id } ],
  last_invoice, last_email, created_at }
```
Related collections:
- `hs_invoices`: GST invoices.
- `shop_orders`: Razorpay orders.
- `counters`: invoice numbering.

### Customer PC (trial and licence state, no server)
| Where | What |
|---|---|
| `%APPDATA%\Easy Books\data\licence.json` | `{ "trial": <token>, "code": <activation code>, "last_seen": date }` |
| `HKCU\Software\Hannusoft\EasyBooks\cfg` (registry; kept after uninstall) | `<token>` (shadow copy) |

The trial token is `base64(JSON{i: install date, s: last seen date, m: HWID}).HMAC-SHA256`. The HMAC key is derived from the HWID and the built-in public key, so a token copied from another PC or edited by hand is rejected.

## 3. Pseudo-code

```python
TRIAL_DAYS = 30; CLOCK_SLACK = 2 days

def trial_state():
    a = verify_hmac(data_file.trial)            # None if missing/edited/other PC
    b = verify_hmac(registry.cfg)
    if not a and not b:
        if data_file or registry had ANY trial value:   # deleted or tampered
            return EXPIRED("trial record removed or changed")
        a = {i: today, s: today, m: HWID}               # genuine first run
    install = min(a.i, b.i)                     # earliest install wins
    last    = max(a.s, b.s)                     # latest date ever seen
    rolled_back = today < last - CLOCK_SLACK    # clock set back
    effective = max(today, last)                # time only moves forward
    write token{i: install, s: effective} to BOTH places   # self-healing
    trial_ends = install + TRIAL_DAYS
    return active = effective < trial_ends and not rolled_back

def offline_status():
    if code saved:
        p = ed25519_verify(code)                # raises if forged
        require p.m == HWID                     # Single/Multi: per-PC code
        if p.e >= effective_today: return ACTIVE(until p.e)
        reason = "licence expired, enter renewal key"
    elif trial_state().active: return TRIAL(days_left)
    return EXPIRED(reason)  # UI: every screen → Licence page; API: all writes 402

# Website: activation (needs internet once, or the /activate page from any device)
def activate(key, hwid):
    lic = find(key); require lic.expires >= today
    if hwid not in lic.machines:
        atomically push hwid only if len(machines) < max_pcs   else 409
    return sign_ed25519({...lic, m: hwid})

# Website: purchase (after Razorpay signature check)
def issue(plan, buyer):
    if plan.renewal: lic = find(buyer.key); require lic.tier == plan.tier
                     lic.expires = max(today, lic.expires) + 365
    else:            lic = new key, tier, max_pcs, expires = today + 365
    invoice = create_gst_invoice(); email(key, invoice, code if exactly 1 PC)
```

### No login (offline continuity)
The offline app calls `POST /api/offline/session` on start. The local server, which listens only on 127.0.0.1, creates the owner account on first run and returns a session token. There is no ID or password, and nothing needs the internet. The only online step is the one-time key activation, which can also be done from a phone using `/activate`.

## 4. Threats and limits
| Attack | Result |
|---|---|
| Set the PC clock back | `effective = max(today, last_seen)`; more than 2 days back blocks access until the date is corrected |
| Delete `licence.json` | Restored from the registry copy; the trial continues from the original install date |
| Delete the registry value | Restored from `licence.json` |
| Edit or copy a token from another PC | HMAC or HWID mismatch: treated as tampered, so the trial ends |
| Copy an activation code to another PC | Rejected: `m` doesn't match that PC's HWID |
| Forge an activation code | Impossible without the website's private Ed25519 key |
| Share a Multi-PC key with more than 8 PCs | The website refuses the 9th activation (409) |
| Delete the data folder AND the registry value AND reinstall | Gives a new 30-day trial. A fully offline app can't prevent this; it needs admin rights plus manual registry work, and the books are lost too |
| Reverse-engineer the HMAC secret for trial tokens | Possible for a skilled attacker; this only extends the trial and can't create a paid licence |

Admins can remove PCs from a key on the website (Platform → Offline licences). A removed PC keeps its signed code until that code expires, because offline codes can't be cancelled remotely.

## 5. Where the code is
- `backend/licensing.py`: `machine_id`, `trial_state`, `offline_status`, `check_pc`, `sign_code` / `verify_code`
- `backend/shop.py`: `issue_offline`, `/shop/activate`, `/offline/session`, `/offline/licence`, admin reset/resend
- `backend/business.py`: `OFFLINE_PLANS` (prices: Single ₹12,000 / ₹6,500, Multi ₹18,000 / ₹10,000, all + 18% GST)
- `frontend/src/pages/OfflineLicence.jsx`: trial and paywall screen; `frontend/src/App.js`: paywall redirect
