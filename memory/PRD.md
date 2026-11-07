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

## Backlog
- P1: Stock/inventory items with HSN master; GSTR-1/3B summaries; aging buckets on receivables
- P1: Multi-company support; FY deletion for empty years
- P2: Invoice templates/logo, email/WhatsApp invoices, bank reconciliation, cheque printing
