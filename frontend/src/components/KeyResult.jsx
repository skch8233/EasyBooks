import { useState } from "react";
import { toast } from "sonner";
import { Copy, Download, KeyRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { dmy } from "@/lib/format";
import { downloadText } from "@/lib/offline";

export const KeyResult = ({ r }) => {
  const [show, setShow] = useState(false);
  const copy = (t) => navigator.clipboard?.writeText(t).then(() => toast.success("Copied"));
  return (
    <div className="rounded-xl border-2 border-emerald-300 bg-emerald-50 p-6 space-y-4" data-testid="key-result">
      <div className="flex items-center gap-2 text-emerald-800 font-heading text-xl font-bold"><KeyRound className="h-5 w-5" /> Your licence is ready</div>
      <div className="grid gap-2 sm:grid-cols-3 text-sm">
        <div><div className="text-xs uppercase text-slate-500">Licence key</div><div className="font-mono font-semibold" data-testid="result-licence-key">{r.key}</div></div>
        <div><div className="text-xs uppercase text-slate-500">Valid till</div><div className="font-mono font-semibold" data-testid="result-expires">{dmy(r.expires)}</div></div>
        <div><div className="text-xs uppercase text-slate-500">Registered to</div><div className="font-semibold">{r.business_name}</div></div>
      </div>
      <div>
        <div className="text-xs uppercase text-slate-500 mb-1">Activation code (paste in the offline app → Licence)</div>
        <div className={`rounded-md bg-white border p-3 font-mono text-xs break-all ${show ? "" : "max-h-14 overflow-hidden"}`} data-testid="result-activation-code">{r.code}</div>
        <button className="text-xs text-primary mt-1" onClick={() => setShow(!show)}>{show ? "Show less" : "Show full code"}</button>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => copy(r.code)} data-testid="copy-activation-code"><Copy className="h-4 w-4 mr-1" /> Copy activation code</Button>
        <Button variant="outline" onClick={() => downloadText(`EasyBooks-${r.key}.lic`, r.code)} data-testid="download-licence-file"><Download className="h-4 w-4 mr-1" /> Download licence file</Button>
        <Button variant="outline" onClick={() => copy(r.key)} data-testid="copy-licence-key"><Copy className="h-4 w-4 mr-1" /> Copy key</Button>
      </div>
      <p className="text-xs text-slate-600">Save this now. Keep your licence key safe: you need it to buy next year's renewal.</p>
    </div>
  );
};
