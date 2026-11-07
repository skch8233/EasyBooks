import { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { MonitorCheck, Loader2 } from "lucide-react";
import { errMsg } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { KeyResult } from "@/components/KeyResult";
import { PublicShell } from "@/components/PublicShell";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function Activate() {
  const [f, setF] = useState({ key: "", machine_id: "" });
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try { setRes((await axios.post(`${API}/shop/activate`, f)).data); } catch (er) { toast.error(errMsg(er)); } finally { setBusy(false); }
  };
  return (
    <PublicShell>
      <div className="max-w-2xl mx-auto px-5 py-14 space-y-8" data-testid="activate-page">
        <div><h1 className="font-heading text-4xl font-extrabold tracking-tight flex items-center gap-3"><MonitorCheck className="h-9 w-9 text-primary" /> Activate offline licence</h1>
          <p className="text-slate-500 mt-3">For PCs without internet. Each licence key works on one computer only. Open Easy Books → Licence on that PC and copy its Machine ID.</p></div>
        <form onSubmit={submit} className="rounded-xl border bg-white p-6 grid gap-4" data-testid="activate-form">
          <div className="space-y-1"><Label>Licence key</Label><Input required className="h-11 font-mono uppercase" placeholder="EB-XXXX-XXXX-XXXX-XXXX" value={f.key} onChange={(e) => setF({ ...f, key: e.target.value.toUpperCase() })} data-testid="activate-key-input" /></div>
          <div className="space-y-1"><Label>Machine ID</Label><Input required pattern="[0-9A-Fa-f]{4}(-[0-9A-Fa-f]{4}){3}" title="Machine ID looks like 1A2B-3C4D-5E6F-7A8B (from the Licence screen)" className="h-11 font-mono uppercase" placeholder="XXXX-XXXX-XXXX-XXXX" value={f.machine_id} onChange={(e) => setF({ ...f, machine_id: e.target.value.toUpperCase() })} data-testid="activate-machine-input" /></div>
          <Button type="submit" className="h-12" disabled={busy} data-testid="activate-submit">{busy && <Loader2 className="h-4 w-4 animate-spin mr-2" />} Get activation code</Button>
        </form>
        {res && <KeyResult r={res} />}
      </div>
    </PublicShell>
  );
}
