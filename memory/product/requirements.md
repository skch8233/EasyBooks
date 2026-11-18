# Requirements: Easy Books Accounting

## Core Value
"Build a complete, simple and professional accounting and bookkeeping software similar to Tally Prime, but with a much easier user interface."

## Personas & Roles
Small businesses, traders, wholesalers and shop owners in India.
User login and permissions; role-based access.

## Features
1. Dashboard: Total sales, Total purchases, Cash balance, Bank balance, Customer outstanding, Supplier outstanding, Monthly income and expenses
2. Voucher Entry — simple entry screens for: Payment, Receipt, Sales, Purchase, Contra, Journal, Debit Note, Credit Note
3. Ledger Management: Create unlimited ledgers; Customer accounts; Supplier accounts; Cash account; Bank accounts; Expense accounts; Income accounts; Opening balances; Automatic ledger posting
4. Accounting Engine: Implement proper double-entry bookkeeping. Every voucher must have balanced debit and credit entries. Automatically update ledgers and balances. Prevent unbalanced vouchers from being saved. Maintain transaction history. Allow editing and cancellation with audit history.
5. Reports: Day Book, Cash Book, Bank Book, Ledger Statement, Trial Balance, Profit and Loss Account, Balance Sheet, Receivables, Payables, Sales Register, Purchase Register
6. Other Features: Financial year management, Automatic voucher numbering, Date-wise transaction search, Party-wise search, Excel and PDF export, Print reports, Data backup and restore, User login and permissions
7. Indian Accounting Requirements: INR currency, Indian date format DD-MM-YYYY, GST-ready sales and purchase entries, CGST, SGST and IGST ledgers, Optional GSTIN and HSN/SAC fields, Configurable GST rates

## Critical user flow
"First build the complete working MVP with dashboard, ledger creation, voucher entry and basic reports. Test the accounting calculations before adding advanced features."
(Phase 1 = MVP; then remaining features from the list above.)

## UI/UX Rules
Very clean and simple interface. Professional accounting software appearance. Easy-to-use entry forms. Large buttons and readable tables. Desktop, tablet and mobile compatibility (responsive web app). Minimal clicks for daily transactions.

## Technical
Use a proper database. Secure authentication. Role-based access. Reliable accounting calculations. Automatic database validation. Test all debit and credit calculations. Never allow deletion of financial records without maintaining an audit trail.

## Round 2 — user's request (build now)
"Subscription Plans: Add trader sign-up with 30-day free trial and Razorpay annual plans at ₹6,500 and ₹10,000
Offline Licence Keys: Add annual licence keys for the offline version, with activation and expiry alerts
GST Returns Summary: Show GSTR-1 and GSTR-3B summaries so traders can file GST easily every month
Branded Invoices: Let traders print sales invoices with their logo, GSTIN and a UPI payment QR code"
- Each trader business gets its own sign-up and separate books (multi-business), per "offer it to other traders and shop owners".
- Pricing/trial details: see Next Round section above (₹6,500 + 18% GST for 1+1 free user; ₹10,000 + 18% GST for 3 to 8 users; 30-day free trial).
- Razorpay: user's own Razorpay account; request keys from user via secrets when needed.

## Round 8 — user's request (build now) — OFFLINE licensing redesign
User's words (verbatim):
"for offline software, Act as a software developer and licensing expert. I need you to design a licensing and authentication workflow for a desktop accounting software application that operates entirely offline.
1. Initial Installation & Grace Period (First 30 Days):
- Upon downloading and installing the software, the user should be granted complete, unrestricted access to all features for the first 30 days without needing to create or enter a Login ID / Password repeatedly.
- The software must securely track the installation date locally (or via a secure hidden token) to prevent users from simply altering their system clock to bypass the trial.
2. Post-30-Day Paywall:
- Exactly after the 30-day trial expires, the software must block access and prompt the user to enter a valid "Subscription Key."
- To get this key, the user must make a payment. Once payment is verified, a valid subscription key is generated.
3. License Validation (Single-User vs. Multi-User):
- Single-User License: The key must be tied to a unique hardware ID (HWID) or MAC address, ensuring it works completely offline but only on that specific local system.
- Multi-User License: The key should allow activation on a predefined number of allowed systems (e.g., up to 3 or 5 machines) using local network validation or a multi-activation key structure.
4. Offline Authentication Continuity:
- Even when the subscription key is active, the software should not require a daily online login ID or password. Once activated locally with the key, it must work completely offline.
Provide the pseudo-code, database schema logic for tracking the trial period securely offline, and the architectural design for the key validation process.
and there should be an option to change the financial year for which accounting is done on the user basis and provide the .exe file of offline software in a link"

User decisions:
- Offline multi-user licence: up to 8 computers per key.
- Offline multi-user price: ₹18,000 + GST first year, then ₹10,000 + GST renewal. (Single-user offline stays ₹12,000 + GST first year, ₹6,500 + GST renewal.) Both offline tiers purchasable on /buy.
- Offline login: "No login at all, the app opens straight to the books".
- Financial year: user picked both — "Each user picks their own working year, and the app remembers it per user; One year for the whole company, which any user can switch". Interpreted: company default year that anyone can switch, and each user's/PC's own chosen working year is remembered.
- Deliver the design (pseudo-code, trial-tracking schema, key validation architecture) as a readable document in the repo (e.g. offline/LICENSING-DESIGN.md) and implement it in the offline app.
- .exe: GitHub build succeeded and EasyBooksSetup.exe is on the user's Releases page. Make sure the new version builds the same way.

## Round 7 — user's request (build now)
User: "provide me single click download and install"
User approved: "yes but i dont have website now will do it later i have github account"
- Website address: none yet — keep a placeholder that is easy to change later (one place), and document how to change it.
- User has a GitHub account; they will use Save to GitHub.
- Build: automatic cloud build of the Windows .exe via GitHub Actions (Windows runner) when code is saved to GitHub, published to GitHub Releases; the /download page links to the latest .exe for one-click download; one-click installer (no setup questions, desktop shortcut, auto-launch).
- Give the user simple non-technical steps for what to click on GitHub.

## Round 6 — user's request (build now)
"One PC Lock: Make each offline licence work on only one computer so keys can't be shared
Email Keys: Send every buyer their licence key and GST invoice by email right after payment"
- Email: use Resend (Emergent-managed).

## Round 5 — user's request (build now)
"Offline Windows Version: Build the standalone offline version with licence keys and a website download page
Online Key Purchase: Let traders buy every plan on the website and get their key right away"
- See all offline details below (standalone, no sync; ₹12,000 first year, then ₹6,500 + GST renewal key required yearly; .exe download page; keys from website after payment).
- GST on ₹12,000 not confirmed by user — default assumed: ₹12,000 + 18% GST (consistent with other plans); keep it easy to change.
- The .exe itself must be packaged outside Emergent: provide the offline app source ready to package, plus simple step-by-step packaging instructions for the user, and a download page where the .exe can be uploaded/linked.
- Razorpay keys still not added; payments stay off until added.

## Round 5 — queued (user's words)
User was offered: (a) installable desktop app that works with internet + download page, (b) fully offline Windows installer like Tally. User said: "both"
- Fully offline Windows installer is a bigger separate project; the code needs packaging outside Emergent. It must use the existing licence key activation/expiry.
- Offline version: "stay a completely separate standalone product" (no sync with the online version).
- Offline pricing (user's words): "offline version use the 12000 annual price and also need compulsory subscription key to work after 1 year which will cast 6500+gst annually"
  - Interpreted: first year ₹12,000; from year 2, the software requires a renewed annual key at ₹6,500 + 18% GST per year to keep working. (GST on the ₹12,000 to be confirmed.)
- User's words: "also provide the exe file for offline software download link and get annual subscription key for every plan online from website after payment fees"
  - Website download page for the offline .exe (file to be packaged outside Emergent, then hosted/linked here).
  - Every plan (online plans + offline first-year + offline renewal) can be bought on the website and the annual key is shown/sent right after payment.

## Round 4 — user's request (build now)
"Stock Management: Add stock items so traders see quantity on hand after every sale and purchase
Payment Reminders: Send customers WhatsApp reminders for overdue bills with a UPI payment link"
- Then (Round 4b, built separately by mobile specialist after this): "Mobile App: Turn Easy Books into a proper phone app traders can install and use daily"

## Round 3 — user's request (build now)
"Hannusoft Branding: Add the Hannusoft logo and "All rights reserved to Hannusoft Private Limited" across the app
Razorpay Payments: Turn on live UPI and card payments so traders can buy plans themselves
Pricing Landing Page: Make a public Easy Books page showing features, both plans and a free-trial button
WhatsApp Invoice Sharing: Let traders send any sales invoice to customers on WhatsApp in one tap"
- Also finish the interrupted retest of Round 2 fixes.
- Razorpay keys: user will add via secure secrets card (RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET).
- Logo image file is not available in the environment yet; recreate it faithfully from the description below until the user uploads the file.
"this is our company hannusoft private limited logo and use all right reserved to hannusoft private limited"
- Logo: Hannusoft Private Limited (round gradient pink-orange "H" icon, "Hannu" dark navy + "soft" orange, "PRIVATE LIMITED" grey). Show as the software maker's branding, plus "© All rights reserved to Hannusoft Private Limited". Logo image file to be obtained from user upload.

## Next Round (after MVP) — user's words
"offer it to other traders and shop owners"
"I want to make a two version of this software one is offline with annually subscription key and other is online mobile app as well as for dextop with annually subscription fees"
- Needs: multi-business sign-up with separate data per business; annual subscription; licence key for the offline version. Details to be confirmed with user.
- Annual fee: traders pay online by UPI or card inside the app (Razorpay — India; needs user's own Razorpay account/keys).
- Pricing (user's words): "annual subscription fees= 6500+18%gst for single user plus 1 free and more than 2 user upto 8 annually subscription fees = 10000 + 18%gst"
  - Interpreted: Plan 1 = ₹6,500 + 18% GST/year, 1 user + 1 free user (2 users). Plan 2 = ₹10,000 + 18% GST/year, 3 to 8 users.
- Free trial: "yes 30 days free trial"

## Integrations
Login: Email and password (default assumed).

## Round 9 — ERP (build in phases) — user's request verbatim
"Build a Complete Project-Wise ERP Management System
Act as an expert ERP architect and full-stack developer. Build a modern, professional, fully functional, responsive, project-wise ERP system for business management.
IMPORTANT: My accounting software is already prepared. Do not rebuild or duplicate accounting features. Develop the remaining ERP modules and integrate them with the existing accounting software through secure APIs or database integration.
1. Dashboard: total projects, active/completed projects, client information, total quotations, invoices, purchases, expenses, outstanding payments, project profitability and recent activities.
2. Project Management: Create unlimited projects with unique project codes. Client, project manager, location and description. Start date, completion date and contract value. Project status: Planning, Running, On Hold, Completed and Cancelled. Project-wise income, purchases, expenses and profitability. Upload project documents. Individual dashboard for every project.
3. Client & Vendor Management: Client and vendor master databases. Company name, GSTIN, PAN, address, state, contact person, mobile and email. Opening balances and payment terms. Multiple projects under one client. Complete transaction and document history.
4. Sales Quotation Generator: Create professional quotations with automatic or manual quotation numbers. Three optional quotation designs. Client and project selection. Item descriptions, quantities, rates, discounts and GST. Scope of work, delivery and payment terms. Live preview before saving. Edit, duplicate, cancel, print and download PDF. Save drafts and track Sent, Accepted, Rejected and Expired status. Convert accepted quotations into sales orders, projects or invoices.
5. Advanced Invoice Generator: three formats: Classic Professional, Modern Corporate, Detailed Project Invoice. Include: Company logo and details. Client and project details. Automatic or manual invoice numbering. Invoice date and due date. Item descriptions, quantity, rate and discount. CGST, SGST and IGST. Previous billing, current billing and cumulative billing. Retention, advance adjustment and deductions. Bank details, terms and authorized signature. Amount in words.
Mandatory: Live preview before finalizing. Switch between all three formats without re-entering information. Preview must match the final PDF. Save draft and edit drafts. Authorized editing of finalized invoices with version history. Cancel invoice with reason and confirmation. Delete drafts only; preserve finalized invoice audit history. Duplicate invoice into a new draft. Print and download PDF. Share through email or WhatsApp where supported. Full and partial payment tracking. Credit notes and debit notes. Overdue invoice tracking. Prevent duplicate invoice numbers. Never reuse cancelled invoice numbers.
6. Purchase & Procurement Management:
Purchase Requisition (PR): Request materials or services project-wise, with approval and status tracking.
Request for Quotation (RFQ): Send quotation requests to multiple vendors.
Vendor Quotations: Record and compare vendor prices, discounts, GST, delivery times and payment terms.
Comparative Statement: Compare multiple vendors, highlight lowest quotations and allow authorized vendor selection.
Purchase Order (PO): Generate professional purchase orders with three optional formats, automatic/manual numbering, live preview, edit, duplicate, approval, cancellation, printing and PDF download.
Goods Receipt Note (GRN): Record received, accepted, rejected and pending quantities. Support partial deliveries and multiple GRNs against one PO.
Purchase Bills: Record vendor invoices, link them with PO and GRN, prevent duplicate vendor invoice numbers and track pending bills.
7. Expense Management: Project-wise expense vouchers. Expense categories. Vendor/person paid. Date, amount, GST and payment mode. Upload bills and receipts. Expense reports.
8. Project-Wise Tracking: Every project has a separate dashboard showing: Contract value. Quotations and sales orders. Total invoices and billed amount. Payments received. Outstanding client balance. Purchase orders. Material received. Purchase bills. Project expenses. Project profitability. Project documents and progress.
9. Reports (Excel and PDF): Project-wise income and expenses. Client and vendor reports. Quotation register. Invoice register. Cancelled invoice report. Outstanding invoices. Purchase requisition register. Vendor comparison report. Purchase order register. Pending delivery report. GRN register. Purchase bill register. PO versus GRN versus bill reconciliation. Project profitability. Include date, project, client, vendor and status filters.
10. Company Settings: Company name, logo, address, GSTIN and PAN. Bank details and authorized signature. Invoice and quotation prefixes. Financial year April–March. Default invoice and quotation templates. GST settings. Terms and conditions. User and role management.
11. User Roles & Permissions: Super Admin, Administrator, Accountant, Project Manager, Data Entry Operator and Viewer roles. Control permissions for creating, editing, approving, finalizing, cancelling and viewing documents. Maintain complete audit logs.
12. Design & Technical: Premium modern corporate interface. Responsive desktop, tablet and mobile design. Simple sidebar navigation. Secure login and role-based access. Relational database with proper document linking. Functional Add, Edit, View, Delete and Search operations. PDF generation and Excel exports. Automatic calculations and validation. Backup and restore. Secure API integration with existing accounting software.
IMPORTANT DEVELOPMENT INSTRUCTIONS: Do not build just a UI prototype. Build fully working modules with real database storage and functional workflows. Keep the entire ERP project-centric. Every quotation, invoice, purchase requisition, RFQ, purchase order, GRN, purchase bill and expense must be linked to the relevant project. Do not duplicate accounting entries. Integrate approved financial transactions with my existing accounting software. Develop in phases, test every module, and ensure all modules work together before final deployment."

User decisions:
- Lives inside Easy Books as a new "Projects / ERP" section (same login; posts approved transactions into the existing Easy Books books — existing ledgers/vouchers are the accounting).
- Access: user answered "Every Easy Books business; Only businesses on a new paid ERP plan" → available to every business, unlocked by a new paid ERP plan at "15000 plus gst" per year.
- Both online and offline (offline Windows build must include ERP too).
- Customers: "A mix of project businesses; Provide option to select industry".

Phasing (build and test each before the next; report after each phase):
- Phase A: ERP section + roles/permissions, Projects (+ per-project dashboard, documents), Client & Vendor masters, Quotations, Advanced Invoices (with accounting posting), ERP dashboard, ERP plan.
- Phase B: Purchase workflow PR → RFQ → Vendor quotes → Comparative statement → PO → GRN → Purchase bills (posting), Expenses.
- Phase C: All ERP reports, company settings additions, backup/restore coverage, offline build inclusion.

## Round 10 — user's request (build now)
User's words: "use these 2 samples as a invoice format in exectly same manner and include accounting also project wise and add a page for e way bill generation and provide accounting reports project wise as well as combined over all basis and final accounts should be in vertical formation with notes of account generation of final account must show final account preparation for company audit, income tax audit, and for other purpose"
Sample invoices (copy layout exactly):
- Goods format: https://customer-assets-m6fa6gv7.emergentagent.net/job_bharat-books-10--8pob58tc/artifacts/1f46a3b1c2ddc47f_GST_Tax_Invoice_Sample.pdf
- Service provider format: https://customer-assets-m6fa6gv7.emergentagent.net/job_bharat-books-10--8pob58tc/artifacts/5d4ec4cdaf11e30e_GST_Tax_Invoice_Sample__Service_Provider_Format_.pdf
User decisions:
- Invoice formats: "Yes, in both, with the user choosing goods or service format" — both samples become default invoice formats in Easy Books accounting sales invoices AND ERP invoices; user picks goods or service format.
- Accounting project-wise: accounting entries can be tagged to a project; accounting reports available project-wise and combined overall.
- E-way bill: "Fill the e-way bill page, then download a ready JSON file to upload on ewaybillgst.gov.in; also add link of eway bill generation page" (no direct government API).
- Final accounts in vertical format with Notes to Accounts: "Both, chosen by business type" — Companies: Schedule III vertical Balance Sheet and P&L with Notes; Proprietorship/partnership: vertical format with notes. Purpose selection: company audit, income tax audit, and other purpose.
- Income tax audit: "Final accounts with notes only" (no Form 3CD schedules).

## Round 11 — user's request (build now)
"Fixed Asset Depreciation: Work out yearly depreciation on fixed assets and show it in the final accounts notes
Tax Provision: Add an income-tax provision entry so company accounts show tax expense and profit after tax"

## Round 12 — user's request (send after Round 11 fixes)
"and also in invoice generator after enter gst no of buyer automatically fetch comlete detail and after sale bill generated automatically shown in sales voucher"
- GSTIN lookup decision (user's words): "Skip auto-fetch; fill the state and PAN from the GSTIN number itself; fill onece gst information and other detail of buyer next time automatically shown after gstno enter enter"
  - No paid API. On entering a GSTIN: state and PAN fill from the number itself. Once a buyer's details are entered, next time that GSTIN is typed (in any invoice/voucher), all saved buyer details fill automatically.
- Sales voucher: every invoice from the invoice generator appears automatically in Easy Books Sales Vouchers / Day Book "When finalized" (drafts stay out of the books).

## Round 13 — user's request (build now)
"CA Multi-Client Access: Let one CA log in once and prepare final accounts for all their client businesses"

## Offline freeze — UPDATED by user: "First provide offline software till multiple client access then built a site"
- So: the offline Windows version must INCLUDE Round 13 (CA multi-client access). Build a new offline installer with it, and freeze the offline version only AFTER that. Then start the online-only website work (Round 14).

## Offline freeze — earlier wording (superseded by the update above)
"Save offline version till here and now completely online website"
- Freeze the offline Windows version at its current state (current GitHub release stays the final offline installer and the download link keeps working).
- From now on, new work is for the online website only. Future pushes must not rebuild or change the offline installer (make the Windows build manual-only, or build from a frozen tag/branch).

## Round 14 — user's request (build after Round 13) — SaaS website + Super Admin
User uploaded two documents and said "now completely online website":
- SaaS spec (follow it; Part 1 first, verify, then Part 2): https://customer-assets-m6fa6gv7.emergentagent.net/job_bharat-books-10--8pob58tc/artifacts/2b75784064600248_Emergent_SaaS_Build_Prompts___Customer___Super_Admin_Edition.pdf
- Company profile (use for About Us / Vision content on the website): https://customer-assets-m6fa6gv7.emergentagent.net/job_bharat-books-10--8pob58tc/artifacts/aafb1b879f09bd63_Company_Profile_-_About_Us___Vision.pdf
- Keep the existing accounting, ERP, final accounts, GST and e-way bill engine as is (the spec says the core engine must not be broken or removed). Existing decided prices stay unless the spec's pricing is adopted by the user (confirm with E1 if the spec's prices differ).
Round 14 decisions (user):
- Pricing: "New document pricing: Retail ₹5,000; College ₹15,000; Hospital ₹15,000; Wholesale/Service ₹2,500 billing-only or ₹5,000 complete" (all + GST, per year). Replaces old online pricing (₹6,500/₹10,000/₹15,000 ERP). User did not pick ERP as a separate add-on. Offline pricing unchanged (offline frozen).
- User limits: "Yes, keep the user limits" (2 users base vs 3 to 8 users). Price for the 3-8 user tier under new pricing not given yet — keep it configurable in the Super Admin plan manager.
- Industries: "Yes, build all five industries now" (Retail POS, Colleges fees/student directory/payroll, Hospitals OPD/IPD/patient registration/pharmacy batch-expiry, Wholesale, Services) per the spec.
- Existing businesses on old plans keep their current validity.
