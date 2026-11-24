import { Link } from "react-router-dom";
import { Layers, MousePointerClick, IndianRupee, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PublicShell } from "@/components/PublicShell";
import { CoreGrid } from "@/pages/Landing";

const WHY = [
  [Layers, "Complete Financial Suite", "From invoicing and GST compliance to bookkeeping, inventory and payroll, everything your business needs runs seamlessly under one roof."],
  [MousePointerClick, "Built for Simplicity", "Clean, intuitive interfaces mean you spend less time figuring out complex menus and more time growing your business, with no heavy technical training required."],
  [IndianRupee, "Honest, Low-Cost Pricing", "Transparent, budget-friendly plans ensure small and medium businesses get top-tier software capabilities without breaking the bank."],
  [ShieldCheck, "Reliable & Secure", "Engineered for speed, accuracy and compliance so your financial data is always organized, audit-ready and protected."],
];

export function Features() {
  return (
    <PublicShell>
      <section className="max-w-6xl mx-auto px-5 py-16" data-testid="features-page">
        <h1 className="font-heading text-4xl sm:text-5xl font-extrabold tracking-tight">Core accounting & ERP features</h1>
        <p className="mt-4 text-slate-600 max-w-2xl">The same dependable engine powers every industry workspace.</p>
        <div className="mt-10"><CoreGrid /></div>
      </section>
    </PublicShell>
  );
}

export default function About() {
  return (
    <PublicShell>
      <div data-testid="about-page">
        <section className="bg-[#0F172A] text-white"><div className="max-w-5xl mx-auto px-5 py-16">
          <div className="text-emerald-400 text-xs font-semibold uppercase tracking-[0.2em]">Hannusoft · Company overview</div>
          <h1 className="mt-4 font-heading text-4xl sm:text-5xl font-extrabold tracking-tight">About Us & Our Vision</h1>
          <p className="mt-4 text-lg text-emerald-300">Complete Finance Software. Effortless to Use. Built for Your Budget.</p>
        </div></section>
        <section className="max-w-5xl mx-auto px-5 py-14 space-y-4">
          <h2 className="font-heading text-2xl font-bold">Simplifying Finance for Every Business</h2>
          <p className="text-slate-600 leading-relaxed">At Hannusoft, we believe powerful financial management should never come with a steep learning curve or an enterprise price tag. We build complete, end-to-end finance and accounting software designed to make daily operations effortless, accurate and affordable for growing businesses and professionals.</p>
          <p className="text-slate-600 leading-relaxed">Whether managing daily billing, tax compliance or full-scale accounting, our platform eliminates complexity and high subscription costs, delivering speed, accuracy and simplicity from day one.</p>
        </section>
        <section className="bg-slate-50 border-y"><div className="max-w-5xl mx-auto px-5 py-14">
          <h2 className="font-heading text-2xl font-bold">Why Businesses Choose Us</h2>
          <div className="mt-8 grid gap-5 sm:grid-cols-2">{WHY.map(([I, t, d]) => <div key={t} className="rounded-xl border bg-white p-6" data-testid={`about-why-${t.split(" ")[0].toLowerCase()}`}><I className="h-6 w-6 text-emerald-600" /><h3 className="mt-3 font-heading font-semibold">{t}</h3><p className="mt-2 text-sm text-slate-600 leading-relaxed">{d}</p></div>)}</div>
        </div></section>
        <section className="max-w-5xl mx-auto px-5 py-14 grid gap-6 md:grid-cols-2">
          <div className="rounded-2xl border-l-4 border-emerald-500 bg-white p-6 shadow-sm" data-testid="about-mission"><h3 className="font-heading text-xl font-bold">Our Mission</h3><p className="mt-3 text-slate-600">To empower entrepreneurs, accountants and organizations with smart, dependable software that turns complex accounting into simple daily workflows.</p></div>
          <div className="rounded-2xl border-l-4 border-[#0F172A] bg-white p-6 shadow-sm" data-testid="about-vision"><h3 className="font-heading text-xl font-bold">Our Vision</h3><p className="mt-3 text-slate-600">To become the most trusted and accessible financial technology partner for businesses everywhere, democratizing enterprise-grade accounting tools so every organization, regardless of size or budget, can manage its finances with complete confidence and clarity.</p></div>
        </section>
        <section className="max-w-5xl mx-auto px-5 pb-16"><Link to="/signup"><Button className="h-12 px-8" data-testid="about-trial-button">Start your free trial</Button></Link></section>
      </div>
    </PublicShell>
  );
}
