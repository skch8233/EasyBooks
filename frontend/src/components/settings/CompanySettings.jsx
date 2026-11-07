import { useEffect, useState } from "react";
import { toast } from "sonner";
import { X } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { STATES } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export const CompanySettings = () => {
  const { settings, setSettings, isAdmin } = useApp();
  const [f, setF] = useState(settings);
  const [rate, setRate] = useState("");
  useEffect(() => setF(settings), [settings]);
  if (!f) return null;
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const save = async () => {
    try { const { data } = await api.put("/settings", f); setSettings(data); toast.success("Company settings saved"); } catch (e) { toast.error(errMsg(e)); }
  };
  const addRate = () => { const r = Number(rate); if (rate !== "" && r >= 0 && r <= 100 && !f.gst_rates.includes(r)) setF({ ...f, gst_rates: [...f.gst_rates, r].sort((a, b) => a - b) }); setRate(""); };

  return (
    <div className="rounded-xl border bg-white p-6 space-y-6" data-testid="company-settings">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5"><Label>Company name</Label><Input className="h-11" value={f.company_name} onChange={set("company_name")} disabled={!isAdmin} data-testid="company-name-input" /></div>
        <div className="space-y-1.5"><Label>GSTIN</Label><Input className="h-11 font-mono uppercase" maxLength={15} value={f.gstin} onChange={set("gstin")} disabled={!isAdmin} data-testid="company-gstin-input" /></div>
        <div className="space-y-1.5"><Label>State (used to auto-pick CGST/SGST vs IGST)</Label>
          <Select value={f.state || "none"} onValueChange={(v) => setF({ ...f, state: v === "none" ? "" : v })} disabled={!isAdmin}>
            <SelectTrigger className="h-11" data-testid="company-state-select"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="none">Not set</SelectItem>{STATES.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
          </Select></div>
        <div className="space-y-1.5"><Label>Phone</Label><Input className="h-11" value={f.phone} onChange={set("phone")} disabled={!isAdmin} data-testid="company-phone-input" /></div>
        <div className="space-y-1.5"><Label>Email</Label><Input className="h-11" value={f.email} onChange={set("email")} disabled={!isAdmin} data-testid="company-email-input" /></div>
        <div className="space-y-1.5"><Label>Address</Label><Input className="h-11" value={f.address} onChange={set("address")} disabled={!isAdmin} data-testid="company-address-input" /></div>
      </div>
      <div className="space-y-2">
        <Label>GST rates (%)</Label>
        <div className="flex flex-wrap items-center gap-2" data-testid="gst-rates-list">
          {f.gst_rates.map((r) => (
            <span key={r} className="inline-flex items-center gap-1 rounded-full border bg-slate-50 px-3 py-1.5 text-sm font-mono">{r}%
              {isAdmin && <button onClick={() => setF({ ...f, gst_rates: f.gst_rates.filter((x) => x !== r) })} data-testid={`remove-gst-rate-${r}`}><X className="h-3 w-3" /></button>}</span>
          ))}
          {isAdmin && <><Input className="h-9 w-24" type="number" placeholder="Rate" value={rate} onChange={(e) => setRate(e.target.value)} data-testid="new-gst-rate-input" />
            <Button size="sm" variant="outline" onClick={addRate} data-testid="add-gst-rate-button">Add</Button></>}
        </div>
      </div>
      {isAdmin && <Button className="h-11 px-6" onClick={save} data-testid="save-company-button">Save Settings</Button>}
    </div>
  );
};
