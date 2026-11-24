import { useState } from "react";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { INDUSTRIES, IND_KEYS, MODES, hasModes } from "@/lib/industry";
import { Button } from "@/components/ui/button";

export const IndustryPicker = ({ value, onChange, testid = "industry" }) => (
  <div className="space-y-3">
    <div className="grid gap-2 sm:grid-cols-2">{IND_KEYS.map((k) => { const I = INDUSTRIES[k]; const on = value.industry_type === k; return (
      <button type="button" key={k} onClick={() => onChange({ industry_type: k, industry_mode: hasModes(k) ? value.industry_mode || "complete" : "complete" })} data-testid={`${testid}-option-${k}`}
        className={`flex gap-3 rounded-xl border p-3 text-left transition-colors ${on ? "border-emerald-500 bg-emerald-50 ring-1 ring-emerald-500" : "hover:border-slate-400"}`}>
        <I.icon className={`h-5 w-5 mt-0.5 ${on ? "text-emerald-600" : "text-slate-500"}`} /><div><div className="text-sm font-semibold">{I.label}</div><div className="text-xs text-slate-500">{I.price} + GST / yr</div></div></button>); })}</div>
    {hasModes(value.industry_type) && <div className="flex flex-wrap gap-2" data-testid={`${testid}-modes`}>{Object.entries(MODES).map(([m, l]) => (
      <button type="button" key={m} onClick={() => onChange({ ...value, industry_mode: m })} data-testid={`${testid}-mode-${m}`}
        className={`rounded-full px-4 py-2 text-sm font-medium ${value.industry_mode === m ? "bg-[#0F172A] text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"}`}>{m === "billing" ? "Option 1: " : "Option 2: "}{l} ({m === "billing" ? "₹2,500" : "₹5,000"})</button>))}</div>}
  </div>
);

export const IndustrySettings = () => {
  const { industry, setIndustry, isAdmin } = useApp();
  const [v, setV] = useState(industry ? { industry_type: industry.industry_type, industry_mode: industry.industry_mode } : { industry_type: "wholesale", industry_mode: "complete" });
  const [busy, setBusy] = useState(false);
  const changed = industry && (v.industry_type !== industry.industry_type || v.industry_mode !== industry.industry_mode);
  const save = async () => {
    setBusy(true);
    try { const { data } = await api.put("/industry", v); setIndustry(data); toast.success(`Workspace switched to ${data.label} · ${data.mode_label}`); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };
  return (
    <div className="rounded-xl border bg-white p-6 space-y-5 max-w-3xl" data-testid="industry-settings">
      <div><h2 className="font-heading text-lg font-bold">Industry workspace</h2><p className="text-sm text-slate-500">Changes the menu labels, modules and receipt formats. Your ledgers, vouchers and reports are not changed. Current: <b data-testid="industry-current">{industry?.label} · {industry?.mode_label}</b></p></div>
      <IndustryPicker value={v} onChange={setV} testid="settings-industry" />
      {isAdmin ? <Button onClick={save} disabled={!changed || busy} data-testid="industry-save-button">Switch workspace</Button> : <p className="text-sm text-slate-500">Only an admin can change the industry.</p>}
      <p className="text-xs text-slate-500">Your paid plan stays valid until its end date. The new industry's price applies from your next renewal.</p>
      {isAdmin && ["retail", "college", "hospital"].includes(industry?.industry_type) && <Button variant="outline" size="sm" disabled={busy} data-testid="industry-sample-button" onClick={async () => {
        setBusy(true);
        try { await api.post("/industry/sample-data"); toast.success("Sample data loaded"); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); } }}>Load sample data for this industry</Button>}
    </div>
  );
};
