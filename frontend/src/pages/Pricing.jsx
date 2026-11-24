import { Link } from "react-router-dom";
import { Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PublicShell } from "@/components/PublicShell";
import { INDUSTRIES } from "@/lib/industry";

const ROWS = [
  ["retail", "complete", "Complete Set", 5000], ["college", "complete", "Complete Set", 15000], ["hospital", "complete", "Complete Set", 15000],
  ["wholesale", "billing", "Option 1 · Billing Only", 2500], ["wholesale", "complete", "Option 2 · Complete Set", 5000],
  ["services", "billing", "Option 1 · Billing Only", 2500], ["services", "complete", "Option 2 · Complete Set", 5000],
];
const DESC = {
  "wholesale-billing": "Party master, invoices & challans in your existing bill format, e-way bill, sales register.",
  "wholesale-complete": "Existing bill format + full ERP, godown stock, credit limits, GSTR-1, ledgers, final accounts.",
  "services-billing": "Client list, project / retainer invoicing, recurring bills, payment receipts, TDS tracking.",
  "services-complete": "Existing bill format + project expenses, cash/bank book, ledgers, P&L, balance sheet.",
};
const inr = (n) => `₹${n.toLocaleString("en-IN")}`;

export const PricingMatrix = () => (
  <div className="overflow-x-auto rounded-2xl border" data-testid="pricing-matrix">
    <table className="w-full text-left text-sm">
      <thead className="bg-[#0F172A] text-white"><tr><th className="px-5 py-4">Industry</th><th className="px-5 py-4">Plan</th><th className="px-5 py-4">Bill / receipt format & modules</th><th className="px-5 py-4 text-right">Per year</th><th className="px-5 py-4" /></tr></thead>
      <tbody>{ROWS.map(([k, mode, plan, price]) => (
        <tr key={k + mode} className="border-t hover:bg-slate-50" data-testid={`pricing-row-${k}-${mode}`}>
          <td className="px-5 py-4 font-semibold">{INDUSTRIES[k].label}</td><td className="px-5 py-4">{plan}</td>
          <td className="px-5 py-4 text-slate-600">{DESC[`${k}-${mode}`] || `${INDUSTRIES[k].format}. ${INDUSTRIES[k].points.slice(0, 3).join(", ")}.`}</td>
          <td className="px-5 py-4 text-right num whitespace-nowrap"><span className="font-semibold">{inr(price)}</span><div className="text-xs text-slate-500">+ ₹{(price * 0.18).toLocaleString("en-IN")} GST</div><div className="text-xs text-slate-500" data-testid={`pricing-multi-${k}-${mode}`}>3–8 users: {inr(price + 3500)}</div></td>
          <td className="px-5 py-4"><Link to={`/signup?industry=${k}&mode=${mode}`}><Button size="sm" variant="outline" data-testid={`pricing-cta-${k}-${mode}`}>Start trial</Button></Link></td>
        </tr>))}</tbody>
    </table>
    <div className="bg-slate-50 px-5 py-3 text-xs text-slate-600 flex flex-wrap gap-x-6 gap-y-1">
      {["Prices are for 1 user + 1 free user; a 3 to 8 user tier is available", "Renews automatically for 365 days on payment", "GST invoice issued for every purchase"].map((t) => <span key={t} className="flex items-center gap-1"><Check className="h-3.5 w-3.5 text-emerald-600" />{t}</span>)}
    </div>
  </div>
);

export default function Pricing() {
  return (
    <PublicShell>
      <section className="max-w-6xl mx-auto px-5 py-16" data-testid="pricing-page">
        <h1 className="font-heading text-4xl sm:text-5xl font-extrabold tracking-tight">Honest, low-cost annual pricing</h1>
        <p className="mt-4 text-slate-600 max-w-2xl">Pick your industry. Every plan starts with a 30-day free trial with all features, then activates for 365 days the moment your payment is confirmed.</p>
        <div className="mt-10"><PricingMatrix /></div>
        <p className="mt-6 text-sm text-slate-500">Need the standalone Windows software? <Link to="/download" className="text-primary underline">See the offline version</Link>.</p>
      </section>
    </PublicShell>
  );
}
