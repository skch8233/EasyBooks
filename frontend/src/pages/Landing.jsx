import { useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { ArrowRight, BarChart3, FileText, Landmark, Package, Scale, ShieldCheck, Truck, Users } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { Button } from "@/components/ui/button";
import { PublicShell } from "@/components/PublicShell";
import { IndustryPreview } from "@/components/IndustryPreview";
import { INDUSTRIES, IND_KEYS } from "@/lib/industry";
import { PricingMatrix } from "@/pages/Pricing";

export const CORE = [
  [Scale, "General ledger & double entry", "Every voucher balanced, with Cash/Bank book, Day Book and Trial Balance."],
  [BarChart3, "Automated final accounts", "P&L, Balance Sheet, Schedule III and notes, depreciation and tax provision."],
  [Landmark, "GST reports", "CGST/SGST/IGST split, GSTR-1 and GSTR-3B summaries, HSN and GSTIN auto-fill."],
  [Truck, "E-way bill generation", "Portal-ready bulk upload JSON straight from your invoice."],
  [Package, "Inventory ERP", "Stock with reorder alerts, projects, quotations, purchase orders and GRNs."],
  [Users, "CA multi-client access", "One CA login prepares final accounts for every client business."],
  [ShieldCheck, "Audit trail & roles", "Admin, accountant and viewer roles. Every edit recorded."],
  [FileText, "Instant PDF & Excel", "Invoices, receipts, e-way bills and balance sheets generated in your browser."],
];

const Hero = () => {
  const [tab, setTab] = useState("retail");
  return (
    <section className="bg-[#0F172A] text-white">
      <div className="max-w-6xl mx-auto px-5 py-16 lg:py-24 grid lg:grid-cols-[1.15fr_1fr] gap-12 items-center">
        <div className="fade-up">
          <div className="text-emerald-400 text-xs font-semibold uppercase tracking-[0.2em]">Accounting · ERP · GST · E-Way Bill</div>
          <h1 className="mt-4 font-heading text-4xl sm:text-5xl lg:text-6xl font-extrabold leading-[1.05] tracking-tight" data-testid="landing-hero-title">Complete Accounting, ERP & GST Compliance Software <span className="text-emerald-400">— Tailored for Your Industry</span></h1>
          <p className="mt-6 text-base md:text-lg text-slate-300 max-w-xl">Automated Final Accounts, Inventory ERP and one-click E-Way Bill generation, with workspaces built for how your business actually works.</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to={`/signup?industry=${tab}`}><Button className="h-12 px-7 text-base bg-emerald-500 hover:bg-emerald-600" data-testid="landing-hero-trial-button">Start 30-day free trial</Button></Link>
            <Link to={`/demo?industry=${tab}`}><Button variant="outline" className="h-12 px-7 text-base bg-transparent text-white border-white/30 hover:bg-white/10 hover:text-white" data-testid="landing-hero-demo-button">Try the live demo</Button></Link>
          </div>
        </div>
        <div className="fade-up space-y-4" style={{ animationDelay: "120ms" }}>
          <div className="flex flex-wrap gap-2" data-testid="landing-industry-tabs">
            {IND_KEYS.map((k) => { const I = INDUSTRIES[k]; return (
              <button key={k} onClick={() => setTab(k)} data-testid={`landing-tab-${k}`}
                className={`flex items-center gap-1.5 rounded-full px-3.5 py-2 text-xs font-semibold transition-colors ${tab === k ? "bg-emerald-500 text-white" : "bg-white/10 text-slate-300 hover:bg-white/20"}`}><I.icon className="h-3.5 w-3.5" />{I.label}</button>); })}
          </div>
          <IndustryPreview k={tab} />
          <Link to={`/solutions/${tab}`} className="inline-flex items-center gap-1 text-sm text-emerald-300 hover:text-emerald-200" data-testid="landing-tab-more">See how it works for {INDUSTRIES[tab].short} <ArrowRight className="h-4 w-4" /></Link>
        </div>
      </div>
    </section>
  );
};

export const CoreGrid = () => (
  <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
    {CORE.map(([I, t, d]) => <div key={t} className="rounded-xl border bg-white p-6 hover:shadow-md hover:-translate-y-0.5 transition-[box-shadow,transform]"><I className="h-6 w-6 text-emerald-600" /><h3 className="mt-4 font-heading font-semibold">{t}</h3><p className="mt-2 text-sm text-slate-600 leading-relaxed">{d}</p></div>)}
  </div>
);

export default function Landing() {
  const { user } = useApp();
  if (user) return <Navigate to="/" replace />;
  return (
    <PublicShell>
      <div data-testid="landing-page">
        <Hero />
        <section className="max-w-6xl mx-auto px-5 py-20" data-testid="landing-industries">
          <h2 className="font-heading text-3xl font-bold tracking-tight">One core engine. Five industry workspaces.</h2>
          <p className="text-slate-500 mt-2 max-w-2xl">Your ledger, GST, final accounts and e-way bill engine stays the same. Labels, bill formats and modules adapt to your sector.</p>
          <div className="mt-10 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
            {IND_KEYS.map((k) => { const I = INDUSTRIES[k]; return (
              <Link key={k} to={`/solutions/${k}`} className="group rounded-2xl border p-6 hover:border-emerald-500 hover:shadow-lg transition-[box-shadow,border-color]" data-testid={`landing-industry-card-${k}`}>
                <I.icon className="h-7 w-7 text-emerald-600" /><h3 className="mt-4 font-heading text-lg font-bold">{I.label}</h3><p className="mt-2 text-sm text-slate-600">{I.tagline}</p>
                <div className="mt-4 flex items-center justify-between text-sm"><span className="num font-semibold">{I.price} <span className="text-slate-500 font-normal">+ GST / yr</span></span><ArrowRight className="h-4 w-4 text-emerald-600 group-hover:translate-x-1 transition-transform" /></div></Link>); })}
          </div>
        </section>
        <section className="bg-slate-50 border-y" data-testid="landing-features"><div className="max-w-6xl mx-auto px-5 py-20">
          <h2 className="font-heading text-3xl font-bold tracking-tight">Core accounting & ERP features</h2><p className="text-slate-500 mt-2">Included in every industry.</p>
          <div className="mt-10"><CoreGrid /></div></div></section>
        <section className="max-w-6xl mx-auto px-5 py-20" data-testid="landing-pricing">
          <h2 className="font-heading text-3xl font-bold tracking-tight">Transparent annual pricing</h2><p className="text-slate-500 mt-2">30-day free trial with every feature. Pay by UPI, card or netbanking. 18% GST extra.</p>
          <div className="mt-10"><PricingMatrix /></div>
        </section>
        <section className="max-w-6xl mx-auto px-5 pb-20 flex flex-wrap items-center justify-between gap-6">
          <div><h2 className="font-heading text-2xl font-bold">Simplifying finance for every business</h2><p className="text-slate-500 mt-1">Set up your industry workspace in under 2 minutes.</p></div>
          <Link to="/signup"><Button className="h-12 px-8 text-base" data-testid="landing-footer-trial-button">Start free trial</Button></Link>
        </section>
      </div>
    </PublicShell>
  );
}
