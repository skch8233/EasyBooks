# Easy Books Accounting — PRD

## Original problem
Read /app/memory/product/requirements.md: a simple, professional Tally Prime–like accounting app for Indian SMBs (dashboard, 8 voucher types, ledgers, double-entry engine with audit, 11 reports, FY management, export/print, backup/restore, roles, INR, DD-MM-YYYY, GST).

## User choices
JWT email/password; roles Admin / Accountant / Viewer; single company + FY management; clean professional light theme.

## Architecture
- Backend FastAPI + MongoDB: auth.py (JWT Bearer, bcrypt, lockout by email, users), accounting.py (groups, GST compute, Decimal validation), routes_ledgers.py, routes_vouchers.py (numbering via counters, edit/cancel + audit), routes_reports.py (TB, P&L, BS, statement, outstanding, registers, dashboard), routes_admin.py (settings, FY, audit logs, backup/restore with pre-restore snapshot, seed).
- Frontend React + shadcn: Dashboard, VoucherEntry (simple/multi-line/items-GST), Vouchers list + dialog (print/edit/cancel), Ledgers, Reports (11 tabs, Excel via xlsx, PDF via jspdf-autotable, print), Settings (company/GST rates, FY, users, backup, password), Audit Trail.

## Implemented (07-11-2026)
- All Phase 1 + listed features; testing iteration 1: the backend passed 94% and the frontend about 95%. All issues found were fixed afterwards and checked by hand (lockout, report race, next-number/dashboard validation, banner reset, decimal storage, restore snapshot).

## Round 2 (07-11-2026)
- Multi-business signup + 30-day trial (business.py), plans basic ₹6,500+GST (2 users) / pro ₹10,000+GST (8 users), read-only (402) when expired, Razorpay order/verify (billing.py), licence keys + public activate/validate, Platform admin, GSTR-1/3B (gst.py), branded invoices with logo (object storage) + UPI QR.
## Round 3 (07-11-2026)
- Hannusoft branding (SVG recreation in components/Hannusoft.jsx) + copyright on sidebar, footer, login/signup, landing, invoices.
- Public landing/pricing at /welcome (GET /api/public/plans); logged-out users redirected there.
- WhatsApp sharing: POST /api/vouchers/{id}/share -> token; public invoice page /i/:token (GET /api/public/invoice/{token}); buttons in list rows, dialog, post-save banner.
- Razorpay flow complete but DISABLED until RAZORPAY_KEY_ID/RAZORPAY_KEY_SECRET are added.
- Testing iteration 3: 48/48 backend, ~95% frontend; mobile invoice + minor fixes applied after.

## Round 4 (07-11-2026)
- Stock management (stock.py): stock items with HSN/unit/GST/rates/opening/reorder level; on hand = opening + purchases + credit notes - sales - debit notes (active vouchers); avg cost value, low/negative flags, movements ledger; ItemPicker in item vouchers with a shortage warning; Stock page, Stock Summary report, dashboard alert.
- Payment reminders (reminders.py): FIFO bill-wise outstanding, due = bill date + ledger credit_days (default from settings, 30); /reminders page with a WhatsApp Remind button (wa.me + /pay/<token> link); public /pay/:token page with a UPI deep link + QR, live dues; reminders logged + audit.
- Testing iteration 4: 66/66 backend, 100% frontend flows; minor design fixes applied.

## Round 5 (07-11-2026)
- Offline Windows product (standalone, no sync): OFFLINE_MODE backend (licence from a signed Ed25519 activation code, licensing.py; read-only without a valid code; local logo storage; first-run signup only), /app/offline (Electron shell + bundled mongod + PyInstaller server + packaging README).
- Offline plans: first year ₹12,000 + GST, compulsory renewal ₹6,500 + GST/yr (business.OFFLINE_PLANS). Website /buy (all plans, Razorpay checkout -> key + activation code + .lic download), /download page (link set in Platform Admin), Platform manual issue + list.
- Testing iteration 5: 81/81 online + 8/8 offline harness; fixes applied after.

## Backlog
- P0: Razorpay keys; package & upload the .exe; email the key after purchase
- P1: Bind offline activation to a machine id; relax email validation offline
- P0: Add Razorpay keys and test live checkout; replace SVG logo with user's real Hannusoft logo file
- P1: Share-link revocation/expiry; B2CL split in GSTR-1; offline desktop app build
- P1: Stock/inventory items with HSN master; GSTR-1/3B summaries; aging buckets on receivables
- P1: Multi-company support; FY deletion for empty years
- P2: Invoice templates/logo, email/WhatsApp invoices, bank reconciliation, cheque printing
