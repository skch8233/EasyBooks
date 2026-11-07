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
