import { Link, Navigate, useParams } from "react-router-dom";
import { CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PublicShell } from "@/components/PublicShell";
import { IndustryPreview } from "@/components/IndustryPreview";
import { CoreGrid } from "@/pages/Landing";
import { INDUSTRIES, hasModes } from "@/lib/industry";

export default function Solutions() {
  const { industry } = useParams();
  const I = INDUSTRIES[industry];
  if (!I) return <Navigate to="/welcome" replace />;
  return (
    <PublicShell>
      <div data-testid={`solution-page-${industry}`}>
        <section className="bg-[#0F172A] text-white"><div className="max-w-6xl mx-auto px-5 py-16 grid lg:grid-cols-[1.1fr_1fr] gap-10 items-center">
          <div className="fade-up">
            <div className="flex items-center gap-2 text-emerald-400 text-xs font-semibold uppercase tracking-[0.2em]"><I.icon className="h-4 w-4" />{I.label}</div>
            <h1 className="mt-4 font-heading text-4xl sm:text-5xl font-extrabold leading-tight tracking-tight" data-testid="solution-title">Accounting, ERP & GST built for {I.label.toLowerCase()}</h1>
            <p className="mt-5 text-base md:text-lg text-slate-300">{I.tagline}</p>
            <div className="mt-6 text-sm text-slate-400">Bill format: <span className="text-white">{I.format}</span> · <span className="num text-white">{I.price}</span> + GST / year</div>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to={`/signup?industry=${industry}`}><Button className="h-12 px-7 bg-emerald-500 hover:bg-emerald-600" data-testid="solution-trial-button">Start free trial in {I.short} mode</Button></Link>
              <Link to={`/demo?industry=${industry}`}><Button variant="outline" className="h-12 px-7 bg-transparent text-white border-white/30 hover:bg-white/10 hover:text-white" data-testid="solution-demo-button">Open live demo</Button></Link>
            </div>
          </div>
          <IndustryPreview k={industry} />
        </div></section>
        <section className="max-w-6xl mx-auto px-5 py-16 grid gap-10 lg:grid-cols-2">
          <div><h2 className="font-heading text-2xl font-bold">What you get</h2>
            <ul className="mt-6 space-y-3">{I.points.map((p) => <li key={p} className="flex gap-3"><CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0" />{p}</li>)}</ul>
            {hasModes(industry) && <div className="mt-6 rounded-xl border bg-slate-50 p-4 text-sm text-slate-700" data-testid="solution-modes">Two modes: <b>Billing Only</b> at ₹2,500 + GST / year, or the <b>Complete Accounting & Billing Set</b> at ₹5,000 + GST / year. Switch any time in Settings.</div>}
          </div>
          <div><h2 className="font-heading text-2xl font-bold">Your daily workflow</h2>
            <ol className="mt-6 space-y-4">{I.flow.map(([t, d], i) => <li key={t} className="flex gap-4"><span className="h-8 w-8 shrink-0 rounded-full bg-emerald-100 text-emerald-700 font-bold flex items-center justify-center">{i + 1}</span><div><div className="font-semibold">{t}</div><div className="text-sm text-slate-600">{d}</div></div></li>)}</ol>
          </div>
        </section>
        <section className="bg-slate-50 border-y"><div className="max-w-6xl mx-auto px-5 py-16"><h2 className="font-heading text-2xl font-bold">Powered by the same core engine</h2><p className="text-slate-500 mt-1">General ledger, final accounts, GST reports and e-way bill, unchanged for every industry.</p><div className="mt-8"><CoreGrid /></div></div></section>
      </div>
    </PublicShell>
  );
}
