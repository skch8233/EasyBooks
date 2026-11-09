import { useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Copy, Globe, KeyRound, Loader2, MonitorCheck, ShieldCheck } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { useApp } from "@/context/AppContext";
import { dmy } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

const SERVER = (process.env.REACT_APP_LICENCE_SERVER || "").replace(/\/$/, "");
const ONLINE_OK = SERVER.startsWith("https://") && !SERVER.includes("YOUR-EASYBOOKS-SITE");

const Status = ({ biz }) => {
  const lic = biz?.licence;
  const trial = biz?.status === "trial";
  const tone = biz?.status === "active" ? "bg-emerald-50 border-emerald-200" : trial ? "bg-amber-50 border-amber-200" : "bg-red-50 border-red-200";
  return (
    <div className={`rounded-xl border p-5 ${tone}`} data-testid="offline-licence-status">
      {lic && biz.status === "active" ? <div className="grid gap-3 sm:grid-cols-4 text-sm">
        <div><div className="text-xs uppercase opacity-70">Status</div><div className="font-heading text-xl font-bold">Active</div></div>
        <div><div className="text-xs uppercase opacity-70">Valid till</div><div className="font-mono font-semibold">{dmy(lic.e)}</div><div>{biz.days_left} days left</div></div>
        <div><div className="text-xs uppercase opacity-70">Licence key</div><div className="font-mono font-semibold">{lic.k}</div><div>{lic.b}</div></div>
        <div><div className="text-xs uppercase opacity-70">Type</div><div className="font-semibold" data-testid="offline-licence-tier">{lic.t === "multi" ? `Multi-PC (up to ${lic.c} computers)` : "Single-PC"}</div></div>
      </div> : trial ? <div className="text-amber-900" data-testid="offline-trial-status">
        <div className="font-heading text-xl font-bold">Free trial: {biz.days_left} day{biz.days_left === 1 ? "" : "s"} left</div>
        <div className="text-sm">All features are unlocked until {dmy(biz.ends_at)}. After that, Easy Books asks for a subscription key.</div>
      </div> : <div className="text-red-800" data-testid="offline-paywall">
        <div className="font-heading text-xl font-bold">Subscription key required</div>
        <div className="text-sm">{biz?.reason || "Enter a subscription key to continue."} Your data is safe and will be there once you activate.</div>
        <a href={`${SERVER}/buy`} target="_blank" rel="noreferrer" className={`text-sm font-semibold underline ${ONLINE_OK ? "" : "hidden"}`} data-testid="offline-buy-link">Buy a key</a>
      </div>}
    </div>
  );
};

const MachineId = ({ id }) => (
  <div className="rounded-xl border bg-white p-5 flex flex-wrap items-center gap-4" data-testid="offline-machine-box">
    <MonitorCheck className="h-6 w-6 text-primary" />
    <div className="flex-1"><div className="text-xs uppercase text-slate-500">This computer's Machine ID</div>
      <div className="font-mono text-lg font-semibold tracking-wider" data-testid="offline-machine-id">{id || "..."}</div>
      <div className="text-xs text-slate-500">A Single-PC key works on this computer only. A Multi-PC key can be activated on up to 8 computers.</div></div>
    <Button variant="outline" onClick={() => navigator.clipboard?.writeText(id).then(() => toast.success("Copied"))} data-testid="copy-machine-id"><Copy className="h-4 w-4 mr-1" /> Copy</Button>
  </div>
);

export default function OfflineLicence() {
  const { biz, loadBiz, isAdmin } = useApp();
  const [code, setCode] = useState("");
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState("");
  const readFile = async (file) => file && setCode((await file.text()).trim());
  const apply = async (c) => { await api.post("/offline/licence", { code: c }); await loadBiz(); setCode(""); setKey(""); toast.success("Licence activated on this PC"); };
  const run = async (what, fn) => { setBusy(what); try { await fn(); } catch (e) { toast.error(errMsg(e)); } finally { setBusy(""); } };
  const online = () => run("online", async () => {
    const { data } = await axios.post(`${SERVER}/api/shop/activate`, { key: key.trim(), machine_id: biz.machine_id });
    await apply(data.code);
  });

  return (
    <div className="space-y-6 max-w-3xl" data-testid="offline-licence-page">
      <h1 className="font-heading text-3xl font-extrabold tracking-tight flex items-center gap-3"><KeyRound className="h-7 w-7" /> Licence</h1>
      <Status biz={biz} />
      <MachineId id={biz?.machine_id} />
      {!isAdmin ? <p className="text-sm text-slate-500">Ask your admin to activate or renew the licence.</p> : <>
        <div className="rounded-xl border bg-white p-6 space-y-3" data-testid="offline-online-activate">
          <div className="font-semibold flex items-center gap-2"><Globe className="h-4 w-4" /> Enter subscription key (needs internet once)</div>
          <p className="text-sm text-slate-500">Enter the licence key from your purchase email. After activation Easy Books works fully offline with no login. After a renewal, click again to load the new expiry date.</p>
          <div className="flex flex-wrap gap-2">
            <Input className="h-11 font-mono uppercase flex-1 min-w-[240px]" placeholder="EB-XXXX-XXXX-XXXX-XXXX" value={key} onChange={(e) => setKey(e.target.value.toUpperCase())} data-testid="offline-key-input" />
            <Button className="h-11" onClick={online} disabled={!ONLINE_OK || !key.trim() || !biz?.machine_id || !!busy} data-testid="offline-activate-online-button">
              {busy === "online" && <Loader2 className="h-4 w-4 animate-spin mr-2" />} Activate online</Button>
          </div>
          {!ONLINE_OK && <p className="text-xs text-amber-700" data-testid="offline-online-unavailable">Online activation is not set up in this build. Use the activation code below.</p>}
        </div>
        <div className="rounded-xl border bg-white p-6 space-y-3">
          <div className="font-semibold flex items-center gap-2"><ShieldCheck className="h-4 w-4" /> No internet? Paste an activation code</div>
          <p className="text-sm text-slate-500">On any phone or PC, open the Easy Books website page <b>/activate</b>, enter your licence key and the Machine ID above, then paste the code (starts with EBOL1.) or open the .lic file here.</p>
          <Textarea rows={4} className="font-mono text-xs" placeholder="EBOL1...." value={code} onChange={(e) => setCode(e.target.value)} data-testid="offline-code-input" />
          <div className="flex flex-wrap gap-2 items-center">
            <Button onClick={() => run("code", () => apply(code))} disabled={!code.trim() || !!busy} data-testid="offline-activate-button">Activate licence</Button>
            <label className="text-sm text-primary cursor-pointer underline"><input type="file" accept=".lic,.txt" className="hidden" onChange={(e) => readFile(e.target.files[0])} data-testid="offline-lic-file" />Open .lic file</label>
          </div>
        </div>
      </>}
    </div>
  );
}
