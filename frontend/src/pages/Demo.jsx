import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { PublicShell } from "@/components/PublicShell";
import { INDUSTRIES, IND_KEYS, MODES, hasModes } from "@/lib/industry";

export default function Demo() {
  const [sp] = useSearchParams();
  const { startDemo } = useApp();
  const [busy, setBusy] = useState("");
  const nav = useNavigate();
  const go = async (industry_type, industry_mode = "complete") => {
    setBusy(industry_type + industry_mode);
    try { await startDemo((await api.post("/public/demo", { industry_type, industry_mode })).data); nav("/"); }
    catch (e) { toast.error(errMsg(e)); setBusy(""); }
  };
  return (
    <PublicShell>
      <section className="max-w-5xl mx-auto px-5 py-16" data-testid="demo-page">
        <h1 className="font-heading text-4xl sm:text-5xl font-extrabold tracking-tight">Live demo</h1>
        <p className="mt-4 text-slate-600 max-w-2xl">Open a private sandbox with sample data for your industry. No signup needed; nothing you enter is shared.</p>
        <div className="mt-10 grid gap-4 md:grid-cols-2">
          {IND_KEYS.map((k) => { const I = INDUSTRIES[k]; return (
            <div key={k} className={`rounded-2xl border p-6 ${sp.get("industry") === k ? "border-emerald-500 ring-2 ring-emerald-100" : ""}`} data-testid={`demo-card-${k}`}>
              <div className="flex items-center gap-3"><I.icon className="h-6 w-6 text-emerald-600" /><h2 className="font-heading text-lg font-bold">{I.label}</h2></div>
              <p className="mt-2 text-sm text-slate-600">{I.tagline}</p>
              <div className="mt-4 flex flex-wrap gap-2">{(hasModes(k) ? ["billing", "complete"] : ["complete"]).map((m) => (
                <button key={m} disabled={!!busy} onClick={() => go(k, m)} data-testid={`demo-open-${k}-${m}`}
                  className="flex items-center gap-2 rounded-lg bg-[#0F172A] px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-60">
                  {busy === k + m && <Loader2 className="h-4 w-4 animate-spin" />}{hasModes(k) ? `Open ${MODES[m]}` : "Open demo"}</button>))}</div>
            </div>); })}
        </div>
      </section>
    </PublicShell>
  );
}
