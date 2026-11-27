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

## Round 6 (Nov 2026) - DONE
- One PC lock: offline keys bind to a Machine ID on first activation (/api/shop/activate, /activate page, offline Licence "Activate online"); other PCs 409; codes carry machine id "m" and offline app rejects codes for another PC or unbound (Round 5) codes. Admin Reset PC / Resend email.
- Email keys: Emergent-managed Resend email with licence key + GST tax invoice (HS/FY/NNNNN, SAC 997331, CGST/SGST or IGST) after every offline purchase/renewal, manual issue and online plan payment.
- Placeholders pending from user: SELLER_GSTIN, SELLER_ADDRESS (backend/.env), REACT_APP_LICENCE_SERVER (offline/build_frontend.bat). Razorpay keys still missing (payments off).
- Backlog: rate-limit /api/shop/activate, limit PC resets, downloadable invoice PDF.

## Round 7 (Nov 2026) - DONE
- One-click download & install: GitHub Actions workflow .github/workflows/build-windows.yml (windows-latest) builds UI + PyInstaller server + bundled MongoDB + one-click NSIS installer (no questions, desktop/Start menu shortcut, auto-launch) and publishes EasyBooksSetup.exe to GitHub Releases (v1.0.<run>) on every Save to GitHub.
- /download links to GitHub releases/latest/download/EasyBooksSetup.exe (Platform admin "Use latest GitHub release" helper).
- Website address placeholder in ONE place: offline/build-settings.txt WEBSITE_URL. User steps: offline/GITHUB-STEPS.md.
- Not yet run on real GitHub (needs user's Save to GitHub). Installer unsigned (SmartScreen warning). Repo must be public for customer downloads.
- Backlog: code-signing certificate, clear/unpublish download link.

## Round 8 (Nov 2026) - DONE
- Offline: no login (auto local owner session), 30-day full trial tracked by 2 HMAC-signed tokens (data folder + HKCU registry) with forward-only clock and tamper detection; paywall redirects to Licence after trial/licence expiry.
- Single-PC (₹12,000/₹6,500 + GST) and Multi-PC up to 8 computers (₹18,000/₹10,000 + GST) keys; per-PC Ed25519 codes; admin per-PC removal.
- Financial year: company default year switchable by any user + per-user working year stored server-side.
- Design doc: offline/LICENSING-DESIGN.md. Tests: iteration_8 100%.
- Download default: OFFLINE_DOWNLOAD_URL env + DB -> github.com/skch8233/EasyBooks releases/latest (repo currently not publicly reachable: 404).

## Round 9 ERP - Phase A (Nov 2026) - DONE
- ERP add-on inside Easy Books ("Projects / ERP"), plan ₹15,000+GST/yr (superadmin grant; Razorpay off). Roles + configurable permission matrix (admin, accountant, project_manager, data_entry, viewer).
- Clients/Vendors (auto ledgers), Projects (codes, dashboard, documents in object storage), Quotations (3 templates, statuses, convert to invoice/project/SO), Advanced invoices (retention, advance, deductions, running bills, finalize -> SAL voucher, versioned edits, cancel, payments -> RCT, ECN/EDN notes, email/WhatsApp, overdue), ERP dashboard.
- Backend: erp_core.py, erp_sales.py. Frontend: pages/erp/*, components/erp/*. Tests: tests/test_round9_erp_phase_a.py (10/10).
- Next: Phase B (purchases, expenses, vendor bills feeding project profit), Phase C (reports, offline build inclusion).

## Round 9 ERP - Phase B (Nov 2026) - DONE
- Purchase requisitions (draft/submit/approve/reject/cancel) -> RFQ (multi-vendor, email) -> vendor quotes -> comparative statement (lowest per item/total, reason for non-lowest) -> PO (3 print formats, approve/close/duplicate/cancel, WhatsApp) -> GRN (accepted/rejected, partial/received, cancel) -> purchase bills (limited to accepted-not-billed qty, duplicate vendor invoice check, posts PUR voucher, payments post PMT, cancel reverses).
- Project expenses: categories, GST, post as payment voucher, bill uploads, filters, category summary, Excel export.
- Double-submit protection: per-document lock (409) on bill post/payment, GRN, expense post, PO approve, RFQ->PO; buttons disabled while saving.
- Backend: erp_purchase.py; Frontend: pages/erp/Purchases, RfqView, PoEditor, BillEditor, Expenses. Tests: tests/test_round9_erp_phase_b.py (iteration 10).
- Next: Phase C (ERP reports, offline build inclusion).

## Round 9 ERP - Phase C (Nov 2026) - DONE
- 16 ERP reports (erp_reports.py, /erp/reports): project income & expenses, profitability, client, vendor, quotation/invoice/cancelled/outstanding (ageing), PR register, vendor comparison, PO register, pending delivery, GRN register, purchase bill register, PO vs GRN vs bill reconciliation, expenses. Filters: date, project, client, vendor, status. Excel + PDF.
- Company settings: PAN (validated, on documents), authorised signature image (ERP settings, printed on invoice/quotation/PO), links to Settings tabs (?tab=).
- Backup/restore: all erp_* collections + ERP counters; restore never rolls numbering back ($max).
- Offline: ERP unlocked with offline licence/trial, ERP nav visible offline, ERP modules in GitHub workflow + build_server.bat hidden imports, README updated.
- Tests: tests/test_round9_erp_phase_c.py (iteration 11); A+B+C suites 31/31 pass.

## Round 10 (Nov 2026) - DONE
- GST invoice formats matching user's 2 sample PDFs: goods (lib/gstInvoice.js goods()) and service-provider (service()); default for ERP invoices and accounting sales vouchers, chosen per invoice; GST meta fields (place of supply, RCM, transport, e-way no, vehicle, consignee, contract ref, billing period); public share link uses same format.
- Project tagging on all vouchers (ERP postings auto-tagged, 374 back-filled); project filter on TB/P&L/BS/registers ("none" = untagged); Project-wise P&L report.
- E-way bill page: prefill from invoice, validation, official bulk-upload JSON v1.0.0621 (transType, actualFrom/ToStateCode, OthValue, TotNonAdvolVal, mainHsnCode), portal link, 12-digit EWB number write-back.
- Final accounts (final_accounts.py, /final-accounts): Schedule III for companies, vertical for others; purpose company audit / tax audit 44AB / other; notes + policies, previous year, closing stock, signature blocks, Excel/PDF.
- Voucher items have unit; company business type + CIN.
- Tests: iteration 12-13; run suites serially: pytest -n 0 (57 passed).

## Round 13 - CA Multi-Client Access (Nov 2026)
- One login, many businesses: `memberships` collection (user_id, business_id, role); token carries optional `bid` claim, checked against memberships on every request (revoke is immediate).
- /ca "CA Clients" page: summary per business (year, entries, last entry, depreciation/tax posted, plan) with Open / Dep & Tax / Final accounts buttons; Add client business; business switcher in top bar.
- Business admins grant access to a CA's existing account by email (accountant/admin/viewer), list and revoke; guards on self-change and last admin.
- Offline Windows build includes it (local client businesses, switch remembered across restarts).
- Offline freeze: GitHub workflow publishes release `offline-final` (marked latest) on the next push, then skips all later builds while that release exists.
- Next: Round 14 (SaaS website + Super Admin) queued, not started.

## Round 14 Part 1 + Round 14b (Nov 2026)
- Industry SaaS: 5 industries (retail, college, hospital, wholesale, services; billing/complete modes for wholesale & services), industry stored on business, signup requires industry, Settings > Industry switch + sample data.
- Plans per industry (base 2 users, multi 3-8 users = base + 3,500 placeholder); ERP included except wholesale billing-only; legacy basic/pro kept.
- Public site: home with industry tabs/previews, /solutions/:industry, /pricing, /features, /about, /demo (sandbox, rate-limited by real client IP, 24h cleanup, hidden from Platform Admin).
- Modules: POS (barcode/MRP inclusive, thermal receipt), Students & fees (installments, late fine, fee receipt), Payroll (payslips), Patients & hospital billing (OPD/IPD/Lab/Pharmacy), Pharmacy batches & expiry, Recurring bills (atomic), Receipts & TDS. Billing-only modes blocked from accounting reports (UI + server middleware).
- 14b: grouped collapsible sidebar with up/down arrows (persisted), styled dropdowns (Pick) and DateInput on industry screens.
- Next: Round 14 Part 2 (Super Admin plan manager etc.).

## Round 14 Part 2 - Super Admin (Nov 2026) - DONE
- /super-admin (replaces Platform Admin; /platform redirects): Overview KPIs (orgs, active paid, expiring 7d, revenue 30d/12m, industry breakdown)
- Organizations: search/filters; Extend (+14d trial / +1 month / +1 year / custom days) with amount, method, reference; reference checked before any change; lifting suspension via Extend is an explicit checkbox and audited
- Industry/mode/plan change keeping expiry, seat-limit override, ERP module toggle; suspend/reactivate
- Expiry: 7-day read-only grace, then lock screen (423) "Subscription Expired - Contact Support to Renew"; billing/subscription endpoints stay open
- Support view: reason prompt, read-only token, banner + exit, access log
- Plan manager: edit name/annual/monthly price/max users/on-sale per industry plan (incl. 3-8 user tier), create custom plans (db.plan_settings, loaded at startup)
- Payments & renewals history (online + manual ledger) with UTF-8 BOM CSV export
- Dates parsed timezone-safely everywhere (parse_dt)
- Tests: test_round19_superadmin.py, test_round19b_naive_dates_retest.py; iteration_28/29 all passed

## Backlog
- P1: Delete/archive custom plans without a restart; split manual vs online revenue
- P2: Teardown for TEST_ orgs in older suites

## Round 15 - Offline side menu (Nov 2026) - READY TO PUBLISH
- New offline build = exact offline-final-v1.0.14 commit (d55a429) + offline/round15/side-menu-patch.txt (Layout.jsx only: 4 collapsible groups, down/up arrows, open/closed remembered in localStorage, current page highlighted + auto-opens its group)
- Workflow checks out OFFLINE_BASE, applies the patch, builds, tags the release on the base commit; manual Run workflow only; pushes stay frozen; concurrency split per event so a push cannot cancel a manual build
- Offline-mode React build of base+patch compiled successfully locally
- Online main code unchanged (Round 14 intact)

## Round 16 - Rename to EASYTALLY BOOKS (Nov 2026) - DONE online, offline ready to publish
- All visible branding (screens, page title, emails, invoices/PDF, Razorpay checkout, offline window/installer/shortcut) renamed to "EASYTALLY BOOKS"; Hannusoft branding kept
- Compatibility kept: EasyBooksSetup.exe file name + download link, appId in.hannusoft.easybooks, registry key Software\Hannusoft\EasyBooks, DB name, machine-ID salt, licence key formats; offline userData pinned to old "Easy Books" folder so existing data stays
- Offline build = d55a429 (v1.0.14) + offline/round15/offline-patch.txt (side menu + rename only); regenerate with offline/round15/rename.py
