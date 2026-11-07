import { useState } from "react";
import { MonitorCheck } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { dmy } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export const LicenceTester = ({ onDone }) => {
  const [f, setF] = useState({ key: "", machine_id: "", device_name: "" });
  const [res, setRes] = useState(null);
  const call = async (path) => {
    try { const { data } = await api.post(`/licence/${path}`, f); setRes(data); onDone?.(); } catch (e) { setRes({ error: errMsg(e) }); }
  };

  return (
    <div className="rounded-xl border bg-white p-6 space-y-4" data-testid="licence-tester">
      <div>
        <h3 className="font-heading font-semibold text-lg flex items-center gap-2"><MonitorCheck className="h-5 w-5" /> Activate offline version</h3>
        <p className="text-sm text-slate-500">The offline app uses these same steps: enter the licence key on the computer and it is activated against its device ID. You can test or activate a device here.</p>
      </div>
      <div className="grid gap-2 sm:grid-cols-[1.4fr_1fr_1fr_auto_auto]">
        <Input className="h-11 font-mono uppercase" placeholder="EB-XXXX-XXXX-XXXX-XXXX" value={f.key} onChange={(e) => setF({ ...f, key: e.target.value })} data-testid="licence-key-input" />
        <Input className="h-11 font-mono" placeholder="Device ID" value={f.machine_id} onChange={(e) => setF({ ...f, machine_id: e.target.value })} data-testid="licence-machine-input" />
        <Input className="h-11" placeholder="Device name" value={f.device_name} onChange={(e) => setF({ ...f, device_name: e.target.value })} data-testid="licence-device-name-input" />
        <Button className="h-11" disabled={!f.key || !f.machine_id} onClick={() => call("activate")} data-testid="licence-activate-button">Activate</Button>
        <Button className="h-11" variant="outline" disabled={!f.key || !f.machine_id} onClick={() => call("validate")} data-testid="licence-validate-button">Check</Button>
      </div>
      {res?.error && <div className="rounded-lg border px-4 py-3 text-sm bg-red-50 border-red-200 text-red-900" data-testid="licence-result">{res.error}</div>}
      {res && !res.error && (
        <div className={`rounded-lg border px-4 py-3 text-sm ${res.valid ? (res.alert ? "bg-amber-50 border-amber-200 text-amber-900" : "bg-emerald-50 border-emerald-200 text-emerald-900") : "bg-red-50 border-red-200 text-red-900"}`} data-testid="licence-result">
          <b>{res.valid ? "Valid" : res.activated ? "Not valid" : "Not activated on this device"}</b> · {res.message} · Expires {dmy(res.expires_at)} · Devices {res.devices_used}/{res.max_devices} · {res.business_name}
        </div>
      )}
    </div>
  );
};
