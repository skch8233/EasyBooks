import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import axios from "axios";
import { BookMarked, Check, Crown, FileText, Landmark, MessageCircle, QrCode, Scale, ShieldCheck, KeyRound, BarChart3, Users } from "lucide-react";
import { useApp } from "@/context/AppContext";
import { amt } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { HannusoftLogo, Copyright } from "@/components/Hannusoft";

const FEATURES = [
  [Scale, "Always-balanced double entry", "Sales, purchase, receipt, payment, contra, journal, debit & credit notes. Unbalanced vouchers are never saved."],
  [Landmark, "GST ready", "CGST / SGST / IGST split automatically, GSTIN & HSN fields, and monthly GSTR-1 & GSTR-3B summaries."],
  [BarChart3, "Every report your CA needs", "Day Book, Cash & Bank Book, Ledger, Trial Balance, P&L, Balance Sheet, Receivables, Payables and registers."],
  [QrCode, "Branded invoices with UPI QR", "Your logo, GSTIN and a scan-to-pay UPI QR on every sales invoice."],
  [MessageCircle, "Share on WhatsApp", "Send any sales invoice to your customer on WhatsApp in one tap."],
  [KeyRound, "Online + offline", "Use it in the browser on mobile and desktop, or activate the offline version with your annual licence key."],
  [ShieldCheck, "Full audit trail", "Edits and cancellations are recorded. Financial records are never deleted."],
  [Users, "Team access", "Admin, accountant and view-only roles for your staff."],
  [FileText, "Excel, PDF & print", "Export or print any report, back up and restore your data anytime."],
];

const Plan = ({ p, trialDays }) => (
  <div className={`rounded-2xl border bg-white p-7 flex flex-col gap-4 ${p.key === "pro" ? "border-primary shadow-lg" : ""}`} data-testid={`landing-plan-${p.key}`}>
    <div className="flex items-center justify-between"><h3 className="font-heading text-2xl font-bold">{p.name}</h3>{p.key === "pro" && <span className="flex items-center gap-1 rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800"><Crown className="h-3 w-3" /> Popular for teams</span>}</div>
    <div className="text-slate-600">{p.users_label}</div>
    <div><span className="num text-4xl font-semibold">₹{amt(p.price).replace(".00", "")}</span><span className="text-slate-500"> + 18% GST / year</span></div>
    <div className="text-sm text-slate-500 num" data-testid={`landing-plan-total-${p.key}`}>₹{amt(p.gst)} GST · ₹{amt(p.total)} total per year</div>
    <ul className="space-y-2 text-sm">{["All features included", "Mobile & desktop browser access", `Up to ${p.max_users} users`, "Free updates during the year"].map((t) => <li key={t} className="flex gap-2"><Check className="h-4 w-4 text-emerald-600" /> {t}</li>)}</ul>
    <Link to="/signup" className="mt-auto"><Button className="w-full h-12 text-base" variant={p.key === "pro" ? "default" : "outline"} data-testid={`landing-plan-${p.key}-cta`}>Start {trialDays}-day free trial</Button></Link>
  </div>
);

export default function Landing() {
  const { user } = useApp();
  const [plans, setPlans] = useState(null);
  useEffect(() => { axios.get(`${process.env.REACT_APP_BACKEND_URL}/api/public/plans`).then((r) => setPlans(r.data)).catch(() => {}); }, []);
  if (user) return <Navigate to="/" replace />;
  const days = plans?.trial_days || 30;

  return (
    <div className="min-h-screen bg-white" data-testid="landing-page">
      <header className="sticky top-0 z-20 border-b bg-white/90 backdrop-blur">
        <div className="max-w-6xl mx-auto flex items-center gap-3 px-5 h-16">
          <div className="h-9 w-9 rounded-lg bg-emerald-500 flex items-center justify-center"><BookMarked className="h-5 w-5 text-white" /></div>
          <span className="font-heading text-xl font-extrabold">Easy Books</span>
          <nav className="ml-auto flex items-center gap-2">
            <a href="#pricing" className="hidden sm:inline px-3 py-2 text-sm font-medium text-slate-600 hover:text-slate-900" data-testid="landing-nav-pricing">Pricing</a>
            <Link to="/download" className="px-2 sm:px-3 py-2 text-sm font-medium text-slate-600 hover:text-slate-900" data-testid="landing-nav-download"><span className="sm:hidden">Offline</span><span className="hidden sm:inline">Windows offline</span></Link>
            <Link to="/buy" className="px-2 sm:px-3 py-2 text-sm font-medium text-slate-600 hover:text-slate-900" data-testid="landing-nav-buy">Buy</Link>
            <Link to="/login"><Button variant="ghost" data-testid="landing-signin-button">Sign in</Button></Link>
            <Link to="/signup"><Button data-testid="landing-header-trial-button">Free trial</Button></Link>
          </nav>
        </div>
      </header>

      <section className="bg-[#0F172A] text-white">
        <div className="max-w-6xl mx-auto px-5 py-20 lg:py-28 grid lg:grid-cols-[1.3fr_1fr] gap-12 items-center">
          <div className="fade-up">
            <div className="text-emerald-400 text-sm font-semibold uppercase tracking-widest">Accounting for Indian traders & shop owners</div>
            <h1 className="mt-4 font-heading text-4xl sm:text-5xl lg:text-6xl font-extrabold leading-[1.05] tracking-tight">Tally-grade bookkeeping. <span className="text-emerald-400">Made simple.</span></h1>
            <p className="mt-6 text-lg text-slate-300 max-w-xl">Billing, GST, ledgers and every report in one easy app, on mobile, desktop and offline.</p>
            <div className="mt-9 flex flex-wrap gap-3">
              <Link to="/signup"><Button className="h-13 px-8 py-3.5 text-base bg-emerald-500 hover:bg-emerald-600" data-testid="landing-hero-trial-button">Start {days}-day free trial</Button></Link>
              <a href="#pricing"><Button variant="outline" className="h-13 px-8 py-3.5 text-base bg-transparent text-white border-white/30 hover:bg-white/10 hover:text-white" data-testid="landing-hero-pricing-button">See pricing</Button></a>
            </div>
            <p className="mt-4 text-sm text-slate-400">No card needed · Cancel anytime · Your data stays private to your business</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/5 p-6 space-y-3 fade-up" style={{ animationDelay: "120ms" }}>
            {[["Total Sales", "₹4,82,350.00", "text-emerald-400"], ["GST payable (Oct)", "₹18,420.00", "text-amber-300"], ["Customer outstanding", "₹1,26,900.00", "text-sky-300"]].map(([l, v, c]) => (
              <div key={l} className="rounded-xl bg-white/5 px-5 py-4"><div className="text-xs uppercase tracking-wide text-slate-400">{l}</div><div className={`num text-2xl font-semibold ${c}`}>{v}</div></div>
            ))}
            <div className="text-xs text-slate-500 text-right">Sample dashboard</div>
          </div>
        </div>
      </section>

      <section className="max-w-6xl mx-auto px-5 py-20" data-testid="landing-features">
        <h2 className="font-heading text-3xl font-bold tracking-tight">Everything your shop needs</h2>
        <p className="text-slate-500 mt-2">Built for traders, wholesalers and retailers across India.</p>
        <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(([I, t, d]) => (
            <div key={t} className="rounded-xl border p-6 hover:shadow-md transition-shadow"><I className="h-6 w-6 text-primary" /><h3 className="mt-4 font-heading font-semibold text-lg">{t}</h3><p className="mt-2 text-sm text-slate-600 leading-relaxed">{d}</p></div>
          ))}
        </div>
      </section>

      <section id="pricing" className="bg-slate-50 border-y" data-testid="landing-pricing">
        <div className="max-w-5xl mx-auto px-5 py-20">
          <h2 className="font-heading text-3xl font-bold tracking-tight">Simple annual pricing</h2>
          <p className="text-slate-500 mt-2">Try everything free for {days} days. Then pick a plan and pay by UPI or card.</p>
          <div className="mt-10 grid gap-6 md:grid-cols-2">{plans?.plans.map((p) => <Plan key={p.key} p={p} trialDays={days} />)}</div>
          {plans?.offline_plans && (
            <div className="mt-8 rounded-2xl border bg-white p-6 flex flex-wrap items-center justify-between gap-4" data-testid="landing-offline-plan">
              <div><h3 className="font-heading text-xl font-bold">Offline Windows software</h3>
                <p className="text-sm text-slate-600 mt-1">Standalone, no internet needed. First year ₹{amt(plans.offline_plans[0].price).replace(".00", "")} + GST, then a compulsory renewal key at ₹{amt(plans.offline_plans[1].price).replace(".00", "")} + GST / year.</p></div>
              <div className="flex gap-2"><Link to="/download"><Button variant="outline" className="h-11" data-testid="landing-offline-download">Download</Button></Link>
                <Link to="/buy"><Button className="h-11" data-testid="landing-offline-buy">Buy licence</Button></Link></div>
            </div>
          )}
        </div>
      </section>

      <section className="max-w-6xl mx-auto px-5 py-16 flex flex-wrap items-center justify-between gap-6">
        <div><h2 className="font-heading text-2xl font-bold">Ready to simplify your books?</h2><p className="text-slate-500 mt-1">Set up in under 2 minutes.</p></div>
        <Link to="/signup"><Button className="h-12 px-8 text-base" data-testid="landing-footer-trial-button">Start free trial</Button></Link>
      </section>

      <footer className="border-t">
        <div className="max-w-6xl mx-auto px-5 py-8 flex flex-wrap items-center justify-between gap-4">
          <HannusoftLogo size={34} />
          <Copyright className="!text-sm" />
        </div>
      </footer>
    </div>
  );
}
