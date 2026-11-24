import { Store, GraduationCap, Stethoscope, Truck, Briefcase } from "lucide-react";

export const INDUSTRIES = {
  retail: { label: "Retail & Shopkeepers", short: "Retail", icon: Store, tagline: "Fast POS billing, barcode & MRP lookup, thermal receipts and Udhaar reminders.",
    price: "₹5,000", format: "Tailored POS / thermal & GST receipt",
    points: ["Fast POS billing with barcode / MRP lookup", "58mm thermal and A4 GST receipts", "Low-stock alerts on every item", "Customer credit (Udhaar) reminders on WhatsApp", "Full final accounts, GST returns and e-way bill"],
    flow: [["Scan or search", "Type a barcode or item name - MRP and GST fill in."], ["Collect payment", "Cash, UPI or card, posted straight into your cash or bank book."], ["Print receipt", "Thermal receipt in one click, sales register updated."]] },
  college: { label: "Colleges & Institutes", short: "Colleges", icon: GraduationCap, tagline: "Student directory, fee collection with installments and late fines, staff payroll.",
    price: "₹15,000", format: "Tailored student fee receipt",
    points: ["Student directory with course, batch and roll no", "Installment fee plans with automatic late fine", "Fee receipts with installment breakdown", "Monthly staff payroll with payslips", "Full final accounts for your trust or society"],
    flow: [["Add students", "Course, batch, roll no and the fee installments."], ["Collect fees", "Late fine is calculated; receipt prints instantly."], ["Run payroll", "Salary for all staff posted in one entry each month."]] },
  hospital: { label: "Hospitals & Clinics", short: "Hospitals", icon: Stethoscope, tagline: "Patient registration, OPD/IPD and lab billing, pharmacy with batch and expiry.",
    price: "₹15,000", format: "Tailored OPD / IPD, lab & pharmacy receipt",
    points: ["Patient registration with UHID", "OPD, IPD, lab and pharmacy receipts", "Pharmacy stock by batch with expiry alerts", "Expired batches are blocked from sale", "Full final accounts and GST reports"],
    flow: [["Register patient", "UHID is created with age, gender and contact."], ["Bill the visit", "Consultation, lab tests or medicines by batch."], ["Watch expiry", "Batches expiring within 90 days are flagged."]] },
  wholesale: { label: "Wholesalers & Distributors", short: "Wholesale", icon: Truck, tagline: "Your existing GST invoice format, e-way bills, party master and full ERP.",
    price: "₹2,500 / ₹5,000", format: "Existing GST bill format (preserved as-is)",
    points: ["Existing GST tax invoice format, unchanged", "E-way bill JSON for the government portal", "Party master and sales register", "Complete set: full ERP, stock, GSTR-1 and final accounts", "Choose Billing Only or Complete Set"],
    flow: [["Pick the party", "GSTIN fills the party details automatically."], ["Make the invoice", "Your existing GST invoice format, printed or shared."], ["Generate e-way bill", "Upload-ready JSON from the same invoice."]] },
  services: { label: "Service Agencies", short: "Services", icon: Briefcase, tagline: "Project and retainer invoicing, recurring bills, payment receipts and TDS tracking.",
    price: "₹2,500 / ₹5,000", format: "Existing invoice format (preserved as-is)",
    points: ["Client list and project / retainer invoicing", "Recurring monthly bills generated in one click", "Payment receipts with TDS deducted", "Complete set: project expenses, ledgers, P&L and balance sheet", "Choose Billing Only or Complete Set"],
    flow: [["Set up retainers", "Monthly bills for each client on autopilot."], ["Receive payment", "Record TDS deducted by the client in the same entry."], ["Track TDS", "TDS receivable register for your return."]] },
};
export const IND_KEYS = Object.keys(INDUSTRIES);
export const MODES = { billing: "Invoice & Billing Only", complete: "Complete Accounting & Billing" };
export const hasModes = (k) => k === "wholesale" || k === "services";

const ACCOUNTING = ["reports", "year-end", "final-accounts", "gst", "audit", "ca"];
const EXTRA = {
  pos: { to: "/pos", label: "POS Billing", id: "pos", write: true },
  students: { to: "/students", label: "Students & Fees", id: "students" },
  payroll: { to: "/payroll", label: "Staff Payroll", id: "payroll" },
  patients: { to: "/patients", label: "Patients & Billing", id: "patients" },
  pharmacy: { to: "/pharmacy", label: "Pharmacy Stock", id: "pharmacy" },
  recurring: { to: "/recurring", label: "Recurring Bills", id: "recurring" },
  tds: { to: "/tds", label: "Receipts & TDS", id: "tds" },
  salesreg: { to: "/reports/sales-register", label: "Sales Register", id: "sales-register" },
};

// Returns { hide: Set of nav ids, extra: [nav items to insert after Dashboard], labels: {id: label} }
export function navFor(ind = "wholesale", mode = "complete") {
  if (ind === "retail") return { hide: new Set(["erp"]), extra: [EXTRA.pos], labels: { ledgers: "Customers & Suppliers", reminders: "Udhaar Reminders" } };
  if (ind === "college") return { hide: new Set(["erp", "eway", "stock", "reminders"]), extra: [EXTRA.students, EXTRA.payroll], labels: { reminders: "Fee Reminders" } };
  if (ind === "hospital") return { hide: new Set(["erp", "eway", "reminders"]), extra: [EXTRA.patients, EXTRA.pharmacy], labels: {} };
  if (ind === "services") {
    const extra = [EXTRA.recurring, EXTRA.tds];
    if (mode === "billing") return { hide: new Set([...ACCOUNTING, "eway", "stock"]), extra: [...extra, EXTRA.salesreg], labels: { ledgers: "Client List", erp: "Projects & Invoicing" } };
    return { hide: new Set(), extra, labels: { erp: "Projects & Invoicing" } };
  }
  if (mode === "billing") return { hide: new Set([...ACCOUNTING, "erp", "reminders"]), extra: [EXTRA.salesreg], labels: { ledgers: "Party Master" } };
  return { hide: new Set(), extra: [], labels: {} };
}
