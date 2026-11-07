import { useState } from "react";
import { toast } from "sonner";
import { KeyRound, ShieldCheck } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { dmy } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export default function OfflineLicence() {
  const { biz, loadBiz, isAdmin } = useApp();
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const lic = biz?.licence;
  const readFile = async (file) => file && setCode((await file.text()).trim());
  const activate = async () => {
    setBusy(true);
    try { await api.post("/offline/licence", { code }); await loadBiz(); setCode(""); toast.success("Licence activated"); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(false); }
  };

  return (
    <div className="space-y-6 max-w-3xl" data-testid="offline-licence-page">
      <h1 className="font-heading text-3xl font-extrabold tracking-tight flex items-center gap-3"><KeyRound className="h-7 w-7" /> Licence</h1>
      <div className={`rounded-xl border p-5 ${biz?.status === "active" ? "bg-emerald-50 border-emerald-200" : "bg-red-50 border-red-200"}`} data-testid="offline-licence-status">
        {lic ? <div className="grid gap-3 sm:grid-cols-3 text-sm">
          <div><div className="text-xs uppercase opacity-70">Status</div><div className="font-heading text-xl font-bold">{biz.status === "active" ? "Active" : "Expired"}</div></div>
          <div><div className="text-xs uppercase opacity-70">Valid till</div><div className="font-mono font-semibold">{dmy(lic.e)}</div>{biz.status === "active" && <div>{biz.days_left} days left</div>}</div>
          <div><div className="text-xs uppercase opacity-70">Licence key</div><div className="font-mono font-semibold">{lic.k}</div><div>{lic.b}</div></div>
        </div> : <div className="font-semibold text-red-800">No licence activated. The software is read-only until you activate a licence.</div>}
      </div>
      {isAdmin ? (
        <div className="rounded-xl border bg-white p-6 space-y-3">
          <div className="font-semibold flex items-center gap-2"><ShieldCheck className="h-4 w-4" /> Activate or renew</div>
          <p className="text-sm text-slate-500">Paste the activation code (starts with EBOL1.) or open the .lic file you got after payment on the Easy Books website. Renewal keys are ₹6,500 + GST per year.</p>
          <Textarea rows={4} className="font-mono text-xs" placeholder="EBOL1...." value={code} onChange={(e) => setCode(e.target.value)} data-testid="offline-code-input" />
          <div className="flex flex-wrap gap-2 items-center">
            <Button onClick={activate} disabled={!code.trim() || busy} data-testid="offline-activate-button">Activate licence</Button>
            <label className="text-sm text-primary cursor-pointer underline"><input type="file" accept=".lic,.txt" className="hidden" onChange={(e) => readFile(e.target.files[0])} data-testid="offline-lic-file" />Open .lic file</label>
          </div>
        </div>
      ) : <p className="text-sm text-slate-500">Ask your admin to activate or renew the licence.</p>}
    </div>
  );
}
